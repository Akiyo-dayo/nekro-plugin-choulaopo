from __future__ import annotations

from .models import WifeBond

AVATAR_URL = "https://q4.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640"


def avatar_url(qq: str) -> str:
    return AVATAR_URL.format(qq=qq)


def build_at(uid: str, nickname: str | None = None) -> str:
    nick = (nickname or "").strip()
    if nick:
        return f"[@id:{uid};nickname:{nick}@]"
    return f"[@id:{uid}@]"


def _person(uid: str, name: str, mention: bool) -> str:
    if mention:
        return build_at(uid, name)
    return name or uid


def render_drawn(
    bond: WifeBond,
    *,
    drawer_name: str,
    mutual: bool,
    shura_owner_name: str | None,
    mention: bool = True,
) -> str:
    drawer = _person(bond.user_id, drawer_name or bond.user_name, mention)
    wife = _person(bond.wife_id, bond.wife_name, mention)
    lines = [
        f"{drawer} 姻缘签落下！",
        f"今日正缘：{wife}",
        f"【{bond.rarity}】{bond.title} · 契合度 {bond.affinity}",
        f"「{bond.flavor}」",
    ]
    if mutual:
        lines.append("双方互相抽中，这是货真价实的【天作之合】，群里可以开始撒花了。")
    if shura_owner_name:
        lines.append(f"警告：修罗场已开启——{shura_owner_name} 今天也把这位认作正缘。")
    return "\n".join(lines)


def render_already_bound(bond: WifeBond, *, mention: bool = True) -> str:
    wife = _person(bond.wife_id, bond.wife_name, mention)
    return (
        f"{_person(bond.user_id, bond.user_name, mention)} 你今天已经名草有主了。\n"
        f"正缘是 {wife}【{bond.rarity}·{bond.title}】，契合度 {bond.affinity}。\n"
        "想换人的话先打「离婚」，渣也要有仪式感。"
    )


def render_my_wife(bond: WifeBond, *, mention: bool = True) -> str:
    wife = _person(bond.wife_id, bond.wife_name, mention)
    return (
        f"{_person(bond.user_id, bond.user_name, mention)} 今日正缘是 {wife}\n"
        f"【{bond.rarity}】{bond.title} · 契合度 {bond.affinity}\n"
        f"「{bond.flavor}」"
    )


def render_divorce(bond: WifeBond, *, mention: bool = True) -> str:
    return (
        f"{_person(bond.user_id, bond.user_name, mention)} 撕掉了和 "
        f"{_person(bond.wife_id, bond.wife_name, mention)} 的今日契约。\n"
        "户口本已恢复空白，可以重新「抽老婆」。"
    )


def render_no_wife() -> str:
    return "你今天还没有老婆。先「抽老婆」，再来秀恩爱。"


def render_no_candidates() -> str:
    return "群里暂时没有可抽取的成员。检查一下是不是人都被排除了，或者只剩你和机器人。"


def render_private_chat() -> str:
    return "抽老婆是群聊玩法，私聊里没有群友可抽。"


def render_group_roster(bonds: list[WifeBond]) -> str:
    if not bonds:
        return "本群今天还没有姻缘记录。来个人先「抽老婆」开张。"
    lines = [f"本群今日花名册（{len(bonds)} 对）："]
    for index, bond in enumerate(bonds, start=1):
        lines.append(
            f"{index}. {bond.user_name} → {bond.wife_name} 【{bond.rarity}·{bond.title}】 {bond.affinity}"
        )
    return "\n".join(lines)


def render_prompt(bonds: list[WifeBond], limit: int = 8) -> str:
    if not bonds:
        return ""
    shown = bonds[:limit]
    lines = [f"本群今日姻缘（{len(bonds)} 对，供你接梗，不要重复完整姻缘签）："]
    for bond in shown:
        lines.append(f"- {bond.user_name} → {bond.wife_name}【{bond.rarity}·{bond.title}】")
    if len(bonds) > limit:
        lines.append(f"- ……还有 {len(bonds) - limit} 对未列出")
    return "\n".join(lines)


def render_help() -> str:
    return "\n".join(
        [
            "抽老婆 · 命运签",
            "从当前 QQ 群成员中抽取今日正缘，带稀有度、称号和契合度。",
            "",
            "指令：",
            "抽老婆 / 今日老婆 — 抽取今日正缘（每人每天锁定一次）",
            "我的老婆 — 查看自己的今日正缘",
            "离婚 — 解除今日绑定后可再抽",
            "本群姻缘 — 今日花名册",
            "抽老婆帮助 — 查看本说明",
            "重置姻缘 — 超级用户清空本群今日记录",
            "",
            "默认排除机器人、你自己，以及配置里的黑名单。",
        ]
    )


def render_result_for_agent(result_text: str) -> str:
    return result_text
