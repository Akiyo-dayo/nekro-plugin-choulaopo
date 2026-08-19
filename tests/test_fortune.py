import random

from choulaopo.fortune import RARITY_WEIGHTS, FortuneSlip, roll_slip


def test_roll_slip_is_deterministic_with_seed():
    first = roll_slip(random.Random(42))
    second = roll_slip(random.Random(42))
    assert first == second
    assert isinstance(first, FortuneSlip)
    assert first.rarity in RARITY_WEIGHTS
    assert 1 <= first.affinity <= 100
    assert first.title
    assert first.flavor


def test_destiny_rarity_has_high_affinity():
    rng = random.Random(7)
    destines = [roll_slip(rng) for _ in range(4000)]
    destiny = [s for s in destines if s.rarity == "天命"]
    assert destiny, "seeded rolls should hit 天命 at least once"
    assert all(s.affinity >= 90 for s in destiny)
