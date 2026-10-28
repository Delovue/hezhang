"""预算与消费统计。

消费总额只来自有效费用，成员之间的结算付款不计入消费，
因此本模块不接收付款数据。
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.balance import ExpenseEntry


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    amount_cents: int


@dataclass(frozen=True)
class MemberShareTotal:
    member_id: int
    owed_cents: int  # 个人承担


@dataclass(frozen=True)
class ActivityStatistics:
    total_spent_cents: int
    budget_cents: int | None
    remaining_budget_cents: int | None  # 超预算时为负数
    over_budget: bool
    by_category: list[CategoryTotal]  # 金额降序，金额相同按分类名升序
    by_member: list[MemberShareTotal]  # 成员 ID 升序


def compute_statistics(
    member_ids: Sequence[int],
    expenses: Sequence[ExpenseEntry],
    budget_cents: int | None,
) -> ActivityStatistics:
    """budget_cents 为 None 表示未设置预算，此时不判断是否超预算。"""
    total = sum(e.amount_cents for e in expenses)

    categories: dict[str, int] = defaultdict(int)
    owed = {member_id: 0 for member_id in member_ids}
    for expense in expenses:
        categories[expense.category] += expense.amount_cents
        for member_id, share in expense.shares.items():
            owed[member_id] += share

    remaining = None if budget_cents is None else budget_cents - total
    return ActivityStatistics(
        total_spent_cents=total,
        budget_cents=budget_cents,
        remaining_budget_cents=remaining,
        over_budget=remaining is not None and remaining < 0,
        by_category=[
            CategoryTotal(name, amount)
            for name, amount in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        by_member=[MemberShareTotal(m, owed[m]) for m in sorted(owed)],
    )
