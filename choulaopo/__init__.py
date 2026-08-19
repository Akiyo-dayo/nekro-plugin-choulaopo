"""抽老婆（命运签）

从当前 QQ 群成员列表中随机抽取一位群友作为今日老婆。
打「抽老婆」立刻出结果；自然语言也会让 AI 调用同一套抽取逻辑。
"""

try:
    from .plugin import plugin
except ModuleNotFoundError as exc:
    if exc.name != "nekro_agent":
        raise
    plugin = None  # type: ignore[assignment]

__all__ = ["plugin"]
