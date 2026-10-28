from uuid import uuid4

import pytest


@pytest.fixture
def settling(client, actors, trip):
    response = client.post(
        f"/api/v1/activities/{trip['id']}/start-settlement", headers=actors["alice"]["headers"]
    )
    assert response.json()["status"] == "SETTLING"
    return trip


def pay(client, actors, group, payer, payee, amount, request_id=None):
    return client.post(
        f"/api/v1/activities/{group['id']}/payments",
        headers=actors[payer]["headers"],
        json={
            "payee_member_id": group["member_ids"][payee],
            "amount_cents": amount,
            "request_id": request_id or str(uuid4()),
        },
    )


def ledger(client, actors, group, path, actor="alice"):
    return client.get(
        f"/api/v1/activities/{group['id']}/{path}", headers=actors[actor]["headers"]
    ).json()


def balance_rows(client, actors, group):
    names = {member_id: name for name, member_id in group["member_ids"].items()}
    return {names[row["member_id"]]: row for row in ledger(client, actors, group, "balances")}


def test_t07_pending_payment_reserves_quota_without_changing_balance(client, actors, settling):
    response = pay(client, actors, settling, "charlie", "alice", 2000)

    assert response.status_code == 201, response.text
    payment = response.json()
    assert payment["status"] == "PENDING"
    assert payment["payer_member_id"] == settling["member_ids"]["charlie"]
    rows = balance_rows(client, actors, settling)
    assert rows["charlie"]["balance_cents"] == -4000
    assert rows["alice"]["balance_cents"] == 5000
    assert rows["charlie"]["available_out_cents"] == 2000
    assert rows["alice"]["available_in_cents"] == 3000
    ids = settling["member_ids"]
    assert ledger(client, actors, settling, "settlement-suggestions") == [
        {"payer_member_id": ids["charlie"], "payee_member_id": ids["alice"], "amount_cents": 2000},
        {"payer_member_id": ids["bob"], "payee_member_id": ids["alice"], "amount_cents": 1000},
    ]


def test_payment_history_has_no_request_id(client, actors, settling):
    payment = pay(client, actors, settling, "charlie", "alice", 2000).json()
    history = ledger(client, actors, settling, "audit-logs?object_type=payment")

    assert [(row["action"], row["object_id"]) for row in history] == [
        ("PAYMENT_CREATED", payment["id"])
    ]
    assert "request_id" not in history[0]["after"]


def test_cannot_register_payment_before_settlement(client, actors, trip):
    assert pay(client, actors, trip, "charlie", "alice", 2000).status_code == 409


@pytest.mark.parametrize(
    ("payer", "payee", "amount"),
    [
        ("charlie", "alice", 4001),  # 超过付款人应付
        ("charlie", "bob", 100),  # bob 没有应收
        ("alice", "bob", 100),  # alice 没有应付
    ],
)
def test_payment_cannot_exceed_quota(client, actors, settling, payer, payee, amount):
    assert pay(client, actors, settling, payer, payee, amount).status_code == 409
    assert ledger(client, actors, settling, "payments") == []


def test_cannot_pay_self(client, actors, settling):
    assert pay(client, actors, settling, "charlie", "charlie", 100).status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": 0},
        {"amount_cents": 20.5},
        {"amount_cents": "2000"},
        {"amount_cents": True},
        {"request_id": "not-a-uuid"},
        {"request_id": None},
        {"payer_member_id": 1},
    ],
)
def test_invalid_payment_input(client, actors, settling, changes):
    payload = {
        "payee_member_id": settling["member_ids"]["alice"],
        "amount_cents": 2000,
        "request_id": str(uuid4()),
    } | changes
    response = client.post(
        f"/api/v1/activities/{settling['id']}/payments",
        headers=actors["charlie"]["headers"],
        json=payload,
    )
    assert response.status_code == 422


def test_payee_must_be_member(client, actors, outsider, settling):
    other = client.post(
        "/api/v1/activities", headers=outsider["headers"], json={"name": "其他活动"}
    ).json()
    foreign = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=outsider["headers"]
    ).json()[0]["id"]
    response = client.post(
        f"/api/v1/activities/{settling['id']}/payments",
        headers=actors["charlie"]["headers"],
        json={"payee_member_id": foreign, "amount_cents": 100, "request_id": str(uuid4())},
    )
    assert response.status_code == 422


def test_t09_retry_returns_original_payment(client, actors, settling):
    request_id = str(uuid4())
    first = pay(client, actors, settling, "charlie", "alice", 2000, request_id)
    retry = pay(client, actors, settling, "charlie", "alice", 2000, request_id)

    assert (first.status_code, retry.status_code) == (201, 200)
    assert retry.json() == first.json()
    assert len(ledger(client, actors, settling, "payments")) == 1
    assert len(ledger(client, actors, settling, "audit-logs?object_type=payment")) == 1
    assert balance_rows(client, actors, settling)["charlie"]["pending_out_cents"] == 2000


@pytest.mark.parametrize(("payee", "amount"), [("alice", 1000), ("bob", 2000)])
def test_t09_reusing_request_id_with_other_content_conflicts(
    client, actors, settling, payee, amount
):
    request_id = str(uuid4())
    pay(client, actors, settling, "charlie", "alice", 2000, request_id)

    assert pay(client, actors, settling, "charlie", payee, amount, request_id).status_code == 409
    assert len(ledger(client, actors, settling, "payments")) == 1


def test_request_id_is_scoped_to_payer(client, actors, settling):
    request_id = str(uuid4())
    assert pay(client, actors, settling, "charlie", "alice", 2000, request_id).status_code == 201
    assert pay(client, actors, settling, "bob", "alice", 1000, request_id).status_code == 201


def test_t10_second_payment_cannot_overuse_reserved_quota(client, actors, settling):
    assert pay(client, actors, settling, "charlie", "alice", 3000).status_code == 201
    assert pay(client, actors, settling, "charlie", "alice", 3000).status_code == 409
    assert pay(client, actors, settling, "charlie", "alice", 1000).status_code == 201


def test_list_payments_newest_first_with_status_filter(client, actors, settling):
    first = pay(client, actors, settling, "charlie", "alice", 1000).json()
    second = pay(client, actors, settling, "bob", "alice", 1000).json()

    assert [p["id"] for p in ledger(client, actors, settling, "payments")] == [
        second["id"],
        first["id"],
    ]
    assert len(ledger(client, actors, settling, "payments?status=PENDING")) == 2
    assert ledger(client, actors, settling, "payments?status=CONFIRMED") == []


def test_t12_outsider_cannot_read_or_register_payments(client, actors, outsider, settling):
    path = f"/api/v1/activities/{settling['id']}/payments"
    assert client.get(path, headers=outsider["headers"]).status_code == 404
    response = client.post(
        path,
        headers=outsider["headers"],
        json={
            "payee_member_id": settling["member_ids"]["alice"],
            "amount_cents": 100,
            "request_id": str(uuid4()),
        },
    )
    assert response.status_code == 404
