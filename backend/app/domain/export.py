"""费用明细 CSV 生成。

每笔有效费用一行，列出日期、分类、说明、付款人、总额、分摊方式及各成员承担金额。
使用 UTF-8 BOM，保证 Excel 直接打开时中文不乱码。用户输入的文本若以公式字符开头，
前置单引号，防止被表格软件当作公式执行。
"""

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from app.domain.money import format_cents
from app.domain.split import SplitMethod

SPLIT_METHOD_LABELS = {
    SplitMethod.EQUAL: "均摊",
    SplitMethod.EXACT: "指定金额",
    SplitMethod.SHARES: "按份数",
}

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class ExportExpense:
    spent_on: date
    category: str
    description: str
    payer_name: str
    amount_cents: int
    split_method: SplitMethod
    shares: Mapping[int, int]


def escape_formula(text: str) -> str:
    """CSV 注入防护：以公式字符开头的文本前置单引号。"""
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def build_expense_csv(
    members: Sequence[tuple[int, str]], expenses: Sequence[ExportExpense]
) -> bytes:
    """members 为 (成员 ID, 显示名) 列表，决定成员列的顺序。返回带 BOM 的 UTF-8 字节。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["日期", "分类", "说明", "付款人", "总额（元）", "分摊方式"]
        + [f"{escape_formula(name)} 承担（元）" for _, name in members]
    )
    for expense in expenses:
        writer.writerow(
            [
                expense.spent_on.isoformat(),
                escape_formula(expense.category),
                escape_formula(expense.description),
                escape_formula(expense.payer_name),
                format_cents(expense.amount_cents),
                SPLIT_METHOD_LABELS[expense.split_method],
            ]
            + [format_cents(expense.shares.get(member_id, 0)) for member_id, _ in members]
        )
    return buffer.getvalue().encode("utf-8-sig")
