from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DrawKind(str, Enum):
    DRAWN = "drawn"
    ALREADY_BOUND = "already_bound"
    NO_CANDIDATES = "no_candidates"


class PlayKind(str, Enum):
    STEAL_SUCCESS = "steal_success"
    STEAL_FAIL = "steal_fail"
    STEAL_PROTECTED = "steal_protected"
    STEAL_SELF = "steal_self"
    STEAL_ALREADY_YOURS = "steal_already_yours"
    STEAL_LIMIT = "steal_limit"
    STEAL_REVERSE = "steal_reverse"
    GIFT_SUCCESS = "gift_success"
    GIFT_NO_WIFE = "gift_no_wife"
    GIFT_SELF = "gift_self"
    SWAP_SUCCESS = "swap_success"
    SWAP_NEED_BOTH = "swap_need_both"
    SWAP_SELF = "swap_self"
    PROTECT_SUCCESS = "protect_success"
    PROTECT_NO_WIFE = "protect_no_wife"
    PROTECT_ALREADY = "protect_already"
    PET_SUCCESS = "pet_success"
    PET_NO_WIFE = "pet_no_wife"
    PET_LIMIT = "pet_limit"
    REMARRY_SUCCESS = "remarry_success"
    REMARRY_NONE = "remarry_none"
    REMARRY_HAS_WIFE = "remarry_has_wife"
    REMARRY_TAKEN = "remarry_taken"
    HOUSEHOLD = "household"


@dataclass(frozen=True)
class FortuneSlip:
    rarity: str
    title: str
    affinity: int
    flavor: str


@dataclass
class WifeBond:
    user_id: str
    user_name: str
    wife_id: str
    wife_name: str
    rarity: str
    title: str
    affinity: int
    flavor: str
    timestamp: str
    protected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WifeBond:
        return cls(
            user_id=str(data["user_id"]),
            user_name=str(data.get("user_name") or ""),
            wife_id=str(data["wife_id"]),
            wife_name=str(data.get("wife_name") or ""),
            rarity=str(data.get("rarity") or "普通"),
            title=str(data.get("title") or "普通群友"),
            affinity=int(data.get("affinity") or 1),
            flavor=str(data.get("flavor") or ""),
            timestamp=str(data.get("timestamp") or ""),
            protected=bool(data.get("protected") or False),
        )


@dataclass
class UserStats:
    name: str = ""
    divorces: int = 0
    steals: int = 0
    steal_fails: int = 0
    stolen_from: int = 0
    steal_attempts: int = 0
    pets: int = 0
    gifts: int = 0
    swaps: int = 0
    protects: int = 0
    last_ex: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UserStats:
        last_ex = data.get("last_ex")
        if not isinstance(last_ex, dict):
            last_ex = None
        return cls(
            name=str(data.get("name") or ""),
            divorces=int(data.get("divorces") or 0),
            steals=int(data.get("steals") or 0),
            steal_fails=int(data.get("steal_fails") or 0),
            stolen_from=int(data.get("stolen_from") or 0),
            steal_attempts=int(data.get("steal_attempts") or 0),
            pets=int(data.get("pets") or 0),
            gifts=int(data.get("gifts") or 0),
            swaps=int(data.get("swaps") or 0),
            protects=int(data.get("protects") or 0),
            last_ex=last_ex,
        )


@dataclass
class GroupDayState:
    date: str
    bonds: dict[str, WifeBond] = field(default_factory=dict)
    stats: dict[str, UserStats] = field(default_factory=dict)


@dataclass(frozen=True)
class DrawConfig:
    exclude_self: bool = True
    exclude_bot: bool = True
    excluded_user_ids: frozenset[str] = field(default_factory=frozenset)
    steal_daily_limit: int = 3
    pet_daily_limit: int = 5
    claim_chance: int = 62
    reverse_chance: int = 18


@dataclass
class DrawResult:
    kind: DrawKind
    bond: WifeBond | None = None
    mutual: bool = False
    shura: bool = False
    shura_owner_id: str | None = None
    shura_owner_name: str | None = None


@dataclass
class PlayResult:
    kind: PlayKind
    bond: WifeBond | None = None
    dumped_bond: WifeBond | None = None
    other_bond: WifeBond | None = None
    victim_id: str | None = None
    victim_name: str | None = None
    affinity_gain: int = 0
    chance: int = 0


@dataclass
class Household:
    target_id: str
    target_name: str
    as_husband: WifeBond | None = None
    as_wife_of: WifeBond | None = None
