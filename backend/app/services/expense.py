from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.split import calculate_split
from app.models import Expense, ExpenseShare, Membership, SplitMethod, User
from app.schemas import ExpenseCreate, ExpensePatch, ExpenseRead
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


def require_expense_editor(expense: Expense, user_id: int, owner_id: int) -> None:
    if user_id not in {expense.created_by_id, owner_id}:
        raise HTTPException(403, "只有费用记录者或活动创建者可以修改此费用")


def require_version(expense: Expense, expected: int) -> None:
    if expense.version != expected:
        raise HTTPException(409, "费用已被修改，请刷新后重试")


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


def original_input(expense: Expense) -> dict:
    result = {
        key: getattr(expense, key)
        for key in [
            "title",
            "category",
            "amount_cents",
            "expense_date",
            "notes",
            "payer_member_id",
            "split_method",
        ]
    }
    participants = []
    for share in expense.shares:
        item = {"member_id": share.member_id}
        if expense.split_method == SplitMethod.EXACT:
            item["amount_cents"] = share.amount_cents
        elif expense.split_method == SplitMethod.SHARES:
            item["shares"] = share.shares
        participants.append(item)
    result["participants"] = participants
    return result


def update_expense(
    session: Session, activity_id: int, expense_id: int, user: User, patch: ExpensePatch
) -> Expense:
    activity = require_activity(session, activity_id, user.id)
    expense = require_expense(session, activity_id, expense_id)
    require_expense_editor(expense, user.id, activity.owner_id)
    require_active(activity)
    require_version(expense, patch.version)
    merged = original_input(expense)
    merged.update(patch.model_dump(exclude_unset=True, exclude={"version"}))
    try:
        data = ExpenseCreate.model_validate(merged)
    except ValidationError as exc:
        raise HTTPException(422, "; ".join(error["msg"] for error in exc.errors())) from None
    validate_members(session, activity_id, data)
    before = expense_snapshot(expense)
    # Delete old shares before inserting their replacements under the unique constraint.
    # Both flushes stay inside the same request transaction.
    expense.shares.clear()
    session.flush()
    for key, value in data.model_dump(exclude={"participants"}).items():
        setattr(expense, key, value)
    expense.version += 1
    attach_shares(expense, data)
    session.flush()
    record_audit(
        session,
        activity_id=activity_id,
        actor_user_id=user.id,
        action="EXPENSE_UPDATED",
        object_type="expense",
        object_id=expense.id,
        before=before,
        after=expense_snapshot(expense),
    )
    return expense
