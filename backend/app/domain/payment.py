"""付款登记校验与付款状态机。

PENDING 可转为 CONFIRMED、REJECTED 或 CANCELLED，后三者均为终态。
仅收款人可确认或拒绝，仅付款人可撤销；创建者不能代替收款人确认。
同一操作者重复执行同一动作返回既有结果，不产生新的入账或历史。
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.activity import ensure_payments_open
from app.domain.balance import MemberBalance
from app.domain.errors import InvalidInputError, PermissionDeniedError, StateConflictError
from app.domain.money import format_cents
from app.domain.split import validate_amount
from app.domain.status import PAYMENT_STATUS_LABELS
from app.errors import ErrorCode
from app.models import ActivityStatus, PaymentStatus


def validate_new_payment(
    activity_status: ActivityStatus,
    payer: MemberBalance,
    payee: MemberBalance,
    amount_cents: int,
) -> None:
    """登记付款前校验。payer、payee 须为在同一写事务中重新计算的最新余额。

    超出可登记额度属于业务状态冲突（409）：同样的金额在别的付款被拒绝后可能合法。
    """
    ensure_payments_open(activity_status)
    validate_amount(amount_cents, ErrorCode.INVALID_PAYMENT)
    if payer.member_id == payee.member_id:
        raise InvalidInputError(ErrorCode.INVALID_PAYMENT, "付款人和收款人不能是同一人")
    if amount_cents > payer.available_out_cents:
        raise StateConflictError(
            ErrorCode.PAYMENT_QUOTA_EXCEEDED,
            f"付款金额超过付款人可登记额度 {format_cents(payer.available_out_cents)} 元",
        )
    if amount_cents > payee.available_in_cents:
        raise StateConflictError(
            ErrorCode.PAYMENT_QUOTA_EXCEEDED,
            f"付款金额超过收款人可登记额度 {format_cents(payee.available_in_cents)} 元",
        )


def check_request_retry(
    existing_payee_id: int,
    existing_amount_cents: int,
    payee_id: int,
    amount_cents: int,
) -> None:
    """同一付款人重复提交同一 request_id 时调用。

    内容一致说明是重试，服务层直接返回原记录；内容不同则拒绝复用该 ID。
    """
    if existing_payee_id != payee_id or existing_amount_cents != amount_cents:
        raise StateConflictError(ErrorCode.REQUEST_ID_CONFLICT, "该请求编号已用于另一笔付款")


class PaymentAction(StrEnum):
    CONFIRM = "CONFIRM"
    REJECT = "REJECT"
    CANCEL = "CANCEL"


_TARGET_STATUS = {
    PaymentAction.CONFIRM: PaymentStatus.CONFIRMED,
    PaymentAction.REJECT: PaymentStatus.REJECTED,
    PaymentAction.CANCEL: PaymentStatus.CANCELLED,
}

_ACTION_LABELS = {
    PaymentAction.CONFIRM: "确认",
    PaymentAction.REJECT: "拒绝",
    PaymentAction.CANCEL: "撤销",
}


@dataclass(frozen=True)
class PaymentTransition:
    status: PaymentStatus
    changed: bool  # False 表示重复操作，服务层不得再写入付款或历史


def apply_payment_action(
    activity_status: ActivityStatus,
    status: PaymentStatus,
    action: PaymentAction,
    actor_id: int,
    payer_id: int,
    payee_id: int,
) -> PaymentTransition:
    allowed_actor = payer_id if action == PaymentAction.CANCEL else payee_id
    if actor_id != allowed_actor:
        role = "付款人" if action == PaymentAction.CANCEL else "收款人"
        raise PermissionDeniedError(
            ErrorCode.PAYMENT_ACTION_FORBIDDEN, f"只有{role}可以{_ACTION_LABELS[action]}这笔付款"
        )

    target = _TARGET_STATUS[action]
    if status == target:
        # 重复确认可能发生在活动已自动结清之后，因此先于活动状态判断
        return PaymentTransition(status, changed=False)
    if status != PaymentStatus.PENDING:
        raise StateConflictError(
            ErrorCode.PAYMENT_STATUS_CONFLICT,
            f"付款{PAYMENT_STATUS_LABELS[status]}，不能再{_ACTION_LABELS[action]}",
        )
    ensure_payments_open(activity_status)
    return PaymentTransition(target, changed=True)
