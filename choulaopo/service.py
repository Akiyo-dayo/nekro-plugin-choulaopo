from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime

from .fortune import roll_slip, steal_success_chance
from .members import GroupMember, filter_candidates
from .models import (
    DrawConfig,
    DrawKind,
    DrawResult,
    GroupDayState,
    Household,
    PlayKind,
    PlayResult,
    UserStats,
    WifeBond,
)
from .store import STORE_KEY, MemoryStateStore, StateKV, dump_state, load_state, today_str

Clock = Callable[[], datetime]
RngFactory = Callable[[], random.Random]


class DrawService:
    def __init__(
        self,
        store: StateKV,
        rng_factory: RngFactory | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._store = store
        self._rng_factory = rng_factory or random.Random
        self._clock = clock or datetime.now

    async def load(self, chat_key: str) -> GroupDayState:
        raw = await self._store.get(chat_key, STORE_KEY)
        return load_state(raw, today_str(self._clock()))

    async def save(self, chat_key: str, state: GroupDayState) -> None:
        await self._store.set(chat_key, STORE_KEY, dump_state(state))

    async def get_bond(self, chat_key: str, user_id: str) -> WifeBond | None:
        state = await self.load(chat_key)
        return state.bonds.get(str(user_id))

    async def list_bonds(self, chat_key: str) -> list[WifeBond]:
        state = await self.load(chat_key)
        return list(state.bonds.values())

    async def reset(self, chat_key: str) -> None:
        await self.save(chat_key, GroupDayState(date=today_str(self._clock())))

    async def divorce(self, chat_key: str, user_id: str) -> WifeBond | None:
        state = await self.load(chat_key)
        user_id = str(user_id)
        bond = state.bonds.pop(user_id, None)
        if bond is not None:
            stats = _stats(state, user_id, bond.user_name)
            stats.divorces += 1
            _remember_ex(stats, bond)
            await self.save(chat_key, state)
        return bond

    async def draw(
        self,
        chat_key: str,
        user_id: str,
        user_name: str,
        members: list[GroupMember],
        bot_id: str,
        config: DrawConfig,
        forced_wife_id: str | None = None,
    ) -> DrawResult:
        user_id = str(user_id)
        state = await self.load(chat_key)
        existing = state.bonds.get(user_id)
        if existing is not None:
            mutual, shura, owner = _relation_flags(state, user_id, existing.wife_id)
            return DrawResult(
                kind=DrawKind.ALREADY_BOUND,
                bond=existing,
                mutual=mutual,
                shura=shura,
                shura_owner_id=owner.user_id if owner else None,
                shura_owner_name=owner.user_name if owner else None,
            )

        wife = _pick_wife(members, user_id, bot_id, config, self._rng_factory(), forced_wife_id)
        if wife is None:
            return DrawResult(kind=DrawKind.NO_CANDIDATES)

        slip = roll_slip(self._rng_factory())
        bond = _make_bond(user_id, user_name, wife.user_id, wife.name, slip.rarity, slip.title, slip.affinity, slip.flavor, self._clock())
        state.bonds[user_id] = bond
        _stats(state, user_id, bond.user_name)
        await self.save(chat_key, state)
        mutual, shura, owner = _relation_flags(state, user_id, wife.user_id)
        return DrawResult(
            kind=DrawKind.DRAWN,
            bond=bond,
            mutual=mutual,
            shura=shura,
            shura_owner_id=owner.user_id if owner else None,
            shura_owner_name=owner.user_name if owner else None,
        )

    async def steal(
        self,
        chat_key: str,
        user_id: str,
        user_name: str,
        target_id: str,
        target_name: str,
        *,
        forced_success: bool | None = None,
        config: DrawConfig | None = None,
    ) -> PlayResult:
        config = config or DrawConfig()
        user_id = str(user_id)
        target_id = str(target_id)
        state = await self.load(chat_key)
        if user_id == target_id:
            return PlayResult(kind=PlayKind.STEAL_SELF)
        actor_bond = state.bonds.get(user_id)
        if actor_bond is not None and actor_bond.wife_id == target_id:
            return PlayResult(kind=PlayKind.STEAL_ALREADY_YOURS, bond=actor_bond)

        stats = _stats(state, user_id, user_name)
        if stats.steal_attempts >= config.steal_daily_limit:
            return PlayResult(kind=PlayKind.STEAL_LIMIT)

        owner = _owner_of(state, target_id, exclude_user=user_id)
        if owner is not None and owner.protected:
            stats.steal_attempts += 1
            stats.steal_fails += 1
            await self.save(chat_key, state)
            return PlayResult(
                kind=PlayKind.STEAL_PROTECTED,
                bond=owner,
                victim_id=owner.user_id,
                victim_name=owner.user_name,
            )

        chance = steal_success_chance(owner.rarity, owner.affinity, False) if owner else config.claim_chance
        success = chance >= 1 and (forced_success if forced_success is not None else self._rng_factory().randint(1, 100) <= chance)
        stats.steal_attempts += 1
        if not success:
            stats.steal_fails += 1
            reverse = None
            if forced_success is None and actor_bond is not None and owner is not None:
                if self._rng_factory().randint(1, 100) <= config.reverse_chance:
                    reverse = _force_dump(state, user_id)
                    if reverse is not None:
                        _stats(state, owner.user_id, owner.user_name).steals += 1
                        _stats(state, user_id, user_name).stolen_from += 1
            await self.save(chat_key, state)
            if reverse is not None:
                return PlayResult(
                    kind=PlayKind.STEAL_REVERSE,
                    bond=owner,
                    dumped_bond=reverse,
                    victim_id=owner.user_id,
                    victim_name=owner.user_name,
                    chance=chance,
                )
            return PlayResult(
                kind=PlayKind.STEAL_FAIL,
                bond=owner,
                victim_id=owner.user_id if owner else None,
                victim_name=owner.user_name if owner else None,
                chance=chance,
            )

        dumped = _force_dump(state, user_id)
        now = self._clock()
        victim_id = owner.user_id if owner else None
        victim_name = owner.user_name if owner else None
        if owner is not None:
            victim_stats = _stats(state, owner.user_id, owner.user_name)
            victim_stats.stolen_from += 1
            _remember_ex(victim_stats, owner)
            state.bonds.pop(owner.user_id, None)
            bond = _make_bond(
                user_id,
                user_name,
                target_id,
                target_name or owner.wife_name,
                owner.rarity,
                owner.title,
                owner.affinity,
                owner.flavor,
                now,
            )
        else:
            slip = roll_slip(self._rng_factory())
            bond = _make_bond(user_id, user_name, target_id, target_name, slip.rarity, slip.title, slip.affinity, slip.flavor, now)
        state.bonds[user_id] = bond
        stats.steals += 1
        await self.save(chat_key, state)
        return PlayResult(
            kind=PlayKind.STEAL_SUCCESS,
            bond=bond,
            dumped_bond=dumped,
            victim_id=victim_id,
            victim_name=victim_name,
            chance=chance,
        )

    async def gift(
        self,
        chat_key: str,
        user_id: str,
        user_name: str,
        target_id: str,
        target_name: str,
    ) -> PlayResult:
        user_id = str(user_id)
        target_id = str(target_id)
        if user_id == target_id:
            return PlayResult(kind=PlayKind.GIFT_SELF)
        state = await self.load(chat_key)
        given = state.bonds.get(user_id)
        if given is None:
            return PlayResult(kind=PlayKind.GIFT_NO_WIFE)
        dumped = _force_dump(state, target_id)
        state.bonds.pop(user_id, None)
        giver = _stats(state, user_id, user_name)
        _remember_ex(giver, given)
        giver.gifts += 1
        bond = _make_bond(
            target_id,
            target_name,
            given.wife_id,
            given.wife_name,
            given.rarity,
            given.title,
            given.affinity,
            given.flavor,
            self._clock(),
        )
        state.bonds[target_id] = bond
        await self.save(chat_key, state)
        return PlayResult(kind=PlayKind.GIFT_SUCCESS, bond=bond, dumped_bond=dumped, victim_id=user_id, victim_name=user_name)

    async def swap(
        self,
        chat_key: str,
        user_id: str,
        user_name: str,
        target_id: str,
        target_name: str,
    ) -> PlayResult:
        user_id = str(user_id)
        target_id = str(target_id)
        if user_id == target_id:
            return PlayResult(kind=PlayKind.SWAP_SELF)
        state = await self.load(chat_key)
        left = state.bonds.get(user_id)
        right = state.bonds.get(target_id)
        if left is None or right is None:
            return PlayResult(kind=PlayKind.SWAP_NEED_BOTH, bond=left, other_bond=right)
        left.user_name = user_name or left.user_name
        right.user_name = target_name or right.user_name
        left.wife_id, right.wife_id = right.wife_id, left.wife_id
        left.wife_name, right.wife_name = right.wife_name, left.wife_name
        left.rarity, right.rarity = right.rarity, left.rarity
        left.title, right.title = right.title, left.title
        left.affinity, right.affinity = right.affinity, left.affinity
        left.flavor, right.flavor = right.flavor, left.flavor
        left.protected = False
        right.protected = False
        _stats(state, user_id, left.user_name).swaps += 1
        _stats(state, target_id, right.user_name).swaps += 1
        await self.save(chat_key, state)
        return PlayResult(kind=PlayKind.SWAP_SUCCESS, bond=left, other_bond=right)

    async def protect(self, chat_key: str, user_id: str) -> PlayResult:
        state = await self.load(chat_key)
        user_id = str(user_id)
        bond = state.bonds.get(user_id)
        if bond is None:
            return PlayResult(kind=PlayKind.PROTECT_NO_WIFE)
        stats = _stats(state, user_id, bond.user_name)
        if bond.protected or stats.protects >= 1:
            return PlayResult(kind=PlayKind.PROTECT_ALREADY, bond=bond)
        bond.protected = True
        stats.protects += 1
        await self.save(chat_key, state)
        return PlayResult(kind=PlayKind.PROTECT_SUCCESS, bond=bond)

    async def pet(self, chat_key: str, user_id: str, config: DrawConfig | None = None) -> PlayResult:
        config = config or DrawConfig()
        state = await self.load(chat_key)
        user_id = str(user_id)
        bond = state.bonds.get(user_id)
        if bond is None:
            return PlayResult(kind=PlayKind.PET_NO_WIFE)
        stats = _stats(state, user_id, bond.user_name)
        if stats.pets >= config.pet_daily_limit:
            return PlayResult(kind=PlayKind.PET_LIMIT, bond=bond)
        gain = self._rng_factory().randint(2, 8)
        bond.affinity = min(100, bond.affinity + gain)
        stats.pets += 1
        await self.save(chat_key, state)
        return PlayResult(kind=PlayKind.PET_SUCCESS, bond=bond, affinity_gain=gain)

    async def remarry(self, chat_key: str, user_id: str, user_name: str) -> PlayResult:
        state = await self.load(chat_key)
        user_id = str(user_id)
        existing = state.bonds.get(user_id)
        if existing is not None:
            return PlayResult(kind=PlayKind.REMARRY_HAS_WIFE, bond=existing)
        stats = _stats(state, user_id, user_name)
        ex = stats.last_ex or {}
        ex_id = str(ex.get("wife_id") or "")
        if not ex_id:
            return PlayResult(kind=PlayKind.REMARRY_NONE)
        owner = _owner_of(state, ex_id)
        if owner is not None:
            return PlayResult(kind=PlayKind.REMARRY_TAKEN, victim_id=owner.user_id, victim_name=owner.user_name)
        bond = _make_bond(
            user_id,
            user_name,
            ex_id,
            str(ex.get("wife_name") or f"用户({ex_id})"),
            str(ex.get("rarity") or "普通"),
            str(ex.get("title") or "普通群友"),
            int(ex.get("affinity") or 1),
            str(ex.get("flavor") or ""),
            self._clock(),
        )
        state.bonds[user_id] = bond
        await self.save(chat_key, state)
        return PlayResult(kind=PlayKind.REMARRY_SUCCESS, bond=bond)

    async def household(self, chat_key: str, target_id: str, target_name: str = "") -> Household:
        state = await self.load(chat_key)
        target_id = str(target_id)
        as_husband = state.bonds.get(target_id)
        as_wife_of = _owner_of(state, target_id)
        name = target_name or (as_husband.user_name if as_husband else "") or (as_wife_of.wife_name if as_wife_of else "") or target_id
        return Household(target_id=target_id, target_name=name, as_husband=as_husband, as_wife_of=as_wife_of)

    async def boards(self, chat_key: str, limit: int = 5) -> dict[str, list[tuple[str, int]]]:
        state = await self.load(chat_key)
        love = sorted(((bond.user_name, bond.affinity) for bond in state.bonds.values()), key=lambda row: -row[1])[:limit]
        scum: list[tuple[str, int]] = []
        unlucky: list[tuple[str, int]] = []
        for uid, stats in state.stats.items():
            name = stats.name or uid
            score = stats.steals + stats.divorces
            if score:
                scum.append((name, score))
            if stats.stolen_from:
                unlucky.append((name, stats.stolen_from))
        scum.sort(key=lambda row: -row[1])
        unlucky.sort(key=lambda row: -row[1])
        return {"love": love, "scum": scum[:limit], "unlucky": unlucky[:limit]}


def _pick_wife(
    members: list[GroupMember],
    user_id: str,
    bot_id: str,
    config: DrawConfig,
    rng: random.Random,
    forced_wife_id: str | None,
) -> GroupMember | None:
    if forced_wife_id:
        for member in members:
            if member.user_id == str(forced_wife_id):
                return member
        return GroupMember(user_id=str(forced_wife_id), name=f"用户({forced_wife_id})")

    candidates = filter_candidates(
        members,
        drawer_id=user_id,
        bot_id=bot_id,
        excluded_user_ids=config.excluded_user_ids,
        exclude_self=config.exclude_self,
        exclude_bot=config.exclude_bot,
    )
    if not candidates:
        return None
    return rng.choice(candidates)


def _relation_flags(
    state: GroupDayState,
    user_id: str,
    wife_id: str,
) -> tuple[bool, bool, WifeBond | None]:
    other = state.bonds.get(wife_id)
    mutual = other is not None and other.wife_id == user_id
    owner = _owner_of(state, wife_id, exclude_user=user_id)
    return mutual, owner is not None, owner


def _owner_of(state: GroupDayState, wife_id: str, exclude_user: str | None = None) -> WifeBond | None:
    wife_id = str(wife_id)
    for uid, bond in state.bonds.items():
        if exclude_user and uid == exclude_user:
            continue
        if bond.wife_id == wife_id:
            return bond
    return None


def _stats(state: GroupDayState, user_id: str, name: str = "") -> UserStats:
    stats = state.stats.get(user_id)
    if stats is None:
        stats = UserStats(name=name)
        state.stats[user_id] = stats
    elif name:
        stats.name = name
    return stats


def _remember_ex(stats: UserStats, bond: WifeBond) -> None:
    stats.last_ex = {
        "wife_id": bond.wife_id,
        "wife_name": bond.wife_name,
        "rarity": bond.rarity,
        "title": bond.title,
        "affinity": bond.affinity,
        "flavor": bond.flavor,
    }


def _force_dump(state: GroupDayState, user_id: str) -> WifeBond | None:
    bond = state.bonds.pop(str(user_id), None)
    if bond is None:
        return None
    stats = _stats(state, str(user_id), bond.user_name)
    _remember_ex(stats, bond)
    return bond


def _make_bond(
    user_id: str,
    user_name: str,
    wife_id: str,
    wife_name: str,
    rarity: str,
    title: str,
    affinity: int,
    flavor: str,
    now: datetime,
) -> WifeBond:
    return WifeBond(
        user_id=str(user_id),
        user_name=user_name or f"用户({user_id})",
        wife_id=str(wife_id),
        wife_name=wife_name or f"用户({wife_id})",
        rarity=rarity,
        title=title,
        affinity=int(affinity),
        flavor=flavor,
        timestamp=now.isoformat(timespec="seconds"),
        protected=False,
    )


__all__ = ["DrawService", "MemoryStateStore", "DrawConfig", "DrawKind", "DrawResult", "PlayKind", "PlayResult"]
