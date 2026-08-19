"""NekroAgent 抽老婆插件入口。"""

from __future__ import annotations

from typing import List

from pydantic import Field

from nekro_agent.api import core, i18n
from nekro_agent.api.plugin import (
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
from nekro_agent.services.command.schemas import CommandOutputSegment, CommandOutputSegmentType

from .chat import is_group_chat, parse_group_id
from .members import coerce_member_list, parse_members
from .models import DrawConfig, DrawKind, DrawResult
from .render import (
    avatar_url,
    render_already_bound,
    render_divorce,
    render_drawn,
    render_group_roster,
    render_help,
    render_my_wife,
    render_no_candidates,
    render_no_wife,
    render_private_chat,
    render_prompt,
)
from .service import DrawService
from .store import STORE_KEY

plugin = NekroPlugin(
    name="抽老婆",
    module_name="choulaopo",
    description="从当前 QQ 群成员中抽取今日老婆，附带姻缘签、稀有度、契合度和趣味文案。",
    version="1.0.0",
    author="Akiyo",
    url="https://github.com/Akiyo-dayo/nekro-plugin-choulaopo",
    support_adapter=["onebot_v11"],
    allow_sleep=True,
    sleep_brief="用于抽取群友作为今日老婆、查看姻缘或离婚，仅在有人玩抽老婆时激活。",
    i18n_name=i18n.i18n_text(zh_CN="抽老婆", en_US="Draw Wife"),
    i18n_description=i18n.i18n_text(
        zh_CN="从当前 QQ 群成员中抽取今日老婆，附带姻缘签、稀有度、契合度和趣味文案。",
        en_US="Draw a random group member as today's wife with a fortune slip.",
    ),
)


@plugin.mount_config()
class ChoulaopoConfig(ConfigBase):
    """抽老婆配置"""

    EXCLUDE_SELF: bool = Field(default=True, title="排除自己", description="抽取时是否把自己排除出候选")
    EXCLUDE_BOT: bool = Field(default=True, title="排除机器人", description="抽取时是否排除机器人自己")
    MENTION_WIFE: bool = Field(default=True, title="@ 被抽中的人", description="结果文案中是否 @ 正缘")
    SHOW_AVATAR: bool = Field(default=True, title="发送头像", description="抽取成功时是否发送 QQ 头像")
    EXCLUDED_USERS: List[str] = Field(
        default_factory=list,
        title="黑名单 QQ",
        description="这些 QQ 号不会被抽中",
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
    )


def _unsupported_reason(adapter_key: str | None, chat_key: str, channel_id: str | None = None, channel_type: str | None = None) -> str | None:
    if adapter_key and adapter_key != "onebot_v11":
        return "抽老婆仅支持 QQ OneBot 群聊"
    if not is_group_chat(chat_key, channel_id=channel_id, channel_type=channel_type):
        return render_private_chat()
    return None


async def _fetch_members(ctx: AgentCtx) -> tuple[str, list]:
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


@plugin.mount_command(
    name="choulaopo",
    description="抽取今日老婆",
    aliases=["抽老婆", "今日老婆"],
    permission=CommandPermission.PUBLIC,
    usage="choulaopo",
    category="抽老婆",
    tags=["wife", "fun", "group"],
)
async def choulaopo_cmd(context: CommandExecutionContext) -> CommandResponse:
    reason = _unsupported_reason(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
    ctx = await AgentCtx.create_by_chat_key(context.chat_key)
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
    reason = _unsupported_reason(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
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
    reason = _unsupported_reason(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
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
    reason = _unsupported_reason(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
    bonds = await get_service().list_bonds(context.chat_key)
    return CmdCtl.success(render_group_roster(bonds))


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
    reason = _unsupported_reason(context.adapter_key, context.chat_key)
    if reason:
        return CmdCtl.failed(reason)
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
    drawer_id = str(user_qq or _ctx.from_platform_userid or "").strip()
    if not drawer_id:
        raise ValueError("无法确定抽取者 QQ，请传入 user_qq")
    try:
        bot_id, members = await _fetch_members(_ctx)
    except Exception as exc:
        core.logger.exception("获取群成员失败")
        raise ValueError(f"获取群成员失败: {exc}") from exc
    drawer_name = next((item.name for item in members if item.user_id == drawer_id), drawer_id)
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
    user_id = str(user_qq or _ctx.from_platform_userid or "").strip()
    if not user_id:
        raise ValueError("无法确定查询对象 QQ，请传入 user_qq")
    bond = await get_service().get_bond(_ctx.chat_key, user_id)
    if bond is None:
        return "today_wife=none"
    return (
        f"today_wife={bond.wife_name}({bond.wife_id})\n"
        f"rarity={bond.rarity}\n"
        f"title={bond.title}\n"
        f"affinity={bond.affinity}"
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
    user_id = str(user_qq or _ctx.from_platform_userid or "").strip()
    if not user_id:
        raise ValueError("无法确定离婚对象 QQ，请传入 user_qq")
    bond = await get_service().divorce(_ctx.chat_key, user_id)
    if bond is None:
        raise ValueError(render_no_wife())
    await _ctx.send_text(render_divorce(bond, mention=config.MENTION_WIFE), record=True)
    return "ok"


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
    return [draw_wife, query_wife, divorce_wife]


@plugin.mount_cleanup_method()
async def clean_up():
    global _service
    _service = None
    core.logger.info("抽老婆插件资源已清理")
