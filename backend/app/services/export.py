"""费用明细 CSV 导出，归档后仍可导出。"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.export import ExportExpense, build_expense_csv
from app.models import Activity, Expense
from app.services.activity import list_members


def member_labels(session: Session, activity: Activity) -> list[tuple[int, str]]:
    """成员列使用显示名；显示名重复时附加成员编号以便区分。"""
    members = list_members(session, activity)
    counts = Counter(member.display_name for member in members)
    return [
        (
            member.id,
            member.display_name
            if counts[member.display_name] == 1
            else f"{member.display_name}（#{member.id}）",
        )
        for member in members
    ]


def export_expenses_csv(session: Session, activity: Activity) -> bytes:
    labels = member_labels(session, activity)
    names = dict(labels)
    expenses = session.scalars(
        select(Expense)
        .where(Expense.activity_id == activity.id, Expense.is_deleted.is_(False))
        .order_by(Expense.expense_date, Expense.id)
    )
    return build_expense_csv(
        labels,
        [
            ExportExpense(
                spent_on=expense.expense_date,
                category=expense.category,
                description=expense.title,
                payer_name=names[expense.payer_member_id],
                amount_cents=expense.amount_cents,
                split_method=expense.split_method,
                shares={share.member_id: share.amount_cents for share in expense.shares},
            )
            for expense in expenses
        ],
    )
