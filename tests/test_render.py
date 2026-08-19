from choulaopo.models import WifeBond
from choulaopo.render import (
    avatar_url,
    build_at,
    render_already_bound,
    render_drawn,
    render_group_roster,
    render_help,
    render_my_wife,
    render_prompt,
)


def _bond(**overrides) -> WifeBond:
    data = dict(
        user_id="10",
        user_name="甲",
        wife_id="20",
        wife_name="乙",
        rarity="传说",
        title="命定之人",
        affinity=96,
        flavor="红线在你们手指上打了个死结。",
        timestamp="2026-08-20T12:00:00",
    )
    data.update(overrides)
    return WifeBond(**data)


def test_avatar_and_at_markup():
    assert "dst_uin=20" in avatar_url("20")
    assert build_at("20", "乙") == "[@id:20;nickname:乙@]"


def test_render_drawn_contains_sign_and_at():
    text = render_drawn(_bond(), drawer_name="甲", mutual=False, shura_owner_name=None)
    assert "[@id:10;nickname:甲@]" in text
    assert "[@id:20;nickname:乙@]" in text
    assert "传说" in text
    assert "命定之人" in text
    assert "96" in text


def test_render_mutual_and_shura_copy():
    mutual = render_drawn(_bond(), drawer_name="甲", mutual=True, shura_owner_name=None)
    assert "天作之合" in mutual
    shura = render_drawn(_bond(), drawer_name="丙", mutual=False, shura_owner_name="甲")
    assert "修罗场" in shura or "甲" in shura


def test_render_already_bound_teases_divorce():
    text = render_already_bound(_bond())
    assert "乙" in text
    assert "离婚" in text


def test_render_roster_and_prompt_are_compact():
    bonds = [_bond(), _bond(user_id="30", user_name="丙", wife_id="40", wife_name="丁")]
    roster = render_group_roster(bonds)
    assert "甲" in roster and "乙" in roster
    prompt = render_prompt(bonds)
    assert "甲" in prompt
    assert len(prompt) < 400


def test_render_my_wife_and_help():
    text = render_my_wife(_bond())
    assert "今日正缘" in text
    assert "乙" in text
    help_text = render_help()
    assert "抽老婆" in help_text
    assert "离婚" in help_text
    assert "抢老婆" in help_text
    assert "送老婆" in help_text
    assert "换妻" in help_text
