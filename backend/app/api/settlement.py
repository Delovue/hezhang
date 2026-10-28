from fastapi import APIRouter

from app.api.dependencies import CurrentUser, Database
from app.api.parameters import ResourceId
from app.domain.settlement import suggest_transfers
from app.schemas import MemberBalanceRead, TransferRead
from app.services.activity import require_activity
from app.services.balance import load_balances

router = APIRouter(prefix="/activities/{activity_id}", tags=["余额与结算"])


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
