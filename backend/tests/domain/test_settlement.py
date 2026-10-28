import random
from collections import defaultdict

from app.domain.balance import ExpenseEntry, PaymentEntry, compute_balances
from app.domain.settlement import Transfer, suggest_transfers
from app.domain.split import split_equal
from app.models import PaymentStatus

A, B, C, D = 1, 2, 3, 4

TRIP_EXPENSES = [
    ExpenseEntry(A, 12000, split_equal(12000, [A, B, C])),
    ExpenseEntry(B, 6000, split_equal(6000, [A, B])),
]


def test_trip_example_suggestions():
    balances = compute_balances([A, B, C], TRIP_EXPENSES, [])

    assert suggest_transfers(balances) == [Transfer(C, A, 4000), Transfer(B, A, 1000)]


def test_suggestions_use_quota_after_pending_payments():
    pending = [PaymentEntry(C, A, 2000, PaymentStatus.PENDING)]
    balances = compute_balances([A, B, C], TRIP_EXPENSES, pending)

    assert suggest_transfers(balances) == [Transfer(C, A, 2000), Transfer(B, A, 1000)]


def test_suggestions_do_not_change_balances():
    balances = compute_balances([A, B, C], TRIP_EXPENSES, [])
    before = [b.balance_cents for b in balances]

    suggest_transfers(balances)

    assert [b.balance_cents for b in balances] == before


def test_multiple_creditors_ties_broken_by_member_id():
    # A 应收 30，B 应收 20，C 应付 40，D 应付 10
    expenses = [
        ExpenseEntry(A, 3000, {C: 3000}),
        ExpenseEntry(B, 2000, {C: 1000, D: 1000}),
    ]
    balances = compute_balances([A, B, C, D], expenses, [])

    assert suggest_transfers(balances) == [
        Transfer(C, A, 3000),
        Transfer(C, B, 1000),
        Transfer(D, B, 1000),
    ]


def test_settled_activity_has_no_suggestions():
    confirmed = [
        PaymentEntry(C, A, 4000, PaymentStatus.CONFIRMED),
        PaymentEntry(B, A, 1000, PaymentStatus.CONFIRMED),
    ]
    balances = compute_balances([A, B, C], TRIP_EXPENSES, confirmed)

    assert suggest_transfers(balances) == []


def test_random_ledgers_are_fully_settled_by_suggestions():
    rng = random.Random(20261028)
    for _ in range(200):
        members = list(range(1, rng.randint(2, 8) + 1))
        expenses = []
        for _ in range(rng.randint(1, 10)):
            amount = rng.randint(1, 50000)
            sharers = rng.sample(members, rng.randint(1, len(members)))
            expenses.append(ExpenseEntry(rng.choice(members), amount, split_equal(amount, sharers)))
        balances = compute_balances(members, expenses, [])

        transfers = suggest_transfers(balances)

        net = defaultdict(int)
        for t in transfers:
            assert t.amount_cents > 0 and t.payer_id != t.payee_id
            net[t.payer_id] += t.amount_cents
            net[t.payee_id] -= t.amount_cents
        assert all(b.balance_cents + net[b.member_id] == 0 for b in balances)
        assert len(transfers) <= len(members) - 1
