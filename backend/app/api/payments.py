from fastapi import APIRouter, Response
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import Limit, Offset, ResourceId
from app.domain.payment import PaymentAction
from app.models import Payment, PaymentStatus
from app.schemas import PaymentCreate, PaymentRead
from app.services.activity import require_activity
from app.services.payment import change_payment, create_payment

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


@router.post("/{payment_id}/confirm", response_model=PaymentRead)
def confirm(activity_id: ResourceId, payment_id: ResourceId, session: Database, user: CurrentUser):
    """收款人确认收款；全部结清时活动自动转为 SETTLED。"""
    return change_payment(session, activity_id, payment_id, user, PaymentAction.CONFIRM)


@router.post("/{payment_id}/reject", response_model=PaymentRead)
def reject(activity_id: ResourceId, payment_id: ResourceId, session: Database, user: CurrentUser):
    """收款人拒绝，释放双方占用的可登记额度。"""
    return change_payment(session, activity_id, payment_id, user, PaymentAction.REJECT)


@router.post("/{payment_id}/cancel", response_model=PaymentRead)
def cancel(activity_id: ResourceId, payment_id: ResourceId, session: Database, user: CurrentUser):
    """付款人撤销自己的待确认付款。"""
    return change_payment(session, activity_id, payment_id, user, PaymentAction.CANCEL)
