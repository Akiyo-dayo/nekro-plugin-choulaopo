"""NekroAgent 抽老婆插件入口。"""

from __future__ import annotations

from typing import Annotated, List

from pydantic import Field

from nekro_agent.api import core, i18n
from nekro_agent.api.plugin import (
    Arg,
    CmdCtl,
    CommandExecutionContext,
    CommandPermission,
    CommandResponse,
    ConfigBase,
    ExtraField,
    NekroPlugin,
    SandboxMethodType,
)
from nekro_agent.api.schemas import AgentCtx

try:
    from nekro_agent.api.plugin import CommandOutputSegment, CommandOutputSegmentType
except ImportError:  # 原版 NA 未从 api.plugin 再导出这两项
    from nekro_agent.services.command.schemas import CommandOutputSegment, CommandOutputSegmentType

from .chat import is_group_chat, parse_group_id, parse_target_user
from .members import GroupMember, coerce_member_list, parse_members
from .models import DrawConfig, DrawKind, DrawResult, PlayResult
from .render import (
    avatar_url,
    play_avatar_id,
    render_already_bound,
    render_boards,
    render_divorce,
    render_drawn,
    render_group_roster,
    render_help,
    render_household,
    render_my_wife,
    render_need_target,
    render_no_candidates,
    render_no_wife,
    render_play,
    render_private_chat,
    render_prompt,
)
from .service import DrawService
from .store import STORE_KEY

plugin = NekroPlugin(
    name="抽老婆",
    module_name="choulaopo",
    description="从当前 QQ 群成员中抽取今日老婆，支持抢、送、换、宠、保护和复婚。",
    version="1.1.1",
    author="Akiyo",
    url="https://github.com/Akiyo-dayo/nekro-plugin-choulaopo",
    support_adapter=["onebot_v11"],
    allow_sleep=True,
    sleep_brief="用于抽取、抢送换宠今日老婆等群互动，仅在有人玩抽老婆时激活。",
    i18n_name=i18n.i18n_text(zh_CN="抽老婆", en_US="Draw Wife"),
    i18n_description=i18n.i18n_text(
        zh_CN="从当前 QQ 群成员中抽取今日老婆，支持抢、送、换、宠、保护和复婚。",
        en_US="Draw a random group member as today's wife, with steal/gift/swap minigames.",
    ),
)


@plugin.mount_config()
class ChoulaopoConfig(ConfigBase):
    """抽老婆配置"""

    EXCLUDE_SELF: bool = Field(default=True, title="排除自己", description="抽取时是否把自己排除出候选")
    EXCLUDE_BOT: bool = Field(default=True, title="排除机器人", description="抽取时是否排除机器人自己")
    MENTION_WIFE: bool = Field(default=True, title="@ 被抽中的人", description="结果文案中是否 @ 正缘")
    SHOW_AVATAR: bool = Field(default=True, title="发送头像", description="抽取成功时是否发送 QQ 头像")
    STEAL_DAILY_LIMIT: int = Field(default=3, title="每日抢婚次数", description="每人每天最多尝试抢老婆的次数")
    PET_DAILY_LIMIT: int = Field(default=5, title="每日宠爱次数", description="每人每天最多贴贴/宠老婆的次数")
    EXCLUDED_USERS: List[str] = Field(
        default_factory=list,
        title="黑名单 QQ",
        description="这些 QQ 号不会被抽中，也不能被抢",
        json_schema_extra=ExtraField(sub_item_name="QQ号").model_dump(),
    )


config = plugin.get_config(ChoulaopoConfig)
_service: DrawService | None = None


class PluginKVStore:
    async def get(self, chat_key: str, store_key: str = STORE_KEY) -> str | None:
        return await plugin.store.get(chat_key=chat_key, store_key=store_key)

    async def set(self, chat_key: str, store_key: str = STORE_KEY, value: str = "") -> None:
        await plugin.store.set(chat_key=chat_key, store_key=store_key, value=value)


def get_service() -> DrawService:
    global _service
    if _service is None:
        _service = DrawService(PluginKVStore())
    return _service


def _draw_config() -> DrawConfig:
    return DrawConfig(
        exclude_self=config.EXCLUDE_SELF,
        exclude_bot=config.EXCLUDE_BOT,
        excluded_user_ids=frozenset(str(item).strip() for item in config.EXCLUDED_USERS if str(item).strip()),
        steal_daily_limit=max(0, int(config.STEAL_DAILY_LIMIT)),
        pet_daily_limit=max(0, int(config.PET_DAILY_LIMIT)),
    )


def _unsupported_reason(adapter_key: str | None, chat_key: str, channel_id: str | None = None, channel_type: str | None = None) -> str | None:
    if adapter_key and adapter_key != "onebot_v11":
        return "抽老婆仅支持 QQ OneBot 群聊"
    if not is_group_chat(chat_key, channel_id=channel_id, channel_type=channel_type):
        return render_private_chat()
    return None


def _member_name(members: list[GroupMember], uid: str, fallback: str = "") -> str:
    for item in members:
        if item.user_id == str(uid):
            return item.name
    return fallback or str(uid)


async def _fetch_members(ctx: AgentCtx) -> tuple[str, list[GroupMember]]:
    group_id = parse_group_id(ctx.chat_key, ctx.channel_id)
    bot = await ctx.get_onebot_v11_bot()
    raw = await bot.call_api("get_group_member_list", group_id=int(group_id))
    return str(bot.self_id), parse_members(coerce_member_list(raw))


def _render_result(result: DrawResult, mention: bool) -> str:
    if result.kind == DrawKind.NO_CANDIDATES:
        return render_no_candidates()
    if result.bond is None:
        return render_no_candidates()
    if result.kind == DrawKind.ALREADY_BOUND:
        return render_already_bound(result.bond, mention=mention)
    return render_drawn(
        result.bond,
        drawer_name=result.bond.user_name,
        mutual=result.mutual,
        shura_owner_name=result.shura_owner_name,
        mention=mention,
    )


def _agent_payload(result: DrawResult) -> str:
    if result.kind == DrawKind.NO_CANDIDATES:
        raise ValueError(render_no_candidates())
    if result.bond is None:
        raise ValueError(render_no_candidates())
    bond = result.bond
    lines = [
        f"kind={result.kind.value}",
        f"user={bond.user_name}({bond.user_id})",
        f"wife={bond.wife_name}({bond.wife_id})",
        f"rarity={bond.rarity}",
        f"title={bond.title}",
        f"affinity={bond.affinity}",
        f"mutual={str(result.mutual).lower()}",
        f"shura={str(result.shura).lower()}",
        f"avatar={avatar_url(bond.wife_id)}",
        "结果已发送到群聊。请用一两句吐槽承接，不要重复完整姻缘签。",
    ]
    return "\n".join(lines)


def _play_payload(result: PlayResult) -> str:
    lines = [f"kind={result.kind.value}"]
    if result.bond:
        lines.append(f"bond={result.bond.user_name}->{result.bond.wife_name}({result.bond.wife_id}) affinity={result.bond.affinity}")
    if result.other_bond:
        lines.append(f"other={result.other_bond.user_name}->{result.other_bond.wife_name}")
    if result.dumped_bond:
        lines.append(f"dumped={result.dumped_bond.wife_name}({result.dumped_bond.wife_id})")
    if result.victim_id:
        lines.append(f"victim={result.victim_name or result.victim_id}({result.victim_id})")
    if result.affinity_gain:
        lines.append(f"affinity_gain={result.affinity_gain}")
    if result.chance:
        lines.append(f"chance={result.chance}")
    lines.append("结果已发送到群聊。请用一两句吐槽承接，不要重复完整文案。")
    return "\n".join(lines)


async def _prepare_avatar_segment(ctx: AgentCtx, qq: str) -> CommandOutputSegment | None:
    try:
        sandbox_path = await ctx.fs.mixed_forward_file(avatar_url(qq), file_name=f"wife_{qq}.jpg")
        host_path = str(ctx.fs.get_file(sandbox_path))
        return CommandOutputSegment(
            type=CommandOutputSegmentType.IMAGE,
            file_path=host_path,
            web_url=avatar_url(qq),
        )
    except Exception as exc:
        core.logger.warning(f"下载老婆头像失败: {exc}")
        return None


async def _command_output(ctx: AgentCtx, text: str, wife_id: str | None, *, with_avatar: bool) -> CommandResponse:
    segments: list[CommandOutputSegment] = [
        CommandOutputSegment(type=CommandOutputSegmentType.TEXT, text=text),
    ]
    if with_avatar and wife_id:
        image = await _prepare_avatar_segment(ctx, wife_id)
        if image is not None:
            segments.append(image)
    return CmdCtl.success(segments)


async def _sandbox_announce(ctx: AgentCtx, text: str, wife_id: str | None, *, with_avatar: bool) -> None:
    if with_avatar and wife_id:
        try:
            sandbox_path = await ctx.fs.mixed_forward_file(avatar_url(wife_id), file_name=f"wife_{wife_id}.jpg")
            await ctx.send_image(sandbox_path, record=False)
        except Exception as exc:
            core.logger.warning(f"发送老婆头像失败: {exc}")
    await ctx.send_text(text, record=True)


def _require_target(raw: str, action: str) -> tuple[str, CommandResponse | None]:
    uid = parse_target_user(raw)
    if not uid:
        return "", CmdCtl.failed(render_need_target(action))
    return uid, None


async def _begin_cmd(context: CommandExecutionContext) -> tuple[AgentCtx | None, CommandResponse | None]:
    reason = _unsupported_reason(context.adapter_key, context.chat_key)
    if reason:
        return None, CmdCtl.failed(reason)
    return await AgentCtx.create_by_chat_key(context.chat_key), None


def _sandbox_user(ctx: AgentCtx, user_qq: str, label: str) -> str:
    user_id = str(user_qq or ctx.from_platform_userid or "").strip()
    if not user_id:
        raise ValueError(f"无法确定{label} QQ，请传入 user_qq")
    return user_id


def _sandbox_target(target_qq: str, label: str) -> str:
    target_id = parse_target_user(target_qq) or str(target_qq or "").strip()
    if not target_id:
        raise ValueError(f"请传入要{label}的对象 QQ")
    return target_id


@plugin.mount_command(
    name="choulaopo",
    description="抽取今日老婆",
    aliases=["抽老婆", "今日老婆", "抽老公"],
    permission=CommandPermission.PUBLIC,
    usage="choulaopo",
    category="抽老婆",
    tags=["wife", "fun", "group"],
)
async def choulaopo_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err or ctx is None:
        return err or CmdCtl.failed(render_private_chat())
    try:
        bot_id, members = await _fetch_members(ctx)
        result = await get_service().draw(
            context.chat_key,
            context.user_id,
            context.username or context.user_id,
            members,
            bot_id,
            _draw_config(),
        )
    except Exception as exc:
        core.logger.exception("抽老婆失败")
        return CmdCtl.failed(str(exc))
    text = _render_result(result, config.MENTION_WIFE)
    wife_id = result.bond.wife_id if result.kind == DrawKind.DRAWN and result.bond else None
    return await _command_output(ctx, text, wife_id, with_avatar=config.SHOW_AVATAR and result.kind == DrawKind.DRAWN)


@plugin.mount_command(
    name="my_wife",
    description="查看今日正缘",
    aliases=["我的老婆"],
    permission=CommandPermission.PUBLIC,
    usage="my_wife",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def my_wife_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err:
        return err
    bond = await get_service().get_bond(context.chat_key, context.user_id)
    if bond is None:
        return CmdCtl.success(render_no_wife())
    return CmdCtl.success(render_my_wife(bond, mention=config.MENTION_WIFE))


@plugin.mount_command(
    name="divorce",
    description="解除今日正缘",
    aliases=["离婚"],
    permission=CommandPermission.PUBLIC,
    usage="divorce",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def divorce_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err:
        return err
    bond = await get_service().divorce(context.chat_key, context.user_id)
    if bond is None:
        return CmdCtl.success(render_no_wife())
    return CmdCtl.success(render_divorce(bond, mention=config.MENTION_WIFE))


@plugin.mount_command(
    name="group_bonds",
    description="查看本群今日姻缘花名册",
    aliases=["本群姻缘"],
    permission=CommandPermission.PUBLIC,
    usage="group_bonds",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def group_bonds_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err:
        return err
    bonds = await get_service().list_bonds(context.chat_key)
    return CmdCtl.success(render_group_roster(bonds))


@plugin.mount_command(
    name="steal_wife",
    description="抢别人当今日正缘",
    aliases=["抢老婆"],
    permission=CommandPermission.PUBLIC,
    usage="steal_wife @某人",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def steal_wife_cmd(
    context: CommandExecutionContext,
    target: Annotated[str, Arg("要抢的群友，@ 对方", positional=True, greedy=True)] = "",
) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err or ctx is None:
        return err or CmdCtl.failed(render_private_chat())
    target_id, err = _require_target(target, "抢老婆")
    if err:
        return err
    try:
        bot_id, members = await _fetch_members(ctx)
    except Exception as exc:
        core.logger.exception("获取群成员失败")
        return CmdCtl.failed(str(exc))
    if target_id == str(bot_id):
        return CmdCtl.failed("机器人不当老婆，换个活人抢。")
    if target_id in _draw_config().excluded_user_ids:
        return CmdCtl.failed("这个人在黑名单里，抢不了。")
    result = await get_service().steal(
        context.chat_key,
        context.user_id,
        context.username or context.user_id,
        target_id,
        _member_name(members, target_id),
        config=_draw_config(),
    )
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    return await _command_output(ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))


@plugin.mount_command(
    name="gift_wife",
    description="把今日正缘送给别人",
    aliases=["送老婆"],
    permission=CommandPermission.PUBLIC,
    usage="gift_wife @某人",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def gift_wife_cmd(
    context: CommandExecutionContext,
    target: Annotated[str, Arg("收礼的群友，@ 对方", positional=True, greedy=True)] = "",
) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err or ctx is None:
        return err or CmdCtl.failed(render_private_chat())
    target_id, err = _require_target(target, "送老婆")
    if err:
        return err
    try:
        _bot_id, members = await _fetch_members(ctx)
    except Exception as exc:
        core.logger.exception("获取群成员失败")
        return CmdCtl.failed(str(exc))
    result = await get_service().gift(
        context.chat_key,
        context.user_id,
        context.username or context.user_id,
        target_id,
        _member_name(members, target_id),
    )
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    return await _command_output(ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))


@plugin.mount_command(
    name="swap_wife",
    description="和别人互换今日正缘",
    aliases=["换妻"],
    permission=CommandPermission.PUBLIC,
    usage="swap_wife @某人",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def swap_wife_cmd(
    context: CommandExecutionContext,
    target: Annotated[str, Arg("换妻对象，@ 对方", positional=True, greedy=True)] = "",
) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err or ctx is None:
        return err or CmdCtl.failed(render_private_chat())
    target_id, err = _require_target(target, "换妻")
    if err:
        return err
    try:
        _bot_id, members = await _fetch_members(ctx)
    except Exception as exc:
        core.logger.exception("获取群成员失败")
        return CmdCtl.failed(str(exc))
    result = await get_service().swap(
        context.chat_key,
        context.user_id,
        context.username or context.user_id,
        target_id,
        _member_name(members, target_id),
    )
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    return await _command_output(ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))


@plugin.mount_command(
    name="protect_wife",
    description="保护今日正缘不被抢",
    aliases=["保护老婆"],
    permission=CommandPermission.PUBLIC,
    usage="protect_wife",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def protect_wife_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err:
        return err
    result = await get_service().protect(context.chat_key, context.user_id)
    return CmdCtl.success(render_play(result, mention=config.MENTION_WIFE))


@plugin.mount_command(
    name="pet_wife",
    description="宠今日正缘，增加契合度",
    aliases=["宠老婆", "贴贴"],
    permission=CommandPermission.PUBLIC,
    usage="pet_wife",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def pet_wife_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err:
        return err
    result = await get_service().pet(context.chat_key, context.user_id, _draw_config())
    return CmdCtl.success(render_play(result, mention=config.MENTION_WIFE))


@plugin.mount_command(
    name="remarry",
    description="和今日前任复婚",
    aliases=["复婚"],
    permission=CommandPermission.PUBLIC,
    usage="remarry",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def remarry_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err or ctx is None:
        return err or CmdCtl.failed(render_private_chat())
    result = await get_service().remarry(context.chat_key, context.user_id, context.username or context.user_id)
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    return await _command_output(ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))


@plugin.mount_command(
    name="household",
    description="查某人今日姻缘户口",
    aliases=["查户口"],
    permission=CommandPermission.PUBLIC,
    usage="household @某人",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def household_cmd(
    context: CommandExecutionContext,
    target: Annotated[str, Arg("要查的群友，不填则查自己", positional=True, greedy=True)] = "",
) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err or ctx is None:
        return err or CmdCtl.failed(render_private_chat())
    target_id = parse_target_user(target) or str(context.user_id)
    try:
        _bot_id, members = await _fetch_members(ctx)
    except Exception:
        members = []
    fallback = context.username if target_id == str(context.user_id) else target_id
    info = await get_service().household(context.chat_key, target_id, _member_name(members, target_id, fallback or target_id))
    return CmdCtl.success(render_household(info, mention=config.MENTION_WIFE))


@plugin.mount_command(
    name="wife_board",
    description="查看今日姻缘榜",
    aliases=["姻缘榜", "恩爱榜", "渣男榜", "倒霉榜"],
    permission=CommandPermission.PUBLIC,
    usage="wife_board",
    category="抽老婆",
    tags=["wife", "fun"],
)
async def wife_board_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err:
        return err
    boards = await get_service().boards(context.chat_key)
    return CmdCtl.success(render_boards(boards))


@plugin.mount_command(
    name="choulaopo_help",
    description="抽老婆帮助",
    aliases=["抽老婆帮助"],
    permission=CommandPermission.PUBLIC,
    usage="choulaopo_help",
    category="抽老婆",
    tags=["wife", "help"],
)
async def help_cmd(context: CommandExecutionContext) -> CommandResponse:
    return CmdCtl.success(render_help())


@plugin.mount_command(
    name="reset_bonds",
    description="重置本群今日姻缘",
    aliases=["重置姻缘"],
    permission=CommandPermission.SUPER_USER,
    usage="reset_bonds",
    category="抽老婆",
    tags=["wife", "admin"],
)
async def reset_bonds_cmd(context: CommandExecutionContext) -> CommandResponse:
    ctx, err = await _begin_cmd(context)
    if err:
        return err
    await get_service().reset(context.chat_key)
    return CmdCtl.success("本群今日姻缘已清空，可以重新开抽。")


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="抽取今日老婆",
    description="从当前 QQ 群成员中随机抽取一位作为指定用户的今日正缘，并在群里公布姻缘签。",
)
async def draw_wife(_ctx: AgentCtx, user_qq: str = "") -> str:
    """从当前群成员中抽取今日老婆，结果会直接发到群里。

    Args:
        user_qq (str): 要抽取的用户 QQ。留空则抽取当前发言者。

    Returns:
        str: 抽取结果摘要，供你用一两句吐槽承接。不要重复完整姻缘签。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    drawer_id = _sandbox_user(_ctx, user_qq, "抽取者")
    try:
        bot_id, members = await _fetch_members(_ctx)
    except Exception as exc:
        core.logger.exception("获取群成员失败")
        raise ValueError(f"获取群成员失败: {exc}") from exc
    drawer_name = _member_name(members, drawer_id, drawer_id)
    result = await get_service().draw(
        _ctx.chat_key,
        drawer_id,
        drawer_name,
        members,
        bot_id,
        _draw_config(),
    )
    text = _render_result(result, config.MENTION_WIFE)
    wife_id = result.bond.wife_id if result.kind == DrawKind.DRAWN and result.bond else None
    await _sandbox_announce(_ctx, text, wife_id, with_avatar=config.SHOW_AVATAR and result.kind == DrawKind.DRAWN)
    return _agent_payload(result)


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="查看今日老婆",
    description="查询某位群友今天抽到的正缘。",
)
async def query_wife(_ctx: AgentCtx, user_qq: str = "") -> str:
    """查询指定用户今天的正缘。

    Args:
        user_qq (str): 要查询的用户 QQ。留空则查询当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    user_id = _sandbox_user(_ctx, user_qq, "查询对象")
    bond = await get_service().get_bond(_ctx.chat_key, user_id)
    if bond is None:
        return "today_wife=none"
    return (
        f"today_wife={bond.wife_name}({bond.wife_id})\n"
        f"rarity={bond.rarity}\n"
        f"title={bond.title}\n"
        f"affinity={bond.affinity}\n"
        f"protected={str(bond.protected).lower()}"
    )


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="解除今日老婆",
    description="解除指定用户今天的正缘绑定，解除后可重新抽取。",
)
async def divorce_wife(_ctx: AgentCtx, user_qq: str = "") -> str:
    """解除指定用户的今日正缘。

    Args:
        user_qq (str): 要离婚的用户 QQ。留空则解除当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    user_id = _sandbox_user(_ctx, user_qq, "离婚对象")
    bond = await get_service().divorce(_ctx.chat_key, user_id)
    if bond is None:
        raise ValueError(render_no_wife())
    await _ctx.send_text(render_divorce(bond, mention=config.MENTION_WIFE), record=True)
    return "ok"


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="抢今日老婆",
    description="指定一位群友，尝试把对方抢成自己的今日正缘。已有主则按稀有度和契合度判定，保护中必失败。",
)
async def steal_today_wife(_ctx: AgentCtx, target_qq: str, user_qq: str = "") -> str:
    """尝试抢某人为今日正缘，结果会发到群里。

    Args:
        target_qq (str): 要抢的对象 QQ。
        user_qq (str): 抢婚发起者 QQ。留空则使用当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    actor_id = _sandbox_user(_ctx, user_qq, "抢婚发起者")
    target_id = _sandbox_target(target_qq, "抢")
    try:
        bot_id, members = await _fetch_members(_ctx)
    except Exception as exc:
        raise ValueError(f"获取群成员失败: {exc}") from exc
    if target_id == str(bot_id):
        raise ValueError("机器人不当老婆")
    result = await get_service().steal(
        _ctx.chat_key,
        actor_id,
        _member_name(members, actor_id, actor_id),
        target_id,
        _member_name(members, target_id),
        config=_draw_config(),
    )
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    await _sandbox_announce(_ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))
    return _play_payload(result)


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="送今日老婆",
    description="把发起者的今日正缘过户给指定群友。对方若已有正缘会被挤走。",
)
async def gift_today_wife(_ctx: AgentCtx, target_qq: str, user_qq: str = "") -> str:
    """把今日正缘送给别人。

    Args:
        target_qq (str): 收礼人 QQ。
        user_qq (str): 送礼人 QQ。留空则使用当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    actor_id = _sandbox_user(_ctx, user_qq, "送礼人")
    target_id = _sandbox_target(target_qq, "送")
    try:
        _bot_id, members = await _fetch_members(_ctx)
    except Exception as exc:
        raise ValueError(f"获取群成员失败: {exc}") from exc
    result = await get_service().gift(
        _ctx.chat_key,
        actor_id,
        _member_name(members, actor_id, actor_id),
        target_id,
        _member_name(members, target_id),
    )
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    await _sandbox_announce(_ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))
    return _play_payload(result)


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="交换今日老婆",
    description="让两名都有今日正缘的群友互换正缘。",
)
async def swap_today_wife(_ctx: AgentCtx, target_qq: str, user_qq: str = "") -> str:
    """互换今日正缘。

    Args:
        target_qq (str): 换妻对象 QQ。
        user_qq (str): 发起者 QQ。留空则使用当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    actor_id = _sandbox_user(_ctx, user_qq, "换妻发起者")
    target_id = _sandbox_target(target_qq, "换")
    try:
        _bot_id, members = await _fetch_members(_ctx)
    except Exception as exc:
        raise ValueError(f"获取群成员失败: {exc}") from exc
    result = await get_service().swap(
        _ctx.chat_key,
        actor_id,
        _member_name(members, actor_id, actor_id),
        target_id,
        _member_name(members, target_id),
    )
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    await _sandbox_announce(_ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))
    return _play_payload(result)


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="保护今日老婆",
    description="为指定用户的今日正缘开启抢婚免疫，每天一次。",
)
async def protect_today_wife(_ctx: AgentCtx, user_qq: str = "") -> str:
    """保护今日正缘不被抢。

    Args:
        user_qq (str): 要保护的用户 QQ。留空则保护当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    user_id = _sandbox_user(_ctx, user_qq, "保护对象")
    result = await get_service().protect(_ctx.chat_key, user_id)
    await _ctx.send_text(render_play(result, mention=config.MENTION_WIFE), record=True)
    return _play_payload(result)


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="宠今日老婆",
    description="给指定用户的今日正缘加契合度，用于贴贴、撒狗粮。",
)
async def pet_today_wife(_ctx: AgentCtx, user_qq: str = "") -> str:
    """宠今日正缘，增加契合度。

    Args:
        user_qq (str): 要宠老婆的用户 QQ。留空则使用当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    user_id = _sandbox_user(_ctx, user_qq, "宠爱对象")
    result = await get_service().pet(_ctx.chat_key, user_id, _draw_config())
    await _ctx.send_text(render_play(result, mention=config.MENTION_WIFE), record=True)
    return _play_payload(result)


@plugin.mount_sandbox_method(
    SandboxMethodType.AGENT,
    name="复婚今日老婆",
    description="让指定用户找回今天刚离或刚被抢走、且目前仍空窗的前任。",
)
async def remarry_today_wife(_ctx: AgentCtx, user_qq: str = "") -> str:
    """尝试和今日前任复婚。

    Args:
        user_qq (str): 要复婚的用户 QQ。留空则使用当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    user_id = _sandbox_user(_ctx, user_qq, "复婚对象")
    try:
        _bot_id, members = await _fetch_members(_ctx)
    except Exception:
        members = []
    result = await get_service().remarry(_ctx.chat_key, user_id, _member_name(members, user_id, user_id))
    text = render_play(result, mention=config.MENTION_WIFE)
    avatar = play_avatar_id(result)
    await _sandbox_announce(_ctx, text, avatar, with_avatar=bool(config.SHOW_AVATAR and avatar))
    return _play_payload(result)


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="查询户口",
    description="查询某位群友今天是谁的正缘、自己又绑了谁。",
)
async def query_household(_ctx: AgentCtx, target_qq: str = "") -> str:
    """查今日姻缘户口。

    Args:
        target_qq (str): 要查的 QQ。留空则查当前发言者。
    """
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    target_id = parse_target_user(target_qq) or _sandbox_user(_ctx, target_qq, "查询对象")
    try:
        _bot_id, members = await _fetch_members(_ctx)
    except Exception:
        members = []
    info = await get_service().household(_ctx.chat_key, target_id, _member_name(members, target_id))
    return (
        f"target={info.target_name}({info.target_id})\n"
        f"has_wife={info.as_husband.wife_name if info.as_husband else 'none'}\n"
        f"owned_by={info.as_wife_of.user_name if info.as_wife_of else 'none'}"
    )


@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="查看姻缘榜",
    description="查看本群今日恩爱榜、渣男榜和倒霉榜。",
)
async def query_boards(_ctx: AgentCtx) -> str:
    """返回今日姻缘榜摘要。"""
    reason = _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type)
    if reason:
        raise ValueError(reason)
    boards = await get_service().boards(_ctx.chat_key)
    parts = []
    for key in ("love", "scum", "unlucky"):
        rows = boards.get(key) or []
        text = ",".join(f"{name}:{score}" for name, score in rows) or "none"
        parts.append(f"{key}={text}")
    return "\n".join(parts)


@plugin.mount_prompt_inject_method("choulaopo_prompt")
async def choulaopo_prompt(_ctx: AgentCtx) -> str:
    try:
        if _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type):
            return ""
        bonds = await get_service().list_bonds(_ctx.chat_key)
        return render_prompt(bonds)
    except Exception as exc:
        core.logger.warning(f"抽老婆提示词注入失败: {exc}")
        return ""


@plugin.mount_collect_methods()
async def collect_available_methods(_ctx: AgentCtx):
    if _unsupported_reason(_ctx.adapter_key, _ctx.chat_key, _ctx.channel_id, _ctx.channel_type):
        return []
    return [
        draw_wife,
        query_wife,
        divorce_wife,
        steal_today_wife,
        gift_today_wife,
        swap_today_wife,
        protect_today_wife,
        pet_today_wife,
        remarry_today_wife,
        query_household,
        query_boards,
    ]


@plugin.mount_cleanup_method()
async def clean_up():
    global _service
    _service = None
    core.logger.info("抽老婆插件资源已清理")
