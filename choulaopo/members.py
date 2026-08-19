from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class GroupMember:
    user_id: str
    name: str


def member_display_name(raw: dict[str, Any]) -> str:
    uid = str(raw.get("user_id", "")).strip()
    card = str(raw.get("card") or "").strip()
    nickname = str(raw.get("nickname") or "").strip()
    return card or nickname or (f"用户({uid})" if uid else "未知群友")


def coerce_member_list(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        for key in ("data", "members", "member_list"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("无法解析群成员列表")


def parse_members(raw_members: Iterable[dict[str, Any]]) -> list[GroupMember]:
    members: list[GroupMember] = []
    seen: set[str] = set()
    for raw in raw_members:
        uid = str(raw.get("user_id", "")).strip()
        if not uid or uid in seen:
            continue
        seen.add(uid)
        members.append(GroupMember(user_id=uid, name=member_display_name(raw)))
    return members


def filter_candidates(
    members: Iterable[GroupMember],
    *,
    drawer_id: str,
    bot_id: str = "",
    excluded_user_ids: Iterable[str] = (),
    exclude_self: bool = True,
    exclude_bot: bool = True,
) -> list[GroupMember]:
    blocked: set[str] = {str(x).strip() for x in excluded_user_ids if str(x).strip()}
    if exclude_self and drawer_id:
        blocked.add(str(drawer_id))
    if exclude_bot and bot_id:
        blocked.add(str(bot_id))
    return [m for m in members if m.user_id not in blocked]
