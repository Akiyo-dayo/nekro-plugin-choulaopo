import asyncio
from datetime import datetime

from choulaopo.members import GroupMember
from choulaopo.service import DrawConfig, DrawKind, DrawService, MemoryStateStore


def _members(*pairs: tuple[str, str]) -> list[GroupMember]:
    return [GroupMember(user_id=uid, name=name) for uid, name in pairs]


def _service() -> DrawService:
    return DrawService(
        store=MemoryStateStore(),
        rng_factory=lambda: __import__("random").Random(1),
        clock=lambda: datetime(2026, 8, 20, 12, 0, 0),
    )


def test_first_draw_binds_today_wife():
    service = _service()

    async def _run():
        return await service.draw(
            chat_key="onebot_v11-group_1",
            user_id="10",
            user_name="抽卡人",
            members=_members(("10", "抽卡人"), ("20", "群友A"), ("30", "群友B")),
            bot_id="1",
            config=DrawConfig(),
        )

    result = asyncio.run(_run())
    assert result.kind == DrawKind.DRAWN
    assert result.bond is not None
    assert result.bond.wife_id in {"20", "30"}
    assert result.bond.user_id == "10"


def test_second_draw_same_day_is_locked():
    service = _service()
    kwargs = dict(
        chat_key="onebot_v11-group_1",
        user_id="10",
        user_name="抽卡人",
        members=_members(("10", "抽卡人"), ("20", "群友A")),
        bot_id="1",
        config=DrawConfig(),
    )

    async def _run():
        first = await service.draw(**kwargs)
        second = await service.draw(**kwargs)
        return first, second

    first, second = asyncio.run(_run())
    assert first.kind == DrawKind.DRAWN
    assert second.kind == DrawKind.ALREADY_BOUND
    assert second.bond is not None
    assert second.bond.wife_id == first.bond.wife_id


def test_divorce_allows_redraw():
    service = _service()
    kwargs = dict(
        chat_key="onebot_v11-group_1",
        user_id="10",
        user_name="抽卡人",
        members=_members(("10", "抽卡人"), ("20", "群友A")),
        bot_id="1",
        config=DrawConfig(),
    )

    async def _run():
        await service.draw(**kwargs)
        divorced = await service.divorce(chat_key="onebot_v11-group_1", user_id="10")
        redraw = await service.draw(**kwargs)
        return divorced, redraw

    divorced, redraw = asyncio.run(_run())
    assert divorced is not None
    assert redraw.kind == DrawKind.DRAWN


def test_mutual_and_shura_flags():
    service = _service()
    members = _members(("10", "甲"), ("20", "乙"), ("30", "丙"))
    config = DrawConfig()

    async def _run():
        a = await service.draw("g", "10", "甲", members, "1", config, forced_wife_id="20")
        b = await service.draw("g", "20", "乙", members, "1", config, forced_wife_id="10")
        c = await service.draw("g", "30", "丙", members, "1", config, forced_wife_id="20")
        return a, b, c

    a, b, c = asyncio.run(_run())
    assert a.bond is not None and a.shura is False
    assert b.mutual is True
    assert c.shura is True
    assert c.shura_owner_id == "10"


def test_day_rollover_resets_bonds():
    store = MemoryStateStore()
    day = {"value": datetime(2026, 8, 20, 23, 0, 0)}
    service = DrawService(store=store, rng_factory=lambda: __import__("random").Random(1), clock=lambda: day["value"])
    members = _members(("10", "抽卡人"), ("20", "群友A"))

    async def _run():
        first = await service.draw("g", "10", "抽卡人", members, "1", DrawConfig())
        day["value"] = datetime(2026, 8, 21, 0, 5, 0)
        again = await service.draw("g", "10", "抽卡人", members, "1", DrawConfig())
        return first, again

    first, again = asyncio.run(_run())
    assert first.kind == DrawKind.DRAWN
    assert again.kind == DrawKind.DRAWN


def test_no_candidates_returns_empty():
    service = _service()

    async def _run():
        return await service.draw(
            chat_key="g",
            user_id="10",
            user_name="独苗",
            members=_members(("10", "独苗"), ("1", "机器人")),
            bot_id="1",
            config=DrawConfig(),
        )

    result = asyncio.run(_run())
    assert result.kind == DrawKind.NO_CANDIDATES
    assert result.bond is None
