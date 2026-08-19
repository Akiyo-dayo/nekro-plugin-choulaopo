from __future__ import annotations

from .models import Household, PlayKind, PlayResult, WifeBond

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
    lock = "（今日已加锁保护）" if bond.protected else ""
    return (
        f"{_person(bond.user_id, bond.user_name, mention)} 今日正缘是 {wife}{lock}\n"
        f"【{bond.rarity}】{bond.title} · 契合度 {bond.affinity}\n"
        f"「{bond.flavor}」"
    )


def render_divorce(bond: WifeBond, *, mention: bool = True) -> str:
    return (
        f"{_person(bond.user_id, bond.user_name, mention)} 撕掉了和 "
        f"{_person(bond.wife_id, bond.wife_name, mention)} 的今日契约。\n"
        "户口本已恢复空白。可以重新「抽老婆」，或对前任打「复婚」。"
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
        lock = "🔒" if bond.protected else ""
        lines.append(
            f"{index}. {bond.user_name} → {bond.wife_name}{lock} 【{bond.rarity}·{bond.title}】 {bond.affinity}"
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


def render_need_target(action: str) -> str:
    return f"请 @ 一个群友，例如：{action} @对方"


def render_household(info: Household, *, mention: bool = True) -> str:
    who = _person(info.target_id, info.target_name, mention)
    lines = [f"查户口：{who}"]
    if info.as_husband is None and info.as_wife_of is None:
        lines.append("户口空白，今日单身贵族。可以「抽老婆」入户，也可以被别人「强娶」。")
        return "\n".join(lines)
    if info.as_husband is not None:
        wife = _person(info.as_husband.wife_id, info.as_husband.wife_name, mention)
        lock = "，已开启保护" if info.as_husband.protected else ""
        lines.append(
            f"名下正缘：{wife} 【{info.as_husband.rarity}·{info.as_husband.title}】契合度 {info.as_husband.affinity}{lock}"
        )
    if info.as_wife_of is not None:
        owner = _person(info.as_wife_of.user_id, info.as_wife_of.user_name, mention)
        lines.append(f"被登记为 {owner} 的今日正缘。")
    if info.as_husband is not None and info.as_wife_of is not None:
        lines.append("结论：既当别人的正缘，自己又另有所属。修罗场材料齐全。")
    return "\n".join(lines)


def render_boards(boards: dict[str, list[tuple[str, int]]]) -> str:
    love = boards.get("love") or []
    scum = boards.get("scum") or []
    unlucky = boards.get("unlucky") or []
    if not love and not scum and not unlucky:
        return "榜单空空。先「抽老婆」，再「宠老婆」或「抢老婆」，榜才有人上。"
    lines = ["本群今日姻缘榜"]
    lines.append("【恩爱榜】契合度")
    if love:
        for index, (name, score) in enumerate(love, start=1):
            lines.append(f"{index}. {name} · {score}")
    else:
        lines.append("暂无")
    lines.append("【渣男榜】抢婚 + 离婚")
    if scum:
        for index, (name, score) in enumerate(scum, start=1):
            lines.append(f"{index}. {name} · {score} 次")
    else:
        lines.append("暂无，难得群风淳朴。")
    lines.append("【倒霉榜】正缘被抢走")
    if unlucky:
        for index, (name, score) in enumerate(unlucky, start=1):
            lines.append(f"{index}. {name} · 被抢 {score} 次")
    else:
        lines.append("暂无，大家都还守得住。")
    return "\n".join(lines)


def render_play(result: PlayResult, *, mention: bool = True) -> str:
    kind = result.kind
    bond = result.bond
    if kind == PlayKind.STEAL_SELF:
        return "自己抢自己？这叫自我攻略，系统不认。"
    if kind == PlayKind.STEAL_ALREADY_YOURS and bond:
        return f"{_person(bond.wife_id, bond.wife_name, mention)} 已经是你的今日正缘了。再抢就变成当众秀恩爱。"
    if kind == PlayKind.STEAL_LIMIT:
        return "今天抢婚次数用完了。给群友一点活路，也给你的膝盖一点休息。"
    if kind == PlayKind.STEAL_PROTECTED and bond:
        owner = _person(bond.user_id, bond.user_name, mention)
        wife = _person(bond.wife_id, bond.wife_name, mention)
        return f"失败。{owner} 今天给 {wife} 上了保护，红线暂时剪不断。"
    if kind == PlayKind.STEAL_FAIL:
        extra = f"成功率大约 {result.chance}%。" if result.chance else ""
        if result.victim_name:
            return f"抢婚失败。{result.victim_name} 把人护得太紧，你空手而归。{extra}".strip()
        return f"强娶失败。对方今天不想入你的户口。{extra}".strip()
    if kind == PlayKind.STEAL_REVERSE and result.dumped_bond:
        lost = _person(result.dumped_bond.wife_id, result.dumped_bond.wife_name, mention)
        return (
            f"抢婚失败，还触发了【反噬】！\n"
            f"你的正缘 {lost} 嫌你丢人，当场撕了契约跑路。\n"
            "这就是报应，建议先回家反省。"
        )
    if kind == PlayKind.STEAL_SUCCESS and bond:
        wife = _person(bond.wife_id, bond.wife_name, mention)
        lines = [
            f"{_person(bond.user_id, bond.user_name, mention)} 抢婚成功！",
            f"今日正缘改判：{wife} 【{bond.rarity}·{bond.title}】契合度 {bond.affinity}",
        ]
        if result.victim_name:
            lines.append(f"{result.victim_name} 的正缘被横刀夺爱了，建议围观时小声一点。")
        else:
            lines.append("这是一场成功的强娶，户口本已盖章。")
        if result.dumped_bond:
            dumped = _person(result.dumped_bond.wife_id, result.dumped_bond.wife_name, mention)
            lines.append(f"喜新厌旧现场：前任 {dumped} 已被自动移出今日名单。")
        return "\n".join(lines)
    if kind == PlayKind.GIFT_SELF:
        return "把老婆送给自己？系统判定为自恋，驳回。"
    if kind == PlayKind.GIFT_NO_WIFE:
        return "你今天没有老婆可送。先抽一个，再谈慷慨。"
    if kind == PlayKind.GIFT_SUCCESS and bond:
        lines = [
            f"{_person(bond.user_id, bond.user_name, mention)} 收下了别人送来的正缘 "
            f"{_person(bond.wife_id, bond.wife_name, mention)}。",
            f"【{bond.rarity}】{bond.title} · 契合度 {bond.affinity}",
        ]
        if result.dumped_bond:
            dumped = _person(result.dumped_bond.wife_id, result.dumped_bond.wife_name, mention)
            lines.append(f"原配 {dumped} 被这份礼物挤出了今日剧本，修罗场+1。")
        return "\n".join(lines)
    if kind == PlayKind.SWAP_SELF:
        return "自己和自己换妻，这叫原地转圈。"
    if kind == PlayKind.SWAP_NEED_BOTH:
        return "换妻需要双方都有今日正缘。缺一边就先去抽，别空手套白狼。"
    if kind == PlayKind.SWAP_SUCCESS and bond and result.other_bond:
        other = result.other_bond
        return (
            "换妻成功，户口本对调完毕。\n"
            f"{_person(bond.user_id, bond.user_name, mention)} 现在的正缘是 "
            f"{_person(bond.wife_id, bond.wife_name, mention)}。\n"
            f"{_person(other.user_id, other.user_name, mention)} 现在的正缘是 "
            f"{_person(other.wife_id, other.wife_name, mention)}。\n"
            "群友可以开始重新站队了。"
        )
    if kind == PlayKind.PROTECT_NO_WIFE:
        return "没有老婆保护什么？先「抽老婆」。"
    if kind == PlayKind.PROTECT_ALREADY and bond:
        return f"今天已经给 {_person(bond.wife_id, bond.wife_name, mention)} 上过锁了。一天一次，别把人锁成保险箱。"
    if kind == PlayKind.PROTECT_SUCCESS and bond:
        return (
            f"{_person(bond.user_id, bond.user_name, mention)} 为 "
            f"{_person(bond.wife_id, bond.wife_name, mention)} 开启今日保护。\n"
            "抢婚申请一律驳回，直到明天刷新。"
        )
    if kind == PlayKind.PET_NO_WIFE:
        return "空气不能贴贴。先「抽老婆」。"
    if kind == PlayKind.PET_LIMIT and bond:
        return f"今天已经把 {_person(bond.wife_id, bond.wife_name, mention)} 宠够了。留点额度给明天。"
    if kind == PlayKind.PET_SUCCESS and bond:
        mood = "甜度超标，建议公开处刑。" if bond.affinity >= 90 else "关系又近了一点。"
        return (
            f"{_person(bond.user_id, bond.user_name, mention)} 贴了贴 "
            f"{_person(bond.wife_id, bond.wife_name, mention)}。\n"
            f"契合度 +{result.affinity_gain}，当前 {bond.affinity}。{mood}"
        )
    if kind == PlayKind.REMARRY_HAS_WIFE and bond:
        return f"你还有 {_person(bond.wife_id, bond.wife_name, mention)}，复婚会变成重婚。先离婚。"
    if kind == PlayKind.REMARRY_NONE:
        return "户口上没有前任。没离过婚，也没被抢走，复什么婚？"
    if kind == PlayKind.REMARRY_TAKEN:
        who = result.victim_name or "别人"
        return f"前任已经在 {who} 名下。人走茶凉，今天复合失败。"
    if kind == PlayKind.REMARRY_SUCCESS and bond:
        return (
            f"{_person(bond.user_id, bond.user_name, mention)} 和 "
            f"{_person(bond.wife_id, bond.wife_name, mention)} 复婚成功。\n"
            f"【{bond.rarity}】{bond.title} · 契合度 {bond.affinity}\n"
            "旧情复燃，群里可以改口叫嫂子了。"
        )
    return "系统卡住了，这步操作没有对应文案。"


def render_help() -> str:
    return "\n".join(
        [
            "抽老婆 · 命运签",
            "从当前 QQ 群成员中抽取今日正缘，还能抢、送、换、宠、保护。",
            "",
            "指令：",
            "抽老婆 / 今日老婆 / 抽老公 — 抽取今日正缘（每人每天锁定一次）",
            "我的老婆 — 查看自己的今日正缘",
            "离婚 — 解除今日绑定后可再抽",
            "复婚 — 找回今天刚离/刚被抢走且仍空窗的前任",
            "抢老婆 @某人 — 抢对方当正缘；已有主则拼概率，保护中必失败",
            "送老婆 @某人 — 把你的正缘过户给对方（对方原配会被挤走）",
            "换妻 @某人 — 双方都有正缘时互换",
            "保护老婆 — 今日正缘免疫被抢（每天一次）",
            "宠老婆 / 贴贴 — 加契合度，上恩爱榜",
            "查户口 @某人 — 看对方是谁的正缘、自己又绑了谁",
            "姻缘榜 / 恩爱榜 / 渣男榜 — 契合度、抢婚离婚、被抢次数",
            "本群姻缘 — 今日花名册",
            "抽老婆帮助 — 查看本说明",
            "重置姻缘 — 超级用户清空本群今日记录",
            "",
            "稀有度越高、契合度越高越难抢。抢失败有小概率【反噬】：你的正缘嫌你丢人先跑了。",
            "默认排除机器人、你自己，以及配置里的黑名单。",
        ]
    )


def render_result_for_agent(result_text: str) -> str:
    return result_text


def play_avatar_id(result: PlayResult) -> str | None:
    if result.kind in {PlayKind.STEAL_SUCCESS, PlayKind.GIFT_SUCCESS, PlayKind.SWAP_SUCCESS, PlayKind.REMARRY_SUCCESS} and result.bond:
        return result.bond.wife_id
    return None
