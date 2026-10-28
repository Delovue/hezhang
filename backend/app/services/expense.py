import hashlib
import json

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.balance import ensure_total_within_limit
from app.domain.split import calculate_split
from app.errors import ApiError, ErrorCode
from app.models import Expense, ExpenseRequest, ExpenseShare, Membership, SplitMethod, User
from app.schemas import ExpenseCreate, ExpenseFields, ExpensePatch, ExpenseRead
from app.services.activity import require_active, require_activity
from app.services.audit import record_audit
from app.services.balance import other_expenses_total


def require_expense(session: Session, activity_id: int, expense_id: int) -> Expense:
    expense = session.scalar(
        select(Expense).where(
            Expense.id == expense_id,
            Expense.activity_id == activity_id,
            Expense.is_deleted.is_(False),
        )
    )
    if expense is None:
        raise ApiError(404, ErrorCode.EXPENSE_NOT_FOUND, "费用不存在")
    return expense


def require_expense_editor(expense: Expense, user_id: int, owner_id: int) -> None:
    if user_id not in {expense.created_by_id, owner_id}:
        raise ApiError(
            403, ErrorCode.EXPENSE_EDIT_FORBIDDEN, "只有费用记录者或活动创建者可以修改此费用"
        )


def require_version(expense: Expense, expected: int) -> None:
    if expense.version != expected:
        raise ApiError(409, ErrorCode.EXPENSE_VERSION_CONFLICT, "费用已被修改，请刷新后重试")


def validate_members(session: Session, activity_id: int, data: ExpenseFields) -> None:
    member_ids = {item.member_id for item in data.participants} | {data.payer_member_id}
    found = set(
        session.scalars(
            select(Membership.id).where(
                Membership.activity_id == activity_id, Membership.id.in_(member_ids)
            )
        ).all()
    )
    if found != member_ids:
        raise ApiError(422, ErrorCode.EXPENSE_MEMBER_MISMATCH, "付款人与所有分摊成员必须属于本活动")


def expense_snapshot(expense: Expense) -> dict:
    result = ExpenseRead.model_validate(expense).model_dump(mode="json")
    result["is_deleted"] = expense.is_deleted
    return result


def attach_shares(expense: Expense, data: ExpenseFields) -> None:
    expense.shares = [
        ExpenseShare(activity_id=expense.activity_id, **item.model_dump())
        for item in calculate_split(data)
    ]


def creation_fingerprint(data: ExpenseCreate) -> str:
    payload = data.model_dump(mode="json", exclude={"request_id"})
    # Member order, omitted defaults and JSON field order do not change an expense.
    payload["participants"].sort(key=lambda participant: participant["member_id"])
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_expense(
    session: Session, activity_id: int, user: User, data: ExpenseCreate
) -> tuple[Expense, bool]:
    """Return the current expense and whether this request newly created it."""
    activity = require_activity(session, activity_id, user.id)
    request_key = str(data.request_id) if data.request_id is not None else None
    fingerprint = creation_fingerprint(data) if request_key is not None else None
    if request_key is not None:
        existing = session.scalar(
            select(ExpenseRequest).where(
                ExpenseRequest.activity_id == activity_id,
                ExpenseRequest.created_by_id == user.id,
                ExpenseRequest.request_id == request_key,
            )
        )
        if existing is not None:
            if existing.payload_hash != fingerprint:
                raise ApiError(
                    409,
                    ErrorCode.REQUEST_ID_CONFLICT,
                    "request_id 已用于其他费用内容，请勿修改原请求后重试",
                )
            expense = session.get(Expense, existing.expense_id)
            if expense is None or expense.is_deleted:
                raise ApiError(
                    409, ErrorCode.EXPENSE_DELETED, "原请求对应的费用已被删除，请刷新账本"
                )
            # A successful creation may be retried after editing or sealing. This is read-only.
            return expense, False
    require_active(activity)
    validate_members(session, activity_id, data)
    ensure_total_within_limit(other_expenses_total(session, activity_id), data.amount_cents)
    expense = Expense(
        activity_id=activity_id,
        created_by_id=user.id,
        **data.model_dump(exclude={"participants", "request_id"}),
    )
    attach_shares(expense, data)
    session.add(expense)
    session.flush()
    if request_key is not None:
        session.add(
            ExpenseRequest(
                activity_id=activity_id,
                created_by_id=user.id,
                request_id=request_key,
                payload_hash=fingerprint,
                expense_id=expense.id,
            )
        )
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
    return expense, True


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
        data = ExpenseFields.model_validate(merged)
    except ValidationError as exc:
        raise ApiError(
            422, ErrorCode.INVALID_EXPENSE, "; ".join(error["msg"] for error in exc.errors())
        ) from None
    validate_members(session, activity_id, data)
    ensure_total_within_limit(
        other_expenses_total(session, activity_id, expense.id), data.amount_cents
    )
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


def delete_expense(
    session: Session, activity_id: int, expense_id: int, user: User, version: int
) -> None:
    activity = require_activity(session, activity_id, user.id)
    expense = require_expense(session, activity_id, expense_id)
    require_expense_editor(expense, user.id, activity.owner_id)
    require_active(activity)
    require_version(expense, version)
    before = expense_snapshot(expense)
    expense.is_deleted = True
    expense.version += 1
    session.flush()
    record_audit(
        session,
        activity_id=activity_id,
        actor_user_id=user.id,
        action="EXPENSE_DELETED",
        object_type="expense",
        object_id=expense.id,
        before=before,
        after=expense_snapshot(expense),
    )
