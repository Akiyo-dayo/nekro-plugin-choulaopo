from choulaopo.chat import parse_target_user
from choulaopo.fortune import steal_success_chance


def test_parse_target_user_from_markup_and_digits():
    assert parse_target_user("[@id:123456;nickname:乙@]") == "123456"
    assert parse_target_user("[CQ:at,qq=654321]") == "654321"
    assert parse_target_user("@10001 过来") == "10001"
    assert parse_target_user("  20002  ") == "20002"
    assert parse_target_user("") == ""
    assert parse_target_user("没有数字") == ""


def test_steal_chance_drops_with_affinity_and_protect():
    easy = steal_success_chance("普通", 1, protected=False)
    hard = steal_success_chance("普通", 100, protected=False)
    legend = steal_success_chance("天命", 90, protected=False)
    locked = steal_success_chance("普通", 1, protected=True)
    assert easy > hard
    assert legend < easy
    assert locked == 0
    assert 5 <= hard <= 100
