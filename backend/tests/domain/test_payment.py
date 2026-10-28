import pytest

from app.domain.balance import ExpenseEntry, PaymentEntry, compute_balances
from app.domain.errors import InvalidInputError, PermissionDeniedError, StateConflictError
from app.domain.money import format_cents
from app.domain.payment import (
    PaymentAction,
    PaymentTransition,
    apply_payment_action,
    check_request_retry,
    validate_new_payment,
)
from app.domain.split import split_equal
from app.models import ActivityStatus, PaymentStatus

A, B, C = 1, 2, 3
SETTLING = ActivityStatus.SETTLING

TRIP_EXPENSES = [
    ExpenseEntry(A, 12000, split_equal(12000, [A, B, C])),
    ExpenseEntry(B, 6000, split_equal(6000, [A, B])),
]


def balances(payments=()):
    return {b.member_id: b for b in compute_balances([A, B, C], TRIP_EXPENSES, list(payments))}


@pytest.mark.parametrize(
    ("cents", "text"), [(0, "0.00"), (5, "0.05"), (3334, "33.34"), (12000, "120.00"), (-5, "-0.05")]
)
def test_format_cents(cents, text):
    assert format_cents(cents) == text


def test_register_partial_payment():
    current = balances()
    validate_new_payment(SETTLING, current[C], current[A], 2000)


def test_register_full_quota_payment():
    current = balances()
    validate_new_payment(SETTLING, current[C], current[A], 4000)


def test_cannot_register_payment_before_settlement():
    current = balances()
    with pytest.raises(StateConflictError):
        validate_new_payment(ActivityStatus.ACTIVE, current[C], current[A], 2000)


@pytest.mark.parametrize("amount", [0, -100, 20.5])
def test_payment_amount_must_be_positive_cents(amount):
    current = balances()
    with pytest.raises(InvalidInputError):
        validate_new_payment(SETTLING, current[C], current[A], amount)


def test_payer_and_payee_must_differ():
    current = balances()
    with pytest.raises(InvalidInputError):
        validate_new_payment(SETTLING, current[C], current[C], 100)


def test_payment_cannot_exceed_payer_quota():
    current = balances()
    with pytest.raises(StateConflictError, match="付款人"):
        validate_new_payment(SETTLING, current[C], current[A], 4001)


def test_payment_cannot_exceed_payee_quota():
    # B 只欠 10 元，但 C 欠 40 元；C 向 B 付款时 B 并无应收
    current = balances()
    with pytest.raises(StateConflictError, match="收款人"):
        validate_new_payment(SETTLING, current[C], current[B], 100)


def test_t10_second_payment_exceeding_reserved_quota_is_rejected():
    # C 欠 40 元，已有一笔 30 元待确认，再登记 30 元会超额占用
    current = balances([PaymentEntry(C, A, 3000, PaymentStatus.PENDING)])
    with pytest.raises(StateConflictError):
        validate_new_payment(SETTLING, current[C], current[A], 3000)
    validate_new_payment(SETTLING, current[C], current[A], 1000)


def test_t09_retry_with_same_content_is_accepted():
    check_request_retry(A, 2000, A, 2000)


@pytest.mark.parametrize(("payee", "amount"), [(B, 2000), (A, 2001)])
def test_t09_request_id_reuse_with_different_content_conflicts(payee, amount):
    with pytest.raises(StateConflictError):
        check_request_retry(A, 2000, payee, amount)


@pytest.mark.parametrize(
    ("action", "actor", "target"),
    [
        (PaymentAction.CONFIRM, A, PaymentStatus.CONFIRMED),
        (PaymentAction.REJECT, A, PaymentStatus.REJECTED),
        (PaymentAction.CANCEL, C, PaymentStatus.CANCELLED),
    ],
)
def test_pending_payment_transitions(action, actor, target):
    result = apply_payment_action(SETTLING, PaymentStatus.PENDING, action, actor, C, A)
    assert result == PaymentTransition(target, changed=True)


@pytest.mark.parametrize(
    ("action", "actor"),
    [
        (PaymentAction.CONFIRM, C),  # 付款人不能自己确认
        (PaymentAction.CONFIRM, B),  # 无关成员，包括活动创建者
        (PaymentAction.REJECT, C),
        (PaymentAction.CANCEL, A),  # 收款人不能撤销
    ],
)
def test_t12_wrong_actor_is_forbidden(action, actor):
    with pytest.raises(PermissionDeniedError):
        apply_payment_action(SETTLING, PaymentStatus.PENDING, action, actor, C, A)


@pytest.mark.parametrize(
    ("status", "action", "actor"),
    [
        (PaymentStatus.CONFIRMED, PaymentAction.CONFIRM, A),
        (PaymentStatus.REJECTED, PaymentAction.REJECT, A),
        (PaymentStatus.CANCELLED, PaymentAction.CANCEL, C),
    ],
)
def test_t09_repeated_action_is_idempotent(status, action, actor):
    result = apply_payment_action(SETTLING, status, action, actor, C, A)
    assert result == PaymentTransition(status, changed=False)


def test_t09_repeated_confirm_after_activity_settled_is_idempotent():
    result = apply_payment_action(
        ActivityStatus.SETTLED, PaymentStatus.CONFIRMED, PaymentAction.CONFIRM, A, C, A
    )
    assert result.changed is False


@pytest.mark.parametrize(
    ("status", "action", "actor"),
    [
        (PaymentStatus.CANCELLED, PaymentAction.CONFIRM, A),
        (PaymentStatus.CONFIRMED, PaymentAction.CANCEL, C),
        (PaymentStatus.REJECTED, PaymentAction.CONFIRM, A),
        (PaymentStatus.CONFIRMED, PaymentAction.REJECT, A),
    ],
)
def test_t11_terminal_status_cannot_change(status, action, actor):
    with pytest.raises(StateConflictError):
        apply_payment_action(SETTLING, status, action, actor, C, A)


def test_pending_payment_cannot_change_outside_settling():
    with pytest.raises(StateConflictError):
        apply_payment_action(
            ActivityStatus.ARCHIVED, PaymentStatus.PENDING, PaymentAction.CONFIRM, A, C, A
        )
