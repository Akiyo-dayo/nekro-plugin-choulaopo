from choulaopo.members import GroupMember, coerce_member_list, filter_candidates, member_display_name


def test_coerce_member_list_accepts_wrapped_payloads():
    wrapped = {"data": [{"user_id": 1, "nickname": "A"}]}
    assert coerce_member_list(wrapped)[0]["user_id"] == 1
    assert coerce_member_list([{"user_id": 2}])[0]["user_id"] == 2


def test_member_display_name_prefers_card():
    assert member_display_name({"user_id": 1, "card": "群名片", "nickname": "昵称"}) == "群名片"
    assert member_display_name({"user_id": 1, "card": "  ", "nickname": "昵称"}) == "昵称"
    assert member_display_name({"user_id": 42}) == "用户(42)"


def test_filter_candidates_excludes_self_bot_and_blacklist():
    members = [
        GroupMember(user_id="1", name="自己"),
        GroupMember(user_id="2", name="机器人"),
        GroupMember(user_id="3", name="黑名单"),
        GroupMember(user_id="4", name="可抽"),
    ]
    result = filter_candidates(
        members,
        drawer_id="1",
        bot_id="2",
        excluded_user_ids={"3"},
        exclude_self=True,
        exclude_bot=True,
    )
    assert [m.user_id for m in result] == ["4"]


def test_filter_candidates_can_keep_self_when_configured():
    members = [GroupMember(user_id="1", name="自己"), GroupMember(user_id="4", name="可抽")]
    result = filter_candidates(
        members,
        drawer_id="1",
        bot_id="9",
        excluded_user_ids=set(),
        exclude_self=False,
        exclude_bot=True,
    )
    assert {m.user_id for m in result} == {"1", "4"}
