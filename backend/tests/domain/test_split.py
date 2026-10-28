import itertools

import pytest

from app.domain.errors import InvalidInputError
from app.domain.split import split_equal


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
