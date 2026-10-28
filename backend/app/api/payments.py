from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import Limit, Offset, ResourceId
from app.models import Payment, PaymentStatus
from app.schemas import PaymentCreate, PaymentRead
from app.services.activity import require_activity
from app.services.payment import create_payment

router = APIRouter(prefix="/activities/{activity_id}/payments", tags=["付款"])


@router.post(
    "",
    response_model=PaymentRead,
    status_code=201,
    responses={200: {"model": PaymentRead, "description": "重复请求，返回已登记的付款"}},
)
def create(
    activity_id: ResourceId,
    data: PaymentCreate,
    response: Response,
    session: Database,
    user: CurrentUser,
):
    payment, created = create_payment(session, activity_id, user, data)
    response.status_code = 201 if created else 200
    return payment


@router.get("", response_model=list[PaymentRead])
def list_payments(
    activity_id: ResourceId,
    session: Database,
    user: CurrentUser,
    status: PaymentStatus | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    require_activity(session, activity_id, user.id)
    query = select(Payment).where(Payment.activity_id == activity_id)
    if status is not None:
        query = query.where(Payment.status == status)
    return session.scalars(query.order_by(Payment.id.desc()).limit(limit).offset(offset)).all()
