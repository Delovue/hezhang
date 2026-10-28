from fastapi import APIRouter

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import ResourceId
from app.domain.statistics import compute_statistics
from app.schemas import StatisticsRead
from app.services.activity import require_activity
from app.services.balance import expense_entries, member_ids

router = APIRouter(prefix="/activities/{activity_id}", tags=["统计与导出"])


@router.get("/statistics", response_model=StatisticsRead)
def statistics(activity_id: ResourceId, session: Database, user: CurrentUser):
    """消费只统计有效费用，成员间的结算付款不计入。"""
    activity = require_activity(session, activity_id, user.id)
    return compute_statistics(
        member_ids(session, activity_id),
        expense_entries(session, activity_id),
        activity.budget_cents,
    )
