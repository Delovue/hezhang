from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.models import Expense
from app.schemas import ExpenseCreate, ExpensePatch, ExpenseRead
from app.services.activity import require_activity
from app.services.expense import (
    create_expense,
    delete_expense,
    require_expense,
    update_expense,
)

router = APIRouter(prefix="/activities/{activity_id}/expenses", tags=["费用"])


@router.post("", response_model=ExpenseRead, status_code=201)
def create(activity_id: int, data: ExpenseCreate, session: Database, user: CurrentUser):
    return create_expense(session, activity_id, user, data)


@router.get("", response_model=list[ExpenseRead])
def list_expenses(
    activity_id: int,
    session: Database,
    user: CurrentUser,
    category: str | None = None,
    payer_member_id: Annotated[int | None, Query(gt=0)] = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    require_activity(session, activity_id, user.id)
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    query = select(Expense).where(Expense.activity_id == activity_id, Expense.is_deleted.is_(False))
    if category is not None:
        query = query.where(Expense.category == category)
    if payer_member_id is not None:
        query = query.where(Expense.payer_member_id == payer_member_id)
    if start_date is not None:
        query = query.where(Expense.expense_date >= start_date)
    if end_date is not None:
        query = query.where(Expense.expense_date <= end_date)
    return session.scalars(
        query.order_by(Expense.expense_date.desc(), Expense.id.desc()).limit(limit).offset(offset)
    ).all()


@router.get("/{expense_id}", response_model=ExpenseRead)
def detail(activity_id: int, expense_id: int, session: Database, user: CurrentUser):
    require_activity(session, activity_id, user.id)
    return require_expense(session, activity_id, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update(
    activity_id: int,
    expense_id: int,
    data: ExpensePatch,
    session: Database,
    user: CurrentUser,
):
    return update_expense(session, activity_id, expense_id, user, data)


@router.delete("/{expense_id}", status_code=204)
def delete(
    activity_id: int,
    expense_id: int,
    session: Database,
    user: CurrentUser,
    version: Annotated[int, Query(ge=1)],
):
    delete_expense(session, activity_id, expense_id, user, version)
    return Response(status_code=204)
