from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol

from .models import GroupDayState, UserStats, WifeBond

STORE_KEY = "day_state"


class StateKV(Protocol):
    async def get(self, chat_key: str, store_key: str = STORE_KEY) -> str | None: ...

    async def set(self, chat_key: str, store_key: str = STORE_KEY, value: str = "") -> None: ...


class MemoryStateStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, chat_key: str, store_key: str = STORE_KEY) -> str | None:
        return self._data.get(f"{chat_key}:{store_key}")

    async def set(self, chat_key: str, store_key: str = STORE_KEY, value: str = "") -> None:
        self._data[f"{chat_key}:{store_key}"] = value


def dump_state(state: GroupDayState) -> str:
    payload = {
        "date": state.date,
        "bonds": {uid: bond.to_dict() for uid, bond in state.bonds.items()},
        "stats": {uid: item.to_dict() for uid, item in state.stats.items()},
    }
    return json.dumps(payload, ensure_ascii=False)


def load_state(raw: str | None, today: str) -> GroupDayState:
    if not raw:
        return GroupDayState(date=today)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return GroupDayState(date=today)
    if str(data.get("date") or "") != today:
        return GroupDayState(date=today)
    bonds: dict[str, WifeBond] = {}
    for uid, item in (data.get("bonds") or {}).items():
        try:
            bonds[str(uid)] = WifeBond.from_dict(item)
        except (KeyError, TypeError, ValueError):
            continue
    stats: dict[str, UserStats] = {}
    for uid, item in (data.get("stats") or {}).items():
        if not isinstance(item, dict):
            continue
        try:
            stats[str(uid)] = UserStats.from_dict(item)
        except (TypeError, ValueError):
            continue
    return GroupDayState(date=today, bonds=bonds, stats=stats)


def today_str(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")
