from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.split import calculate_split
from app.models import Expense, ExpenseShare, Membership, User
from app.schemas import ExpenseCreate, ExpenseRead
from app.services.activity import require_active, require_activity
from app.services.audit import record_audit


def require_expense(session: Session, activity_id: int, expense_id: int) -> Expense:
    expense = session.scalar(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.activity_id == activity_id,
            Expense.is_deleted.is_(False),
        )
    )
    if expense is None:
        raise HTTPException(404, "费用不存在")
    return expense


def validate_members(session: Session, activity_id: int, data: ExpenseCreate) -> None:
    member_ids = {item.member_id for item in data.participants} | {data.payer_member_id}
    found = set(
        session.scalars(
            select(Membership.id).where(
                Membership.activity_id == activity_id, Membership.id.in_(member_ids)
            )
        ).all()
    )
    if found != member_ids:
        raise HTTPException(422, "付款人与所有分摊成员必须属于本活动")


def expense_snapshot(expense: Expense) -> dict:
    result = ExpenseRead.model_validate(expense).model_dump(mode="json")
    result["is_deleted"] = expense.is_deleted
    return result


def attach_shares(expense: Expense, data: ExpenseCreate) -> None:
    expense.shares = [
        ExpenseShare(activity_id=expense.activity_id, **item.model_dump())
        for item in calculate_split(data)
    ]


def create_expense(session: Session, activity_id: int, user: User, data: ExpenseCreate) -> Expense:
    activity = require_activity(session, activity_id, user.id)
    require_active(activity)
    validate_members(session, activity_id, data)
    expense = Expense(
        activity_id=activity_id,
        created_by_id=user.id,
        **data.model_dump(exclude={"participants"}),
    )
    attach_shares(expense, data)
    session.add(expense)
    session.flush()
    record_audit(
        session,
        activity_id=activity_id,
        actor_user_id=user.id,
        action="EXPENSE_CREATED",
        object_type="expense",
        object_id=expense.id,
        after=expense_snapshot(expense),
    )
    return expense
