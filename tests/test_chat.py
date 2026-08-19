import pytest

from choulaopo.chat import is_group_chat, parse_group_id


def test_parse_group_id_from_chat_key():
    assert parse_group_id("onebot_v11-group_12345678") == "12345678"


def test_parse_group_id_from_channel_id_prefixed():
    assert parse_group_id("onebot_v11-group_1", channel_id="group_87654321") == "87654321"


def test_parse_group_id_from_numeric_channel_id():
    assert parse_group_id("onebot_v11-group_1", channel_id="10001") == "10001"


def test_parse_group_id_rejects_private_chat():
    with pytest.raises(ValueError, match="群聊"):
        parse_group_id("onebot_v11-private_10001")


def test_is_group_chat_by_channel_type():
    assert is_group_chat("onebot_v11-group_1", channel_type="group") is True
    assert is_group_chat("onebot_v11-private_1", channel_type="private") is False
