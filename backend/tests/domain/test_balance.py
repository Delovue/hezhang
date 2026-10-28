import pytest

from app.domain.balance import ExpenseEntry, PaymentEntry, compute_balances
from app.domain.split import split_equal
from app.domain.status import PaymentStatus

A, B, C = 1, 2, 3

# README 中的三人出游示例：A 垫付餐费 120 元三人均摊，B 垫付车费 60 元仅 A、B 分摊
TRIP_EXPENSES = [
    ExpenseEntry(A, 12000, split_equal(12000, [A, B, C])),
    ExpenseEntry(B, 6000, split_equal(6000, [A, B])),
]


def by_member(balances):
    return {b.member_id: b for b in balances}


def test_t06_trip_example_balances():
    result = by_member(compute_balances([A, B, C], TRIP_EXPENSES, []))

    assert {m: b.paid_cents for m, b in result.items()} == {A: 12000, B: 6000, C: 0}
    assert {m: b.owed_cents for m, b in result.items()} == {A: 7000, B: 7000, C: 4000}
    assert {m: b.balance_cents for m, b in result.items()} == {A: 5000, B: -1000, C: -4000}


def test_balances_sum_to_zero():
    balances = compute_balances([A, B, C], TRIP_EXPENSES, [])
    assert sum(b.balance_cents for b in balances) == 0


def test_t05_member_outside_expense_is_unaffected():
    only_car = [ExpenseEntry(B, 6000, split_equal(6000, [A, B]))]
    result = by_member(compute_balances([A, B, C], only_car, []))

    assert result[C].owed_cents == 0
    assert result[C].balance_cents == 0


def test_t07_pending_payment_keeps_balance_but_reserves_quota():
    pending = [PaymentEntry(C, A, 2000, PaymentStatus.PENDING)]
    result = by_member(compute_balances([A, B, C], TRIP_EXPENSES, pending))

    assert result[A].balance_cents == 5000
    assert result[C].balance_cents == -4000
    assert result[C].pending_out_cents == 2000
    assert result[A].pending_in_cents == 2000
    assert result[C].available_out_cents == 2000
    assert result[A].available_in_cents == 3000


def test_t08_confirmed_payment_updates_balances():
    confirmed = [PaymentEntry(C, A, 2000, PaymentStatus.CONFIRMED)]
    result = by_member(compute_balances([A, B, C], TRIP_EXPENSES, confirmed))

    assert {m: b.balance_cents for m, b in result.items()} == {A: 3000, B: -1000, C: -2000}
    assert result[C].available_out_cents == 2000


@pytest.mark.parametrize("status", [PaymentStatus.REJECTED, PaymentStatus.CANCELLED])
def test_rejected_or_cancelled_payment_is_ignored(status):
    payments = [PaymentEntry(C, A, 2000, status)]
    result = by_member(compute_balances([A, B, C], TRIP_EXPENSES, payments))

    assert result[C].balance_cents == -4000
    assert result[C].available_out_cents == 4000


def test_member_without_activity_has_zero_balance():
    result = compute_balances([A, B], [], [])
    assert [(b.member_id, b.balance_cents, b.available_out_cents) for b in result] == [
        (A, 0, 0),
        (B, 0, 0),
    ]


def test_reference_to_non_member_is_data_error():
    with pytest.raises(ValueError):
        compute_balances([A, B], [ExpenseEntry(C, 100, {A: 100})], [])


def test_unbalanced_expense_is_data_error():
    with pytest.raises(ValueError):
        compute_balances([A, B], [ExpenseEntry(A, 100, {A: 50, B: 49})], [])
