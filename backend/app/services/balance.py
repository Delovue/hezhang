"""读取活动的费用与付款流水，交给领域函数计算余额。余额不落库。"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.balance import ExpenseEntry, MemberBalance, PaymentEntry, compute_balances
from app.errors import ApiError, ErrorCode
from app.models import Expense, Membership, Payment, PaymentStatus


def member_ids(session: Session, activity_id: int) -> list[int]:
    return list(
        session.scalars(
            select(Membership.id)
            .where(Membership.activity_id == activity_id)
            .order_by(Membership.id)
        )
    )


def require_members(
    session: Session, activity_id: int, ids: Iterable[int], code: ErrorCode
) -> None:
    if not set(ids) <= set(member_ids(session, activity_id)):
        raise ApiError(422, code, "所选成员必须属于本活动")


def expense_entries(session: Session, activity_id: int) -> list[ExpenseEntry]:
    # 软删除费用的分摊仍保留用于追溯，计算时必须排除
    expenses = session.scalars(
        select(Expense)
        .where(Expense.activity_id == activity_id, Expense.is_deleted.is_(False))
        .order_by(Expense.id)
    )
    return [
        ExpenseEntry(
            payer_id=expense.payer_member_id,
            amount_cents=expense.amount_cents,
            shares={share.member_id: share.amount_cents for share in expense.shares},
            category=expense.category,
        )
        for expense in expenses
    ]


def payment_entries(session: Session, activity_id: int) -> list[PaymentEntry]:
    payments = session.scalars(
        select(Payment).where(
            Payment.activity_id == activity_id,
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.CONFIRMED]),
        )
    )
    return [
        PaymentEntry(
            payer_id=payment.payer_member_id,
            payee_id=payment.payee_member_id,
            amount_cents=payment.amount_cents,
            status=payment.status,
        )
        for payment in payments
    ]


def load_balances(session: Session, activity_id: int) -> list[MemberBalance]:
    return compute_balances(
        member_ids(session, activity_id),
        expense_entries(session, activity_id),
        payment_entries(session, activity_id),
    )
