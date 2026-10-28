from urllib.parse import quote

from fastapi import APIRouter, Response

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import ResourceId
from app.domain.statistics import compute_statistics
from app.schemas import StatisticsRead
from app.services.activity import require_activity
from app.services.balance import expense_entries, member_ids
from app.services.export import export_expenses_csv

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


@router.get(
    "/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "UTF-8 BOM 编码的费用明细"}},
)
def export_csv(activity_id: ResourceId, session: Database, user: CurrentUser):
    activity = require_activity(session, activity_id, user.id)
    filename = quote(f"{activity.name}-费用明细.csv", safe="")
    return Response(
        content=export_expenses_csv(session, activity),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"activity-{activity.id}.csv\"; filename*=UTF-8''{filename}"
            )
        },
    )
