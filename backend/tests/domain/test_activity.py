import pytest

from app.domain.activity import (
    archive,
    ensure_ledger_editable,
    ensure_payments_open,
    is_cleared,
    settle_if_cleared,
    start_settlement,
)
from app.domain.balance import ExpenseEntry, PaymentEntry, compute_balances
from app.domain.errors import PermissionDeniedError, StateConflictError
from app.domain.split import split_equal
from app.domain.status import ActivityStatus, PaymentStatus

A, B, C = 1, 2, 3
CREATOR = A

TRIP_EXPENSES = [
    ExpenseEntry(A, 12000, split_equal(12000, [A, B, C])),
    ExpenseEntry(B, 6000, split_equal(6000, [A, B])),
]
OPEN_BALANCES = compute_balances([A, B, C], TRIP_EXPENSES, [])
CLEARED_BALANCES = compute_balances(
    [A, B, C],
    TRIP_EXPENSES,
    [
        PaymentEntry(C, A, 4000, PaymentStatus.CONFIRMED),
        PaymentEntry(B, A, 1000, PaymentStatus.CONFIRMED),
    ],
)


def test_start_settlement_with_debts_enters_settling():
    status = start_settlement(ActivityStatus.ACTIVE, CREATOR, CREATOR, OPEN_BALANCES)
    assert status == ActivityStatus.SETTLING


def test_t17_start_settlement_without_expenses_is_settled_immediately():
    balances = compute_balances([A, B, C], [], [])
    status = start_settlement(ActivityStatus.ACTIVE, CREATOR, CREATOR, balances)
    assert status == ActivityStatus.SETTLED


def test_t17_start_settlement_with_net_zero_is_settled_immediately():
    # A、B 各垫付 50 元并两人均摊，净额恰好全零
    expenses = [
        ExpenseEntry(A, 5000, split_equal(5000, [A, B])),
        ExpenseEntry(B, 5000, split_equal(5000, [A, B])),
    ]
    balances = compute_balances([A, B], expenses, [])
    assert start_settlement(ActivityStatus.ACTIVE, CREATOR, CREATOR, balances) == (
        ActivityStatus.SETTLED
    )


def test_only_creator_can_start_settlement():
    with pytest.raises(PermissionDeniedError):
        start_settlement(ActivityStatus.ACTIVE, B, CREATOR, OPEN_BALANCES)


@pytest.mark.parametrize(
    "status", [ActivityStatus.SETTLING, ActivityStatus.SETTLED, ActivityStatus.ARCHIVED]
)
def test_cannot_start_settlement_twice(status):
    with pytest.raises(StateConflictError):
        start_settlement(status, CREATOR, CREATOR, OPEN_BALANCES)


def test_pending_payment_blocks_clearing():
    pending = compute_balances(
        [A, B],
        [],
        [PaymentEntry(B, A, 100, PaymentStatus.PENDING)],
    )
    # 余额全零但存在待确认付款，仍不能判为结清
    assert not is_cleared(pending)


def test_settle_if_cleared_after_last_confirmation():
    assert settle_if_cleared(ActivityStatus.SETTLING, CLEARED_BALANCES) == ActivityStatus.SETTLED
    assert settle_if_cleared(ActivityStatus.SETTLING, OPEN_BALANCES) == ActivityStatus.SETTLING


def test_settle_if_cleared_does_not_touch_active_activity():
    balances = compute_balances([A, B], [], [])
    assert settle_if_cleared(ActivityStatus.ACTIVE, balances) == ActivityStatus.ACTIVE


def test_t16_archive_settled_activity():
    assert archive(ActivityStatus.SETTLED, CREATOR, CREATOR) == ActivityStatus.ARCHIVED


@pytest.mark.parametrize(
    "status", [ActivityStatus.ACTIVE, ActivityStatus.SETTLING, ActivityStatus.ARCHIVED]
)
def test_t16_archive_rejected_unless_settled(status):
    with pytest.raises(StateConflictError):
        archive(status, CREATOR, CREATOR)


def test_only_creator_can_archive():
    with pytest.raises(PermissionDeniedError):
        archive(ActivityStatus.SETTLED, C, CREATOR)


def test_ledger_editable_only_while_active():
    ensure_ledger_editable(ActivityStatus.ACTIVE)
    for status in (ActivityStatus.SETTLING, ActivityStatus.SETTLED, ActivityStatus.ARCHIVED):
        with pytest.raises(StateConflictError):
            ensure_ledger_editable(status)


def test_payments_open_only_while_settling():
    ensure_payments_open(ActivityStatus.SETTLING)
    for status in (ActivityStatus.ACTIVE, ActivityStatus.SETTLED, ActivityStatus.ARCHIVED):
        with pytest.raises(StateConflictError):
            ensure_payments_open(status)
