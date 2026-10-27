from app.models import SplitMethod
from app.schemas import ShareRead, SplitInput


def calculate_split(spec: SplitInput) -> list[ShareRead]:
    """Shared calculator for expense saves and the future preview endpoint."""
    participants = sorted(spec.participants, key=lambda item: item.member_id)
    if spec.split_method == SplitMethod.EXACT:
        return [
            ShareRead(member_id=item.member_id, amount_cents=item.amount_cents, shares=None)
            for item in participants
        ]
    weights = [
        item.shares if spec.split_method == SplitMethod.SHARES else 1 for item in participants
    ]
    total_weight = sum(weights)
    quotients = [divmod(spec.amount_cents * weight, total_weight) for weight in weights]
    amounts = [quotient for quotient, _remainder in quotients]
    remaining = spec.amount_cents - sum(amounts)
    order = sorted(
        range(len(participants)),
        key=lambda index: (-quotients[index][1], participants[index].member_id),
    )
    for index in order[:remaining]:
        amounts[index] += 1
    return [
        ShareRead(
            member_id=item.member_id,
            amount_cents=amounts[index],
            shares=item.shares if spec.split_method == SplitMethod.SHARES else None,
        )
        for index, item in enumerate(participants)
    ]
