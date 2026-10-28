from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import transaction
from app.main import create_app
from app.models import Activity, ActivityStatus, AuditLog, Expense, ExpenseRequest, ExpenseShare
from app.services import expense as expense_service


@pytest.fixture
def retry_data(expense_data):
    return expense_data | {"request_id": str(uuid4())}


def submit(client, group, actor, data):
    return client.post(
        f"/api/v1/activities/{group['id']}/expenses", headers=actor["headers"], json=data
    )


def ledger_counts(client):
    with transaction(client.app.state.engine) as session:
        return {
            model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in [Expense, ExpenseShare, ExpenseRequest, AuditLog]
        }


def test_same_request_is_recorded_once(client, actors, group, retry_data):
    created = submit(client, group, actors["alice"], retry_data)
    assert created.status_code == 201, created.text
    counts = ledger_counts(client)
    assert counts == {"expenses": 1, "expense_shares": 3, "expense_requests": 1, "audit_logs": 4}
    for _ in range(2):
        replayed = submit(client, group, actors["alice"], retry_data)
        assert replayed.status_code == 200, replayed.text
        assert replayed.json() == created.json()
    assert ledger_counts(client) == counts
    history = client.get(
        f"/api/v1/activities/{group['id']}/audit-logs", headers=actors["alice"]["headers"]
    ).json()
    assert retry_data["request_id"] not in str(history)
    assert "request_id" not in created.json() and "payload_hash" not in created.json()


@pytest.mark.parametrize("method", ["EQUAL", "EXACT", "SHARES"])
def test_equivalent_payloads_share_one_request(client, actors, group, retry_data, method):
    ids = list(group["member_ids"].values())
    participants = [{"member_id": member_id} for member_id in ids]
    if method == "EXACT":
        participants = [
            {"member_id": mid, "amount_cents": amount}
            for mid, amount in zip(ids, [3334, 3333, 3333], strict=True)
        ]
    elif method == "SHARES":
        participants = [{"member_id": mid, "shares": index + 1} for index, mid in enumerate(ids)]
    first_payload = retry_data | {
        "split_method": method,
        "participants": participants,
        "title": "  餐费  ",
    }
    first_payload.pop("notes")
    first = submit(client, group, actors["alice"], first_payload)
    assert first.status_code == 201
    equivalent = first_payload | {
        "request_id": first_payload["request_id"].upper(),
        "title": "餐费",
        "notes": None,
        "participants": list(reversed(participants)),
    }
    retry = submit(client, group, actors["alice"], equivalent)
    assert retry.status_code == 200 and retry.json() == first.json()
    assert ledger_counts(client)["expense_requests"] == 1


def test_reusing_key_with_changed_business_content_conflicts(client, actors, group, retry_data):
    created = submit(client, group, actors["alice"], retry_data)
    assert created.status_code == 201
    before = ledger_counts(client)
    for change in [
        {"amount_cents": 11000},
        {"title": "新餐费"},
        {"category": "交通"},
        {"expense_date": "2026-10-28"},
        {"notes": "不同备注"},
        {"payer_member_id": group["member_ids"]["bob"]},
        {"participants": [{"member_id": group["member_ids"]["bob"]}]},
        {
            "split_method": "SHARES",
            "participants": [
                {"member_id": member_id, "shares": 1} for member_id in group["member_ids"].values()
            ],
        },
    ]:
        response = submit(client, group, actors["alice"], retry_data | change)
        assert response.status_code == 409, (change, response.text)
    assert ledger_counts(client) == before
    path = f"/api/v1/activities/{group['id']}/expenses/{created.json()['id']}"
    assert client.get(path, headers=actors["alice"]["headers"]).json() == created.json()


def test_requests_without_keys_keep_existing_create_behavior(client, actors, group, expense_data):
    ids = []
    for payload in [expense_data, expense_data, expense_data | {"request_id": None}]:
        created = submit(client, group, actors["alice"], payload)
        assert created.status_code == 201
        ids.append(created.json()["id"])
    assert len(set(ids)) == 3
    assert ledger_counts(client)["expense_requests"] == 0


def test_keys_are_scoped_to_activity_and_recording_user(
    client, actors, outsider, group, retry_data
):
    alice = submit(client, group, actors["alice"], retry_data)
    bob = submit(client, group, actors["bob"], retry_data)
    assert alice.status_code == bob.status_code == 201
    assert alice.json()["id"] != bob.json()["id"]
    assert submit(client, group, actors["bob"], retry_data).json() == bob.json()
    other = client.post(
        "/api/v1/activities", headers=actors["alice"]["headers"], json={"name": "另一次旅行"}
    ).json()
    mid = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=actors["alice"]["headers"]
    ).json()[0]["id"]
    other_created = submit(
        client,
        other,
        actors["alice"],
        retry_data
        | {
            "payer_member_id": mid,
            "participants": [{"member_id": mid}],
        },
    )
    assert other_created.status_code == 201
    assert submit(client, group, outsider, retry_data).status_code == 404
    assert ledger_counts(client)["expense_requests"] == 3


@pytest.mark.parametrize("different_content", [False, True])
def test_concurrent_requests_have_one_creation(
    client, actors, group, retry_data, different_content
):
    barrier = Barrier(2)
    second_payload = retry_data | ({"amount_cents": 12000} if different_content else {})

    def post(payload):
        barrier.wait(timeout=5)
        return submit(client, group, actors["alice"], payload)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(post, [retry_data, second_payload]))
    expected = [201, 409] if different_content else [200, 201]
    assert sorted(response.status_code for response in responses) == expected
    if not different_content:
        assert responses[0].json() == responses[1].json()
    assert ledger_counts(client) == {
        "expenses": 1,
        "expense_shares": 3,
        "expense_requests": 1,
        "audit_logs": 4,
    }


def test_audit_failure_rolls_back_request_key_and_allows_retry(
    client, actors, group, retry_data, monkeypatch
):
    original = expense_service.record_audit
    before = ledger_counts(client)

    def fail_after_audit(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected failure after audit flush")

    with monkeypatch.context() as patch:
        patch.setattr(expense_service, "record_audit", fail_after_audit)
        with pytest.raises(RuntimeError, match="injected failure"):
            submit(client, group, actors["alice"], retry_data)
    assert ledger_counts(client) == before
    assert submit(client, group, actors["alice"], retry_data).status_code == 201
    assert submit(client, group, actors["alice"], retry_data).status_code == 200


def test_rejected_input_does_not_reserve_the_request_key(client, actors, group, retry_data):
    for change in [{"amount_cents": 0}, {"payer_member_id": 99999}]:
        assert submit(client, group, actors["alice"], retry_data | change).status_code == 422
    assert ledger_counts(client)["expense_requests"] == 0
    assert submit(client, group, actors["alice"], retry_data).status_code == 201


def test_retry_after_edit_returns_current_expense_without_reverting(
    client, actors, group, retry_data
):
    expense = submit(client, group, actors["alice"], retry_data).json()
    path = f"/api/v1/activities/{group['id']}/expenses/{expense['id']}"
    updated = client.patch(
        path, headers=actors["alice"]["headers"], json={"version": 1, "amount_cents": 12000}
    )
    assert updated.status_code == 200
    before = ledger_counts(client)
    retry = submit(client, group, actors["alice"], retry_data)
    assert retry.status_code == 200 and retry.json() == updated.json()
    assert (
        submit(client, group, actors["alice"], retry_data | {"amount_cents": 12000}).status_code
        == 409
    )
    assert (
        client.patch(
            path,
            headers=actors["alice"]["headers"],
            json={
                "version": 2,
                "request_id": str(uuid4()),
            },
        ).status_code
        == 422
    )
    assert ledger_counts(client) == before


def test_retry_after_delete_does_not_recreate_expense(client, actors, group, retry_data):
    expense = submit(client, group, actors["alice"], retry_data).json()
    path = f"/api/v1/activities/{group['id']}/expenses/{expense['id']}"
    assert (
        client.delete(path, headers=actors["alice"]["headers"], params={"version": 1}).status_code
        == 204
    )
    before = ledger_counts(client)
    assert submit(client, group, actors["alice"], retry_data).status_code == 409
    assert ledger_counts(client) == before
    assert client.get(path, headers=actors["alice"]["headers"]).status_code == 404
    replacement = submit(client, group, actors["alice"], retry_data | {"request_id": str(uuid4())})
    assert replacement.status_code == 201 and replacement.json()["id"] != expense["id"]


@pytest.mark.parametrize(
    "status", [ActivityStatus.SETTLING, ActivityStatus.SETTLED, ActivityStatus.ARCHIVED]
)
def test_retry_after_sealing_is_read_only(client, actors, group, retry_data, status):
    created = submit(client, group, actors["alice"], retry_data)
    assert created.status_code == 201
    with transaction(client.app.state.engine, write=True) as session:
        session.get(Activity, group["id"]).status = status
    before = ledger_counts(client)
    retry = submit(client, group, actors["alice"], retry_data)
    assert retry.status_code == 200 and retry.json() == created.json()
    assert (
        submit(
            client, group, actors["alice"], retry_data | {"request_id": str(uuid4())}
        ).status_code
        == 409
    )
    assert ledger_counts(client) == before


def test_request_records_survive_application_recreation(
    client, settings, actors, group, retry_data
):
    created = submit(client, group, actors["alice"], retry_data)
    assert created.status_code == 201
    with TestClient(create_app(settings)) as reopened:
        retry = submit(reopened, group, actors["alice"], retry_data)
        assert retry.status_code == 200 and retry.json() == created.json()
    assert ledger_counts(client)["expenses"] == 1


def test_request_id_must_be_uuid4(client, actors, group, retry_data):
    for invalid in ["", "not-a-uuid", "00000000-0000-1000-8000-000000000001", 123, True]:
        assert (
            submit(client, group, actors["alice"], retry_data | {"request_id": invalid}).status_code
            == 422
        )
    assert ledger_counts(client)["expenses"] == 0
