import itertools

import pytest

from app.domain.errors import InvalidInputError
from app.domain.split import (
    ShareResult,
    SplitMethod,
    SplitParticipant,
    compute_split,
    split_equal,
    split_exact,
    split_shares,
)


def test_t01_equal_split_100_yuan_among_three():
    result = split_equal(10000, [1, 2, 3])

    assert result == {1: 3334, 2: 3333, 3: 3333}
    assert sum(result.values()) == 10000


def test_t02_equal_split_one_cent_is_deterministic_for_any_order():
    for order in itertools.permutations([7, 3, 5]):
        assert split_equal(1, list(order)) == {3: 1, 5: 0, 7: 0}


def test_equal_split_result_is_ordered_by_member_id():
    assert list(split_equal(500, [9, 2, 4])) == [2, 4, 9]


def test_equal_split_single_member_takes_all():
    assert split_equal(12345, [42]) == {42: 12345}


@pytest.mark.parametrize("amount", [0, -100, 10.5, "100", True, None])
def test_equal_split_rejects_invalid_amount(amount):
    with pytest.raises(InvalidInputError):
        split_equal(amount, [1, 2])


@pytest.mark.parametrize("members", [[], [1, 1], [1, "2"], [1.0, 2]])
def test_equal_split_rejects_invalid_members(members):
    with pytest.raises(InvalidInputError):
        split_equal(100, members)


def test_exact_split_keeps_given_amounts():
    assert split_exact(10000, {3: 5000, 1: 2000, 2: 3000}) == {1: 2000, 2: 3000, 3: 5000}


def test_exact_split_allows_zero_share():
    assert split_exact(600, {1: 600, 2: 0}) == {1: 600, 2: 0}


@pytest.mark.parametrize(
    "amounts",
    [
        {1: 2000, 2: 3000, 3: 4999},  # 合计少 1 分
        {1: 2000, 2: 3000, 3: 5001},  # 合计多 1 分
        {1: 11000, 2: -1000},  # 负份额
        {1: 5000.0, 2: 5000},  # 非整数分
        {},
    ],
)
def test_t04_exact_split_rejects_invalid_amounts(amounts):
    with pytest.raises(InvalidInputError):
        split_exact(10000, amounts)


def test_t03_shares_split_600_yuan_by_2_2_1_1():
    assert split_shares(60000, {1: 2, 2: 2, 3: 1, 4: 1}) == {
        1: 20000,
        2: 20000,
        3: 10000,
        4: 10000,
    }


def test_shares_split_gives_leftover_to_largest_remainder():
    # 100 分按 1:2 → 精确值 33.33 与 66.67，余数大的成员 2 补 1 分
    assert split_shares(100, {1: 1, 2: 2}) == {1: 33, 2: 67}


def test_shares_split_breaks_remainder_tie_by_member_id():
    for order in itertools.permutations([(8, 1), (2, 1), (5, 1)]):
        assert split_shares(1, dict(order)) == {2: 1, 5: 0, 8: 0}


@pytest.mark.parametrize("amount", [1, 7, 99, 10001, 123457])
def test_shares_split_conserves_total(amount):
    result = split_shares(amount, {1: 3, 2: 5, 3: 7, 4: 1})
    assert sum(result.values()) == amount


@pytest.mark.parametrize("shares", [{1: 0, 2: 1}, {1: -1, 2: 2}, {1: 1.5, 2: 1}, {}])
def test_t04_shares_split_rejects_invalid_shares(shares):
    with pytest.raises(InvalidInputError):
        split_shares(100, shares)


def test_compute_split_equal_ignores_values():
    participants = [SplitParticipant(2), SplitParticipant(1, amount_cents=999)]
    assert compute_split(301, SplitMethod.EQUAL, participants) == [
        ShareResult(1, 151),
        ShareResult(2, 150),
    ]


def test_compute_split_shares_keeps_share_counts():
    participants = [SplitParticipant(1, shares=2), SplitParticipant(2, shares=1)]
    assert compute_split(300, SplitMethod.SHARES, participants) == [
        ShareResult(1, 200, 2),
        ShareResult(2, 100, 1),
    ]


@pytest.mark.parametrize("method", list(SplitMethod))
def test_t04_compute_split_rejects_duplicate_members(method):
    participants = [
        SplitParticipant(1, amount_cents=50, shares=1),
        SplitParticipant(1, amount_cents=50, shares=1),
    ]
    with pytest.raises(InvalidInputError):
        compute_split(100, method, participants)


@pytest.mark.parametrize(
    ("method", "participants"),
    [
        (SplitMethod.EXACT, [SplitParticipant(1, amount_cents=100), SplitParticipant(2)]),
        (SplitMethod.SHARES, [SplitParticipant(1, shares=1), SplitParticipant(2)]),
    ],
)
def test_compute_split_requires_values_for_method(method, participants):
    with pytest.raises(InvalidInputError):
        compute_split(100, method, participants)


def test_t05_member_outside_split_bears_nothing():
    result = compute_split(6000, SplitMethod.EQUAL, [SplitParticipant(1), SplitParticipant(2)])
    assert {r.member_id for r in result} == {1, 2}
