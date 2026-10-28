from datetime import date

from fastapi import APIRouter, Response
from sqlalchemy import or_, select

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import Limit, Offset, OptionalQueryId, QueryId, ResourceId, Search
from app.errors import ApiError, ErrorCode
from app.models import Expense, ExpenseShare
from app.schemas import ExpenseCreate, ExpensePatch, ExpenseRead
from app.services.activity import require_activity
from app.services.expense import (
    create_expense,
    delete_expense,
    require_expense,
    update_expense,
)

router = APIRouter(prefix="/activities/{activity_id}/expenses", tags=["费用"])


@router.post(
    "",
    response_model=ExpenseRead,
    status_code=201,
    responses={200: {"model": ExpenseRead, "description": "重复请求，返回已创建费用的当前版本"}},
)
def create(
    activity_id: ResourceId,
    data: ExpenseCreate,
    response: Response,
    session: Database,
    user: CurrentUser,
):
    expense, created = create_expense(session, activity_id, user, data)
    response.status_code = 201 if created else 200
    return expense


@router.get("", response_model=list[ExpenseRead])
def list_expenses(
    activity_id: ResourceId,
    session: Database,
    user: CurrentUser,
    category: str | None = None,
    payer_member_id: OptionalQueryId = None,
    participant_member_id: OptionalQueryId = None,
    q: Search = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    require_activity(session, activity_id, user.id)
    if start_date and end_date and start_date > end_date:
        raise ApiError(422, ErrorCode.INVALID_QUERY, "开始日期不能晚于结束日期")
    query = select(Expense).where(Expense.activity_id == activity_id, Expense.is_deleted.is_(False))
    if category is not None:
        query = query.where(Expense.category == category)
    if payer_member_id is not None:
        query = query.where(Expense.payer_member_id == payer_member_id)
    if participant_member_id is not None:
        query = query.where(Expense.shares.any(ExpenseShare.member_id == participant_member_id))
    if q is not None:
        query = query.where(
            or_(
                Expense.title.icontains(q, autoescape=True),
                Expense.notes.icontains(q, autoescape=True),
            )
        )
    if start_date is not None:
        query = query.where(Expense.expense_date >= start_date)
    if end_date is not None:
        query = query.where(Expense.expense_date <= end_date)
    return session.scalars(
        query.order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(limit).offset(offset)
    ).all()


@router.get("/{expense_id}", response_model=ExpenseRead)
def detail(activity_id: ResourceId, expense_id: ResourceId, session: Database, user: CurrentUser):
    require_activity(session, activity_id, user.id)
    return require_expense(session, activity_id, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update(
    activity_id: ResourceId,
    expense_id: ResourceId,
    data: ExpensePatch,
    session: Database,
    user: CurrentUser,
):
    return update_expense(session, activity_id, expense_id, user, data)


@router.delete("/{expense_id}", status_code=204)
def delete(
    activity_id: ResourceId,
    expense_id: ResourceId,
    session: Database,
    user: CurrentUser,
    version: QueryId,
):
    delete_expense(session, activity_id, expense_id, user, version)
    return Response(status_code=204)
