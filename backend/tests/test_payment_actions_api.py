import pytest

from tests.test_expenses import create
from tests.test_payments_api import balance_rows, ledger, pay


@pytest.fixture
def settling(client, actors, trip):
    client.post(
        f"/api/v1/activities/{trip['id']}/start-settlement", headers=actors["alice"]["headers"]
    )
    return trip


def act(client, actors, group, payment, action, actor):
    return client.post(
        f"/api/v1/activities/{group['id']}/payments/{payment['id']}/{action}",
        headers=actors[actor]["headers"],
    )


def activity_status(client, actors, group):
    return client.get(
        f"/api/v1/activities/{group['id']}", headers=actors["alice"]["headers"]
    ).json()["status"]


def test_t08_confirmed_payment_updates_balances(client, actors, settling):
    payment = pay(client, actors, settling, "charlie", "alice", 2000).json()
    response = act(client, actors, settling, payment, "confirm", "alice")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CONFIRMED"
    rows = balance_rows(client, actors, settling)
    assert {name: row["balance_cents"] for name, row in rows.items()} == {
        "alice": 3000,
        "bob": -1000,
        "charlie": -2000,
    }
    assert rows["charlie"]["confirmed_out_cents"] == 2000
    assert rows["charlie"]["pending_out_cents"] == 0


@pytest.mark.parametrize(("action", "actor"), [("reject", "alice"), ("cancel", "charlie")])
def test_reject_or_cancel_releases_quota(client, actors, settling, action, actor):
    payment = pay(client, actors, settling, "charlie", "alice", 2000).json()
    response = act(client, actors, settling, payment, action, actor)

    assert response.json()["status"] == {"reject": "REJECTED", "cancel": "CANCELLED"}[action]
    rows = balance_rows(client, actors, settling)
    assert rows["charlie"]["balance_cents"] == -4000
    assert rows["charlie"]["available_out_cents"] == 4000
    assert rows["alice"]["available_in_cents"] == 5000


@pytest.mark.parametrize(
    ("action", "actor"),
    [
        ("confirm", "charlie"),  # 付款人不能自己确认
        ("confirm", "bob"),  # 无关成员
        ("reject", "charlie"),
        ("cancel", "alice"),  # 收款人不能撤销
    ],
)
def test_t12_wrong_actor_is_forbidden(client, actors, settling, action, actor):
    payment = pay(client, actors, settling, "charlie", "alice", 2000).json()

    assert act(client, actors, settling, payment, action, actor).status_code == 403
    assert ledger(client, actors, settling, "payments")[0]["status"] == "PENDING"


def test_t12_creator_cannot_confirm_for_payee(client, actors, group, expense_data):
    # bob 垫付、只由 charlie 承担，收款人是 bob 而不是创建者 alice
    ids = group["member_ids"]
    create(
        client,
        actors,
        group,
        expense_data
        | {"payer_member_id": ids["bob"], "participants": [{"member_id": ids["charlie"]}]},
        actor="bob",
    )
    client.post(
        f"/api/v1/activities/{group['id']}/start-settlement", headers=actors["alice"]["headers"]
    )
    payment = pay(client, actors, group, "charlie", "bob", 10000).json()

    assert act(client, actors, group, payment, "confirm", "alice").status_code == 403
    assert act(client, actors, group, payment, "confirm", "bob").status_code == 200


def test_t09_repeated_confirm_does_not_double_count(client, actors, settling):
    payment = pay(client, actors, settling, "charlie", "alice", 2000).json()
    first = act(client, actors, settling, payment, "confirm", "alice")
    again = act(client, actors, settling, payment, "confirm", "alice")

    assert (first.status_code, again.status_code) == (200, 200)
    assert again.json() == first.json()
    assert balance_rows(client, actors, settling)["alice"]["balance_cents"] == 3000
    history = ledger(client, actors, settling, "audit-logs?action=PAYMENT_CONFIRMED")
    assert len(history) == 1


@pytest.mark.parametrize(
    ("first", "first_actor", "second", "second_actor"),
    [
        ("confirm", "alice", "cancel", "charlie"),
        ("cancel", "charlie", "confirm", "alice"),
        ("reject", "alice", "confirm", "alice"),
        ("confirm", "alice", "reject", "alice"),
    ],
)
def test_t11_terminal_payment_cannot_change(
    client, actors, settling, first, first_actor, second, second_actor
):
    payment = pay(client, actors, settling, "charlie", "alice", 2000).json()
    assert act(client, actors, settling, payment, first, first_actor).status_code == 200

    assert act(client, actors, settling, payment, second, second_actor).status_code == 409


def test_full_settlement_marks_activity_settled_then_archive(client, actors, settling):
    charlie = pay(client, actors, settling, "charlie", "alice", 4000).json()
    bob = pay(client, actors, settling, "bob", "alice", 1000).json()
    act(client, actors, settling, charlie, "confirm", "alice")
    assert activity_status(client, actors, settling) == "SETTLING"

    act(client, actors, settling, bob, "confirm", "alice")

    assert activity_status(client, actors, settling) == "SETTLED"
    assert all(row["balance_cents"] == 0 for row in balance_rows(client, actors, settling).values())
    assert ledger(client, actors, settling, "settlement-suggestions") == []
    history = ledger(client, actors, settling, "audit-logs?object_type=activity")
    assert history[0]["action"] == "ACTIVITY_SETTLED"
    archived = client.post(
        f"/api/v1/activities/{settling['id']}/archive", headers=actors["alice"]["headers"]
    )
    assert archived.json()["status"] == "ARCHIVED"


def test_repeat_confirm_after_activity_settled_is_idempotent(client, actors, settling):
    charlie = pay(client, actors, settling, "charlie", "alice", 4000).json()
    bob = pay(client, actors, settling, "bob", "alice", 1000).json()
    act(client, actors, settling, charlie, "confirm", "alice")
    act(client, actors, settling, bob, "confirm", "alice")

    assert act(client, actors, settling, bob, "confirm", "alice").status_code == 200
    assert activity_status(client, actors, settling) == "SETTLED"


def test_payment_from_other_activity_is_not_found(client, actors, outsider, settling):
    payment = pay(client, actors, settling, "charlie", "alice", 2000).json()
    other = client.post(
        "/api/v1/activities", headers=outsider["headers"], json={"name": "其他活动"}
    ).json()
    response = client.post(
        f"/api/v1/activities/{other['id']}/payments/{payment['id']}/confirm",
        headers=outsider["headers"],
    )
    assert response.status_code == 404
