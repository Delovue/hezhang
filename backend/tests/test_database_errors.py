from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text

from app.database import transaction
from app.main import create_app
from app.models import User
from app.services import expense as expense_service
from tests.test_api_errors import assert_error
from tests.test_expense_requests import ledger_counts


def test_real_write_lock_returns_retry_hint_then_allows_same_request(
    client, actors, group, expense_data
):
    engine = client.app.state.engine
    payload = expense_data | {"request_id": str(uuid4())}
    path = f"/api/v1/activities/{group['id']}/expenses"
    origin = "http://localhost:5173"
    headers = actors["alice"]["headers"] | {"Origin": origin}
    before = ledger_counts(client)

    def shorten_busy_wait(connection, _record):
        connection.execute("PRAGMA busy_timeout=50")

    event.listen(engine, "connect", shorten_busy_wait)
    try:
        with transaction(engine, write=True) as locked:
            locked.scalar(select(User.id).limit(1))  # Acquire a real independent SQLite write lock.
            blocked = client.post(path, headers=headers, json=payload)
        assert_error(blocked, 409, "DATABASE_BUSY", retryable=True)
        assert blocked.headers["retry-after"] == "1"
        assert blocked.headers["access-control-allow-origin"] == origin
        assert "retry-after" in blocked.headers["access-control-expose-headers"].lower()
        assert ledger_counts(client) == before
        assert client.post(path, headers=headers, json=payload).status_code == 201
        assert client.post(path, headers=headers, json=payload).status_code == 200
    finally:
        event.remove(engine, "connect", shorten_busy_wait)


@pytest.mark.parametrize("failure", ["integrity", "operational"])
def test_database_failure_is_sanitized_and_rolls_back_all_rows(
    client, actors, group, expense_data, monkeypatch, failure
):
    before = ledger_counts(client)
    original = expense_service.record_audit

    def fail_after_writes(session, **kwargs):
        original(session, **kwargs)
        if failure == "integrity":
            session.add(
                User(
                    username="alice", display_name="private-db-marker", password_hash="secret-hash"
                )
            )
            session.flush()
        else:
            session.execute(text("SELECT * FROM private_missing_table_marker"))

    monkeypatch.setattr(expense_service, "record_audit", fail_after_writes)
    response = client.post(
        f"/api/v1/activities/{group['id']}/expenses",
        headers=actors["alice"]["headers"],
        json=expense_data | {"request_id": str(uuid4())},
    )
    status, code = (409, "DATA_CONFLICT") if failure == "integrity" else (503, "DATABASE_NOT_READY")
    assert_error(response, status, code)
    assert "retry-after" not in response.headers
    for secret in [
        "private-db-marker",
        "secret-hash",
        "private_missing_table_marker",
        "INSERT INTO",
        "SELECT *",
    ]:
        assert secret not in response.text
    assert ledger_counts(client) == before


@pytest.mark.parametrize("origin", ["http://localhost:5173", "https://untrusted.example", None])
def test_unexpected_failure_returns_safe_json_and_respects_cors(
    client, settings, actors, group, expense_data, monkeypatch, origin
):
    original = expense_service.record_audit
    before = ledger_counts(client)

    def fail_after_audit(session, **kwargs):
        original(session, **kwargs)
        raise RuntimeError("private-debug-marker")

    monkeypatch.setattr(expense_service, "record_audit", fail_after_audit)
    headers = actors["alice"]["headers"] | ({"Origin": origin} if origin else {})
    with TestClient(create_app(settings), raise_server_exceptions=False) as actual_http:
        response = actual_http.post(
            f"/api/v1/activities/{group['id']}/expenses",
            headers=headers,
            json=expense_data | {"request_id": str(uuid4())},
        )
    assert_error(response, 500, "INTERNAL_ERROR")
    assert "private-debug-marker" not in response.text
    if origin == "http://localhost:5173":
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["vary"] == "Origin"
    else:
        assert "access-control-allow-origin" not in response.headers
    assert "retry-after" not in response.headers
    assert ledger_counts(client) == before
