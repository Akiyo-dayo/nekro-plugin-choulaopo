from __future__ import annotations

import random

from .models import FortuneSlip

RARITY_WEIGHTS: dict[str, int] = {
    "普通": 70,
    "稀有": 22,
    "传说": 7,
    "天命": 1,
}

_AFFINITY_RANGE: dict[str, tuple[int, int]] = {
    "普通": (1, 60),
    "稀有": (50, 85),
    "传说": (75, 98),
    "天命": (90, 100),
}

_TITLES: dict[str, tuple[str, ...]] = {
    "普通": ("普通群友", "路人缘", "今日过客", "群里的那个谁", "同事以上朋友未满"),
    "稀有": ("青梅竹马", "欢喜冤家", "契约结婚", "死对头转正", "深夜网友"),
    "传说": ("命定之人", "霸总本尊", "傲娇本命", "白月光本体", "天降系"),
    "天命": ("天作之合", "红线绑定", "系统强制结婚", "唯一指定老婆", "世界第一可爱"),
}

_FLAVORS: dict[str, tuple[str, ...]] = {
    "普通": (
        "缘分浅浅一层，但也够今天互相整蛊了。",
        "群里随手一捞，捞到了今天的剧情NPC。",
        "不算轰轰烈烈，但足够让群友起哄一整晚。",
    ),
    "稀有": (
        "你们大概在群里对过线，现在正式升级为今日家属。",
        "欢喜冤家也是缘，先吵两句再牵手。",
        "契约生效：今天要互相给对方撑场面。",
    ),
    "传说": (
        "红线在你们手指上打了个死结，解开算你赢。",
        "群里的空气突然变得像偶像剧片尾。",
        "这种契合度，建议直接走剧情杀。",
    ),
    "天命": (
        "系统提示：检测到世界线收束，禁止反悔。",
        "不是抽到的，是命里写好必须相遇。",
        "今日老婆已加锁，钥匙在对方口袋里。",
    ),
}


_STEAL_BASE: dict[str, int] = {
    "普通": 58,
    "稀有": 38,
    "传说": 20,
    "天命": 8,
}


def steal_success_chance(rarity: str, affinity: int, protected: bool = False) -> int:
    if protected:
        return 0
    base = _STEAL_BASE.get(rarity, 40)
    affinity = max(0, min(100, int(affinity)))
    chance = int(base * (1 - affinity / 180.0))
    return max(5, min(100, chance))


def roll_slip(rng: random.Random | None = None) -> FortuneSlip:
    rng = rng or random.Random()
    rarity = rng.choices(list(RARITY_WEIGHTS.keys()), weights=list(RARITY_WEIGHTS.values()), k=1)[0]
    low, high = _AFFINITY_RANGE[rarity]
    return FortuneSlip(
        rarity=rarity,
        title=rng.choice(_TITLES[rarity]),
        affinity=rng.randint(low, high),
        flavor=rng.choice(_FLAVORS[rarity]),
    )
