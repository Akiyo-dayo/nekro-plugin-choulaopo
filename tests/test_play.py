import asyncio
from datetime import datetime

from choulaopo.members import GroupMember
from choulaopo.models import DrawConfig, PlayKind
from choulaopo.service import DrawService, MemoryStateStore


def _members() -> list[GroupMember]:
    return [
        GroupMember("10", "甲"),
        GroupMember("20", "乙"),
        GroupMember("30", "丙"),
        GroupMember("40", "丁"),
    ]


def _service() -> DrawService:
    return DrawService(
        store=MemoryStateStore(),
        rng_factory=lambda: __import__("random").Random(1),
        clock=lambda: datetime(2026, 8, 20, 12, 0, 0),
    )


def _bind(service: DrawService, user_id: str, user_name: str, wife_id: str) -> None:
    async def _run():
        return await service.draw(
            "g",
            user_id,
            user_name,
            _members(),
            "1",
            DrawConfig(),
            forced_wife_id=wife_id,
        )

    result = asyncio.run(_run())
    assert result.bond is not None


def test_steal_success_takes_owned_wife_and_dumps_old():
    service = _service()
    _bind(service, "10", "甲", "20")
    _bind(service, "30", "丙", "40")

    async def _run():
        return await service.steal("g", "10", "甲", "40", "丁", forced_success=True)

    result = asyncio.run(_run())
    assert result.kind == PlayKind.STEAL_SUCCESS
    assert result.victim_id == "30"
    assert result.dumped_bond is not None and result.dumped_bond.wife_id == "20"
    assert asyncio.run(service.get_bond("g", "10")).wife_id == "40"
    assert asyncio.run(service.get_bond("g", "30")) is None


def test_steal_fail_and_protect_block():
    service = _service()
    _bind(service, "30", "丙", "40")

    async def _run():
        fail = await service.steal("g", "10", "甲", "40", "丁", forced_success=False)
        await service.protect("g", "30")
        blocked = await service.steal("g", "10", "甲", "40", "丁", forced_success=True)
        return fail, blocked

    fail, blocked = asyncio.run(_run())
    assert fail.kind == PlayKind.STEAL_FAIL
    assert blocked.kind == PlayKind.STEAL_PROTECTED
    assert asyncio.run(service.get_bond("g", "30")).wife_id == "40"


def test_gift_and_swap_and_pet_and_remarry():
    service = _service()
    _bind(service, "10", "甲", "20")
    _bind(service, "30", "丙", "40")

    async def _run():
        pet = await service.pet("g", "10")
        swapped = await service.swap("g", "10", "甲", "30", "丙")
        await service.divorce("g", "10")
        remarried = await service.remarry("g", "10", "甲")
        gifted = await service.gift("g", "10", "甲", "30", "丙")
        return gifted, swapped, pet, remarried

    gifted, swapped, pet, remarried = asyncio.run(_run())
    assert pet.kind == PlayKind.PET_SUCCESS
    assert pet.affinity_gain >= 1
    assert swapped.kind == PlayKind.SWAP_SUCCESS
    assert remarried.kind == PlayKind.REMARRY_SUCCESS
    assert gifted.kind == PlayKind.GIFT_SUCCESS


def test_steal_self_and_already_yours():
    service = _service()
    _bind(service, "10", "甲", "20")

    async def _run():
        self_hit = await service.steal("g", "10", "甲", "10", "甲", forced_success=True)
        mine = await service.steal("g", "10", "甲", "20", "乙", forced_success=True)
        return self_hit, mine

    self_hit, mine = asyncio.run(_run())
    assert self_hit.kind == PlayKind.STEAL_SELF
    assert mine.kind == PlayKind.STEAL_ALREADY_YOURS


def test_boards_track_affinity_and_scum():
    service = _service()
    _bind(service, "10", "甲", "20")
    _bind(service, "30", "丙", "40")
    asyncio.run(service.steal("g", "10", "甲", "40", "丁", forced_success=True))
    boards = asyncio.run(service.boards("g"))
    assert boards["love"]
    assert any(row[0] == "甲" for row in boards["scum"])
    assert any(row[0] == "丙" for row in boards["unlucky"])


def test_claim_unbound_and_household():
    service = _service()

    async def _run():
        claimed = await service.steal("g", "10", "甲", "20", "乙", forced_success=True)
        info = await service.household("g", "20", "乙")
        return claimed, info

    claimed, info = asyncio.run(_run())
    assert claimed.kind == PlayKind.STEAL_SUCCESS
    assert claimed.victim_id is None
    assert info.as_wife_of is not None
    assert info.as_wife_of.user_id == "10"
