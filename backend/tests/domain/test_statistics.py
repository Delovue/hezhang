from app.domain.balance import ExpenseEntry
from app.domain.split import split_equal
from app.domain.statistics import (
    ActivityStatistics,
    CategoryTotal,
    MemberShareTotal,
    compute_statistics,
)

A, B, C = 1, 2, 3

TRIP_EXPENSES = [
    ExpenseEntry(A, 12000, split_equal(12000, [A, B, C]), "餐饮"),
    ExpenseEntry(B, 6000, split_equal(6000, [A, B]), "交通"),
]


def test_trip_statistics_within_budget():
    stats = compute_statistics([A, B, C], TRIP_EXPENSES, 50000)

    assert stats == ActivityStatistics(
        total_spent_cents=18000,
        budget_cents=50000,
        remaining_budget_cents=32000,
        over_budget=False,
        by_category=[CategoryTotal("餐饮", 12000), CategoryTotal("交通", 6000)],
        by_member=[
            MemberShareTotal(A, 7000),
            MemberShareTotal(B, 7000),
            MemberShareTotal(C, 4000),
        ],
    )


def test_over_budget_reports_negative_remaining():
    stats = compute_statistics([A, B, C], TRIP_EXPENSES, 15000)

    assert stats.over_budget is True
    assert stats.remaining_budget_cents == -3000


def test_spending_exactly_budget_is_not_over():
    stats = compute_statistics([A, B, C], TRIP_EXPENSES, 18000)

    assert stats.over_budget is False
    assert stats.remaining_budget_cents == 0


def test_no_budget_skips_budget_check():
    stats = compute_statistics([A, B, C], TRIP_EXPENSES, None)

    assert stats.remaining_budget_cents is None
    assert stats.over_budget is False


def test_same_category_merged_and_ties_sorted_by_name():
    expenses = [
        ExpenseEntry(A, 1000, {A: 1000}, "住宿"),
        ExpenseEntry(A, 3000, {A: 3000}, "门票"),
        ExpenseEntry(B, 2000, {B: 2000}, "住宿"),
    ]
    stats = compute_statistics([A, B], expenses, None)

    assert stats.by_category == [CategoryTotal("住宿", 3000), CategoryTotal("门票", 3000)]


def test_empty_activity_statistics():
    stats = compute_statistics([A, B], [], 10000)

    assert stats.total_spent_cents == 0
    assert stats.remaining_budget_cents == 10000
    assert stats.by_category == []
    assert stats.by_member == [MemberShareTotal(A, 0), MemberShareTotal(B, 0)]
