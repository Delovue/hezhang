"""活动生命周期：ACTIVE -> SETTLING -> SETTLED -> ARCHIVED。

- ACTIVE：可加入成员、录入和修改费用
- SETTLING：冻结成员、费用、分摊和预算，只允许处理付款
- SETTLED：账务只读，等待创建者归档
- ARCHIVED：只读查询与导出
"""

from collections.abc import Sequence

from app.domain.balance import MemberBalance
from app.domain.errors import PermissionDeniedError, StateConflictError
from app.models import ActivityStatus


def is_cleared(balances: Sequence[MemberBalance]) -> bool:
    """全部余额为零且没有待确认付款。"""
    return all(
        b.balance_cents == 0 and b.pending_out_cents == 0 and b.pending_in_cents == 0
        for b in balances
    )


def ensure_ledger_editable(status: ActivityStatus) -> None:
    """成员加入、费用增删改和预算修改前调用。"""
    if status != ActivityStatus.ACTIVE:
        raise StateConflictError("活动已发起结算，成员、费用和预算不能再修改")


def ensure_payments_open(status: ActivityStatus) -> None:
    """登记付款和改变付款状态前调用。"""
    if status != ActivityStatus.SETTLING:
        raise StateConflictError("只有结算中的活动可以处理付款")


def _ensure_creator(actor_id: int, creator_id: int, action: str) -> None:
    if actor_id != creator_id:
        raise PermissionDeniedError(f"只有活动创建者可以{action}")


def start_settlement(
    status: ActivityStatus,
    actor_id: int,
    creator_id: int,
    balances: Sequence[MemberBalance],
) -> ActivityStatus:
    """创建者发起结算。发起时已满足结清条件则直接进入 SETTLED。"""
    _ensure_creator(actor_id, creator_id, "发起结算")
    if status != ActivityStatus.ACTIVE:
        raise StateConflictError("活动已发起过结算")
    return ActivityStatus.SETTLED if is_cleared(balances) else ActivityStatus.SETTLING


def settle_if_cleared(status: ActivityStatus, balances: Sequence[MemberBalance]) -> ActivityStatus:
    """付款状态变化后调用，由服务端自动判定是否结清。"""
    if status == ActivityStatus.SETTLING and is_cleared(balances):
        return ActivityStatus.SETTLED
    return status


def archive(status: ActivityStatus, actor_id: int, creator_id: int) -> ActivityStatus:
    _ensure_creator(actor_id, creator_id, "归档活动")
    if status != ActivityStatus.SETTLED:
        raise StateConflictError("活动尚未结清，不能归档")
    return ActivityStatus.ARCHIVED
