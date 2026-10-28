"""金额展示格式。接口和存储始终使用整数分，只在展示时转换为元。"""


def format_cents(cents: int) -> str:
    """把整数分格式化为两位小数的元，例如 3334 -> "33.34"，-5 -> "-0.05"。"""
    sign = "-" if cents < 0 else ""
    yuan, fen = divmod(abs(cents), 100)
    return f"{sign}{yuan}.{fen:02d}"
