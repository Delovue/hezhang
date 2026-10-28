"""付款登记与查询。

登记在写事务内先取写锁，再读取最新余额与待确认占用并校验，最后写入付款和历史，
因此两笔并发登记不会同时通过额度检查。
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.payment import check_request_retry, validate_new_payment
from app.models import Membership, Payment, User
from app.schemas import PaymentCreate, PaymentRead
from app.services.activity import require_activity
from app.services.audit import record_audit
from app.services.balance import load_balances, require_members


def current_member(session: Session, activity_id: int, user_id: int) -> Membership:
    member = session.scalar(
        select(Membership).where(
            Membership.activity_id == activity_id, Membership.user_id == user_id
        )
    )
    if member is None:
        raise HTTPException(404, "活动不存在")
    return member


def payment_snapshot(payment: Payment) -> dict:
    # request_id 只用于去重，不进入历史
    return PaymentRead.model_validate(payment).model_dump(
        mode="json", exclude={"created_at", "updated_at"}
    )


def create_payment(
    session: Session, activity_id: int, user: User, data: PaymentCreate
) -> tuple[Payment, bool]:
    """返回付款记录以及本次请求是否新建。付款人固定为当前用户。"""
    activity = require_activity(session, activity_id, user.id)
    payer = current_member(session, activity_id, user.id)
    request_key = str(data.request_id)
    existing = session.scalar(
        select(Payment).where(
            Payment.activity_id == activity_id,
            Payment.payer_member_id == payer.id,
            Payment.request_id == request_key,
        )
    )
    if existing is not None:
        check_request_retry(
            existing.payee_member_id, existing.amount_cents, data.payee_member_id, data.amount_cents
        )
        # 重试可能发生在活动结清之后，只读返回原记录，不再检查状态和额度
        return existing, False

    require_members(session, activity_id, [data.payee_member_id])
    balances = {b.member_id: b for b in load_balances(session, activity_id)}
    validate_new_payment(
        activity.status, balances[payer.id], balances[data.payee_member_id], data.amount_cents
    )
    payment = Payment(
        activity_id=activity_id,
        payer_member_id=payer.id,
        payee_member_id=data.payee_member_id,
        amount_cents=data.amount_cents,
        request_id=request_key,
    )
    session.add(payment)
    session.flush()
    session.refresh(payment)
    record_audit(
        session,
        activity_id=activity_id,
        actor_user_id=user.id,
        action="PAYMENT_CREATED",
        object_type="payment",
        object_id=payment.id,
        after=payment_snapshot(payment),
    )
    return payment, True
