from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class DrawKind(str, Enum):
    DRAWN = "drawn"
    ALREADY_BOUND = "already_bound"
    NO_CANDIDATES = "no_candidates"


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
        )


@dataclass
class GroupDayState:
    date: str
    bonds: dict[str, WifeBond] = field(default_factory=dict)


@dataclass(frozen=True)
class DrawConfig:
    exclude_self: bool = True
    exclude_bot: bool = True
    excluded_user_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass
class DrawResult:
    kind: DrawKind
    bond: WifeBond | None = None
    mutual: bool = False
    shura: bool = False
    shura_owner_id: str | None = None
    shura_owner_name: str | None = None
