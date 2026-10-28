import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, ActivityStatus, Membership, User
from app.schemas import ActivityCreate, ActivityPatch, ActivityRead, MemberRead
from app.services.audit import record_audit


def require_activity(session: Session, activity_id: int, user_id: int) -> Activity:
    activity = session.scalar(
        select(Activity)
        .join(Membership, Membership.activity_id == Activity.id)
        .where(Activity.id == activity_id, Membership.user_id == user_id)
    )
    if activity is None:
        raise HTTPException(404, "活动不存在")
    return activity


def require_active(activity: Activity) -> None:
    if activity.status != ActivityStatus.ACTIVE:
        raise HTTPException(409, "活动已封账，不能修改成员、费用或预算")


def require_owner(activity: Activity, user_id: int) -> None:
    if activity.owner_id != user_id:
        raise HTTPException(403, "只有活动创建者可以执行此操作")


def activity_snapshot(activity: Activity) -> dict:
    return {
        "id": activity.id,
        "name": activity.name,
        "owner_id": activity.owner_id,
        "budget_cents": activity.budget_cents,
        "status": activity.status.value,
    }


def activity_read(activity: Activity, user_id: int) -> ActivityRead:
    return ActivityRead(
        **activity_snapshot(activity),
        invite_code=(
            activity.invite_code
            if activity.owner_id == user_id and activity.status == ActivityStatus.ACTIVE
            else None
        ),
    )


def create_activity(session: Session, user: User, data: ActivityCreate) -> Activity:
    activity = Activity(
        **data.model_dump(), owner_id=user.id, invite_code=secrets.token_urlsafe(18)
    )
    session.add(activity)
    session.flush()
    session.add(Membership(activity_id=activity.id, user_id=user.id))
    record_audit(
        session,
        activity_id=activity.id,
        actor_user_id=user.id,
        action="ACTIVITY_CREATED",
        object_type="activity",
        object_id=activity.id,
        after=activity_snapshot(activity),
    )
    return activity


def join_activity(session: Session, user: User, invite_code: str) -> Activity:
    activity = session.scalar(select(Activity).where(Activity.invite_code == invite_code))
    if activity is None:
        raise HTTPException(404, "邀请码无效")
    require_active(activity)
    existing = session.scalar(
        select(Membership).where(
            Membership.activity_id == activity.id, Membership.user_id == user.id
        )
    )
    if existing is None:
        member = Membership(activity_id=activity.id, user_id=user.id)
        session.add(member)
        session.flush()
        record_audit(
            session,
            activity_id=activity.id,
            actor_user_id=user.id,
            action="MEMBER_JOINED",
            object_type="membership",
            object_id=member.id,
            after={"member_id": member.id, "user_id": user.id},
        )
    return activity


def update_activity(
    session: Session, activity_id: int, user: User, data: ActivityPatch
) -> Activity:
    activity = require_activity(session, activity_id, user.id)
    require_owner(activity, user.id)
    require_active(activity)
    before = activity_snapshot(activity)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(activity, key, value)
    record_audit(
        session,
        activity_id=activity.id,
        actor_user_id=user.id,
        action="ACTIVITY_UPDATED",
        object_type="activity",
        object_id=activity.id,
        before=before,
        after=activity_snapshot(activity),
    )
    return activity


def list_members(session: Session, activity: Activity) -> list[MemberRead]:
    rows = session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.activity_id == activity.id)
        .order_by(Membership.id)
    ).all()
    return [
        MemberRead(
            id=member.id,
            user_id=user.id,
            display_name=user.display_name,
            role="OWNER" if user.id == activity.owner_id else "MEMBER",
        )
        for member, user in rows
    ]
