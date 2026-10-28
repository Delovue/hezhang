from uuid import uuid4

from starlette.exceptions import HTTPException

from app.api import auth
from app.database import transaction
from app.models import Activity, ActivityStatus
from tests.conftest import PASSWORD, register_actor
from tests.test_expenses import create


def assert_error(response, status, code, *, retryable=False):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"detail", "code", "retryable"}
    assert body["code"] == code and body["retryable"] is retryable
    return body


def test_auth_error_codes_and_challenge_header(client):
    register_actor(client, "alice")
    missing = client.get("/api/v1/auth/me")
    assert_error(missing, 401, "AUTHENTICATION_REQUIRED")
    assert missing.headers["www-authenticate"] == "Bearer"
    invalid = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "wrong-pass"}
    )
    assert_error(invalid, 401, "INVALID_CREDENTIALS")
    assert invalid.headers["www-authenticate"] == "Bearer"
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ALICE",
            "display_name": "另一个人",
            "password": PASSWORD,
        },
    )
    assert_error(duplicate, 409, "USERNAME_EXISTS")


def test_permission_codes_do_not_reveal_foreign_activity(
    client, actors, outsider, group, expense_data
):
    base = f"/api/v1/activities/{group['id']}"
    foreign = client.get(base, headers=outsider["headers"])
    missing = client.get("/api/v1/activities/99999", headers=outsider["headers"])
    assert_error(foreign, 404, "ACTIVITY_NOT_FOUND")
    assert foreign.json() == missing.json()
    assert_error(
        client.patch(base, headers=actors["bob"]["headers"], json={"name": "越权"}),
        403,
        "ACTIVITY_OWNER_REQUIRED",
    )
    assert_error(
        client.post(
            "/api/v1/activities/join",
            headers=actors["bob"]["headers"],
            json={"invite_code": "nonexistent"},
        ),
        404,
        "INVITE_INVALID",
    )
    expense = create(client, actors, group, expense_data, actor="bob")
    assert_error(
        client.patch(
            f"{base}/expenses/{expense['id']}",
            headers=actors["charlie"]["headers"],
            json={"version": 1, "title": "越权"},
        ),
        403,
        "EXPENSE_EDIT_FORBIDDEN",
    )
    assert_error(
        client.get(base + "/expenses/99999", headers=actors["alice"]["headers"]),
        404,
        "EXPENSE_NOT_FOUND",
    )


def test_conflict_codes_distinguish_required_recovery(client, actors, group, expense_data):
    payload = expense_data | {"request_id": str(uuid4())}
    expense = create(client, actors, group, payload)
    base = f"/api/v1/activities/{group['id']}/expenses"
    path = f"{base}/{expense['id']}"
    headers = actors["alice"]["headers"]
    assert (
        client.patch(path, headers=headers, json={"version": 1, "title": "已修改"}).status_code
        == 200
    )
    assert_error(
        client.patch(path, headers=headers, json={"version": 1, "title": "过时"}),
        409,
        "EXPENSE_VERSION_CONFLICT",
    )
    assert_error(
        client.post(base, headers=headers, json=payload | {"amount_cents": 12000}),
        409,
        "REQUEST_ID_CONFLICT",
    )
    assert client.delete(path, headers=headers, params={"version": 2}).status_code == 204
    assert_error(client.post(base, headers=headers, json=payload), 409, "EXPENSE_DELETED")
    with transaction(client.app.state.engine, write=True) as session:
        session.get(Activity, group["id"]).status = ActivityStatus.SETTLING
    assert_error(
        client.post(base, headers=headers, json=payload | {"request_id": str(uuid4())}),
        409,
        "ACTIVITY_LOCKED",
    )


def test_validation_error_keeps_field_locations_without_echoing_input(client):
    secret = "private-password-marker"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "!",
            "display_name": "用户",
            "password": secret,
        },
    )
    body = assert_error(response, 422, "VALIDATION_ERROR")
    assert body["detail"][0]["loc"] == ["body", "username"]
    assert all(set(issue) == {"loc", "msg", "type"} for issue in body["detail"])
    assert secret not in response.text


def test_query_and_expense_validation_codes(client, actors, group, expense_data):
    base = f"/api/v1/activities/{group['id']}"
    headers = actors["alice"]["headers"]
    for path, params in [
        ("/api/v1/activities", {"before_id": 1, "offset": 1}),
        (base + "/audit-logs", {"object_id": 1}),
        (base + "/audit-logs", {"before_id": 1, "offset": 1}),
        (base + "/expenses", {"start_date": "2026-10-28", "end_date": "2026-10-27"}),
    ]:
        assert_error(client.get(path, headers=headers, params=params), 422, "INVALID_QUERY")
    assert_error(
        client.post(
            base + "/expenses", headers=headers, json=expense_data | {"payer_member_id": 99999}
        ),
        422,
        "EXPENSE_MEMBER_MISMATCH",
    )
    exact = create(
        client,
        actors,
        group,
        expense_data
        | {
            "split_method": "EXACT",
            "participants": [{"member_id": group["member_ids"]["alice"], "amount_cents": 10000}],
        },
    )
    assert_error(
        client.patch(
            f"{base}/expenses/{exact['id']}",
            headers=headers,
            json={"version": 1, "amount_cents": 12000},
        ),
        422,
        "INVALID_EXPENSE",
    )


def test_framework_http_errors_keep_status_and_headers(client, monkeypatch):
    assert_error(client.get("/does-not-exist"), 404, "NOT_FOUND")
    wrong_method = client.post("/api/v1/auth/me")
    assert_error(wrong_method, 405, "METHOD_NOT_ALLOWED")
    assert "GET" in wrong_method.headers["allow"]

    def fail_verification(*_args):
        raise HTTPException(418, "自定义 HTTP 错误", headers={"X-Test-Header": "kept"})

    monkeypatch.setattr(auth, "verify_password", fail_verification)
    response = client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    assert_error(response, 418, "HTTP_ERROR")
    assert response.headers["x-test-header"] == "kept"
