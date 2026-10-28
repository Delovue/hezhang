from fastapi import APIRouter

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import ResourceId
from app.domain.settlement import suggest_transfers
from app.domain.split import calculate_split
from app.errors import ErrorCode
from app.schemas import ActivityRead, MemberBalanceRead, ShareRead, SplitInput, TransferRead
from app.services.activity import activity_read, require_activity
from app.services.balance import load_balances, require_members
from app.services.lifecycle import archive_activity, start_settlement

router = APIRouter(prefix="/activities/{activity_id}", tags=["余额与结算"])


@router.post("/split-preview", response_model=list[ShareRead])
def split_preview(activity_id: ResourceId, data: SplitInput, session: Database, user: CurrentUser):
    """与保存费用使用同一个分摊函数，只计算不保存。"""
    require_activity(session, activity_id, user.id)
    require_members(
        session,
        activity_id,
        (item.member_id for item in data.participants),
        ErrorCode.EXPENSE_MEMBER_MISMATCH,
    )
    return calculate_split(data)


@router.get("/balances", response_model=list[MemberBalanceRead])
def balances(activity_id: ResourceId, session: Database, user: CurrentUser):
    require_activity(session, activity_id, user.id)
    return load_balances(session, activity_id)


@router.get("/settlement-suggestions", response_model=list[TransferRead])
def settlement_suggestions(activity_id: ResourceId, session: Database, user: CurrentUser):
    require_activity(session, activity_id, user.id)
    return [
        TransferRead(
            payer_member_id=transfer.payer_id,
            payee_member_id=transfer.payee_id,
            amount_cents=transfer.amount_cents,
        )
        for transfer in suggest_transfers(load_balances(session, activity_id))
    ]


@router.post("/start-settlement", response_model=ActivityRead)
def start(activity_id: ResourceId, session: Database, user: CurrentUser):
    """创建者发起结算，冻结账目；已满足结清条件时直接返回 SETTLED。"""
    return activity_read(start_settlement(session, activity_id, user), user.id)


@router.post("/archive", response_model=ActivityRead)
def archive(activity_id: ResourceId, session: Database, user: CurrentUser):
    return activity_read(archive_activity(session, activity_id, user), user.id)
