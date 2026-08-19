from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime

from .fortune import roll_slip
from .members import GroupMember, filter_candidates
from .models import DrawConfig, DrawKind, DrawResult, GroupDayState, WifeBond
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
        await self.save(chat_key, GroupDayState(date=today_str(self._clock()), bonds={}))

    async def divorce(self, chat_key: str, user_id: str) -> WifeBond | None:
        state = await self.load(chat_key)
        bond = state.bonds.pop(str(user_id), None)
        if bond is not None:
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
        now = self._clock()
        bond = WifeBond(
            user_id=user_id,
            user_name=user_name or f"用户({user_id})",
            wife_id=wife.user_id,
            wife_name=wife.name,
            rarity=slip.rarity,
            title=slip.title,
            affinity=slip.affinity,
            flavor=slip.flavor,
            timestamp=now.isoformat(timespec="seconds"),
        )
        state.bonds[user_id] = bond
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
    owner = next(
        (bond for uid, bond in state.bonds.items() if uid != user_id and bond.wife_id == wife_id),
        None,
    )
    return mutual, owner is not None, owner


__all__ = ["DrawService", "MemoryStateStore", "DrawConfig", "DrawKind", "DrawResult"]
