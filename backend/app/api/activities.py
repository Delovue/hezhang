from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import Limit, Offset, OptionalQueryId, ResourceId, Search
from app.errors import ApiError, ErrorCode
from app.models import Activity, ActivityStatus, AuditLog, Membership
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
    status: ActivityStatus | None = None,
    q: Search = None,
    before_id: OptionalQueryId = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    if before_id is not None and offset:
        raise ApiError(422, ErrorCode.INVALID_QUERY, "before_id 不能与非零 offset 同时使用")
    query = (
        select(Activity)
        .join(Membership, Membership.activity_id == Activity.id)
        .where(Membership.user_id == user.id)
    )
    if status is not None:
        query = query.where(Activity.status == status)
    if q is not None:
        query = query.where(Activity.name.icontains(q, autoescape=True))
    if before_id is not None:
        query = query.where(Activity.id < before_id)
    activities = session.scalars(
        query.order_by(Activity.id.desc()).limit(limit).offset(offset)
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
    action: Annotated[str | None, Query(pattern=r"^[A-Z][A-Z0-9_]{0,39}$")] = None,
    object_type: Annotated[str | None, Query(pattern=r"^[a-z][a-z0-9_]{0,29}$")] = None,
    object_id: OptionalQueryId = None,
    actor_user_id: OptionalQueryId = None,
    before_id: OptionalQueryId = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    require_activity(session, activity_id, user.id)
    if object_id is not None and object_type is None:
        raise ApiError(422, ErrorCode.INVALID_QUERY, "按对象编号查询时必须同时提供 object_type")
    if before_id is not None and offset:
        raise ApiError(422, ErrorCode.INVALID_QUERY, "before_id 不能与非零 offset 同时使用")
    query = select(AuditLog).where(AuditLog.activity_id == activity_id)
    if action is not None:
        query = query.where(AuditLog.action == action)
    if object_type is not None:
        query = query.where(AuditLog.object_type == object_type)
    if object_id is not None:
        query = query.where(AuditLog.object_id == object_id)
    if actor_user_id is not None:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
    if before_id is not None:
        query = query.where(AuditLog.id < before_id)
    return session.scalars(query.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).all()
