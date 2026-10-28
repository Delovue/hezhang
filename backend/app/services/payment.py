"""付款登记与查询。

登记在写事务内先取写锁，再读取最新余额与待确认占用并校验，最后写入付款和历史，
因此两笔并发登记不会同时通过额度检查。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.payment import (
    PaymentAction,
    apply_payment_action,
    check_request_retry,
    validate_new_payment,
)
from app.errors import ApiError, ErrorCode
from app.models import Membership, Payment, User
from app.schemas import PaymentCreate, PaymentRead
from app.services.activity import require_activity
from app.services.audit import record_audit
from app.services.balance import load_balances, require_members
from app.services.lifecycle import settle_if_cleared


def current_member(session: Session, activity_id: int, user_id: int) -> Membership:
    member = session.scalar(
        select(Membership).where(
            Membership.activity_id == activity_id, Membership.user_id == user_id
        )
    )
    if member is None:
        raise ApiError(404, ErrorCode.ACTIVITY_NOT_FOUND, "活动不存在")
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

    require_members(session, activity_id, [data.payee_member_id], ErrorCode.INVALID_PAYMENT)
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


def require_payment(session: Session, activity_id: int, payment_id: int) -> Payment:
    payment = session.scalar(
        select(Payment).where(Payment.id == payment_id, Payment.activity_id == activity_id)
    )
    if payment is None:
        raise ApiError(404, ErrorCode.PAYMENT_NOT_FOUND, "付款不存在")
    return payment


_AUDIT_ACTIONS = {
    PaymentAction.CONFIRM: "PAYMENT_CONFIRMED",
    PaymentAction.REJECT: "PAYMENT_REJECTED",
    PaymentAction.CANCEL: "PAYMENT_CANCELLED",
}


def change_payment(
    session: Session, activity_id: int, payment_id: int, user: User, action: PaymentAction
) -> Payment:
    """确认、拒绝或撤销付款。

    写锁保证确认、拒绝与撤销竞争时后到的请求读到已变更的状态，只有一个终态成功。
    同一操作者重复执行同一动作直接返回，不再写入付款或历史。
    """
    activity = require_activity(session, activity_id, user.id)
    payment = require_payment(session, activity_id, payment_id)
    actor = current_member(session, activity_id, user.id)
    transition = apply_payment_action(
        activity.status,
        payment.status,
        action,
        actor.id,
        payment.payer_member_id,
        payment.payee_member_id,
    )
    if not transition.changed:
        return payment

    before = payment_snapshot(payment)
    payment.status = transition.status
    session.flush()
    session.refresh(payment)
    record_audit(
        session,
        activity_id=activity_id,
        actor_user_id=user.id,
        action=_AUDIT_ACTIONS[action],
        object_type="payment",
        object_id=payment.id,
        before=before,
        after=payment_snapshot(payment),
    )
    settle_if_cleared(session, activity, user)
    return payment
