"""活动结算生命周期：发起结算、自动结清与归档。

调用方必须处于写事务中（POST 请求默认 BEGIN IMMEDIATE），
保证读取余额、校验状态与写入状态之间不会有其他写入插入。
"""

from sqlalchemy.orm import Session

from app.domain import activity as rules
from app.models import Activity, ActivityStatus, User
from app.services.activity import activity_snapshot, require_activity
from app.services.audit import record_audit
from app.services.balance import load_balances


def _change_status(
    session: Session, activity: Activity, user: User, status: ActivityStatus, action: str
) -> None:
    before = activity_snapshot(activity)
    activity.status = status
    session.flush()
    record_audit(
        session,
        activity_id=activity.id,
        actor_user_id=user.id,
        action=action,
        object_type="activity",
        object_id=activity.id,
        before=before,
        after=activity_snapshot(activity),
    )


def start_settlement(session: Session, activity_id: int, user: User) -> Activity:
    activity = require_activity(session, activity_id, user.id)
    status = rules.start_settlement(
        activity.status, user.id, activity.owner_id, load_balances(session, activity_id)
    )
    _change_status(session, activity, user, status, "SETTLEMENT_STARTED")
    return activity


def settle_if_cleared(session: Session, activity: Activity, user: User) -> None:
    """付款状态变化后调用；满足结清条件时由服务端自动转为 SETTLED。"""
    status = rules.settle_if_cleared(activity.status, load_balances(session, activity.id))
    if status != activity.status:
        _change_status(session, activity, user, status, "ACTIVITY_SETTLED")


def archive_activity(session: Session, activity_id: int, user: User) -> Activity:
    activity = require_activity(session, activity_id, user.id)
    status = rules.archive(activity.status, user.id, activity.owner_id)
    _change_status(session, activity, user, status, "ACTIVITY_ARCHIVED")
    return activity
