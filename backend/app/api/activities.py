from fastapi import APIRouter
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import Limit, Offset, ResourceId
from app.models import Activity, AuditLog, Membership
from app.schemas import (
    ActivityCreate,
    ActivityPatch,
    ActivityRead,
    AuditRead,
    JoinActivity,
    MemberRead,
)
from app.services.activity import (
    activity_read,
    create_activity,
    join_activity,
    list_members,
    require_activity,
    update_activity,
)

router = APIRouter(prefix="/activities", tags=["活动与成员"])


@router.post("", response_model=ActivityRead, status_code=201)
def create(data: ActivityCreate, session: Database, user: CurrentUser):
    return activity_read(create_activity(session, user, data), user.id)


@router.get("", response_model=list[ActivityRead])
def list_activities(
    session: Database,
    user: CurrentUser,
    limit: Limit = 50,
    offset: Offset = 0,
):
    activities = session.scalars(
        select(Activity)
        .join(Membership, Membership.activity_id == Activity.id)
        .where(Membership.user_id == user.id)
        .order_by(Activity.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [activity_read(activity, user.id) for activity in activities]


@router.post("/join", response_model=ActivityRead)
def join(data: JoinActivity, session: Database, user: CurrentUser):
    return activity_read(join_activity(session, user, data.invite_code), user.id)


@router.get("/{activity_id}", response_model=ActivityRead)
def detail(activity_id: ResourceId, session: Database, user: CurrentUser):
    return activity_read(require_activity(session, activity_id, user.id), user.id)


@router.patch("/{activity_id}", response_model=ActivityRead)
def update(activity_id: ResourceId, data: ActivityPatch, session: Database, user: CurrentUser):
    return activity_read(update_activity(session, activity_id, user, data), user.id)


@router.get("/{activity_id}/members", response_model=list[MemberRead])
def members(activity_id: ResourceId, session: Database, user: CurrentUser):
    return list_members(session, require_activity(session, activity_id, user.id))


@router.get("/{activity_id}/audit-logs", response_model=list[AuditRead])
def audit_logs(
    activity_id: ResourceId,
    session: Database,
    user: CurrentUser,
    limit: Limit = 50,
    offset: Offset = 0,
):
    require_activity(session, activity_id, user.id)
    return session.scalars(
        select(AuditLog)
        .where(AuditLog.activity_id == activity_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
