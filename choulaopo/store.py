from __future__ import annotations

import json
from datetime import datetime
from typing import Protocol

from .models import GroupDayState, WifeBond

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
    }
    return json.dumps(payload, ensure_ascii=False)


def load_state(raw: str | None, today: str) -> GroupDayState:
    if not raw:
        return GroupDayState(date=today, bonds={})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return GroupDayState(date=today, bonds={})
    if str(data.get("date") or "") != today:
        return GroupDayState(date=today, bonds={})
    bonds: dict[str, WifeBond] = {}
    for uid, item in (data.get("bonds") or {}).items():
        try:
            bonds[str(uid)] = WifeBond.from_dict(item)
        except (KeyError, TypeError, ValueError):
            continue
    return GroupDayState(date=today, bonds=bonds)


def today_str(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y-%m-%d")
