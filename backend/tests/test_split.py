from itertools import permutations

import pytest
from pydantic import ValidationError

from app.domain.split import calculate_split
from app.schemas import SplitInput


@pytest.mark.parametrize(
    ("method", "amount", "participants", "expected"),
    [
        (
            "EQUAL",
            10000,
            [{"member_id": 3}, {"member_id": 1}, {"member_id": 2}],
            [3334, 3333, 3333],
        ),
        (
            "SHARES",
            60000,
            [
                {"member_id": 1, "shares": 2},
                {"member_id": 2, "shares": 2},
                {"member_id": 3, "shares": 1},
                {"member_id": 4, "shares": 1},
            ],
            [20000, 20000, 10000, 10000],
        ),
        (
            "SHARES",
            5,
            [
                {"member_id": 1, "shares": 1},
                {"member_id": 2, "shares": 2},
                {"member_id": 3, "shares": 4},
            ],
            [1, 1, 3],
        ),
        (
            "EXACT",
            10000,
            [
                {"member_id": 1, "amount_cents": 2000},
                {"member_id": 2, "amount_cents": 3000},
                {"member_id": 3, "amount_cents": 5000},
            ],
            [2000, 3000, 5000],
        ),
    ],
)
def test_reference_splits(method, amount, participants, expected):
    spec = SplitInput(amount_cents=amount, split_method=method, participants=participants)
    assert [share.amount_cents for share in calculate_split(spec)] == expected


def test_one_cent_and_input_order_invariance():
    participants = [{"member_id": member, "shares": 1} for member in [9, 2, 6]]
    for ordered in permutations(participants):
        result = calculate_split(
            SplitInput(amount_cents=1, split_method="SHARES", participants=list(ordered))
        )
        assert [(share.member_id, share.amount_cents) for share in result] == [
            (2, 1),
            (6, 0),
            (9, 0),
        ]


def test_large_amounts_and_many_small_totals_conserve_cents():
    for amount in [*range(1, 101), 9_007_199_254_740_991]:
        result = calculate_split(
            SplitInput(
                amount_cents=amount,
                split_method="SHARES",
                participants=[{"member_id": i, "shares": i} for i in range(1, 8)],
            )
        )
        assert sum(share.amount_cents for share in result) == amount
        assert all(
            isinstance(share.amount_cents, int) and share.amount_cents >= 0 for share in result
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": True},
        {"amount_cents": 1.5},
        {"amount_cents": "100"},
        {"amount_cents": 0},
        {"amount_cents": -1},
        {"amount_cents": 9_007_199_254_740_992},
        {"participants": []},
        {"participants": [{"member_id": 1}, {"member_id": 1}]},
        {"participants": [{"member_id": 1, "shares": 1}]},
        {"split_method": "SHARES", "participants": [{"member_id": 1, "shares": 0}]},
        {"split_method": "EXACT", "participants": [{"member_id": 1, "amount_cents": 99}]},
    ],
)
def test_invalid_money_or_split_rejected(changes):
    payload = {"amount_cents": 100, "split_method": "EQUAL", "participants": [{"member_id": 1}]}
    payload.update(changes)
    with pytest.raises(ValidationError):
        SplitInput.model_validate(payload)
