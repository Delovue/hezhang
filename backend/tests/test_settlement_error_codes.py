"""丙的接口错误码：前端按 code 分支处理，不依赖中文提示。"""

from uuid import uuid4

import pytest

from app.errors import ErrorCode
from tests.test_api_errors import assert_error
from tests.test_payments_api import pay


def post(client, actors, group, path, actor="alice", **kwargs):
    return client.post(
        f"/api/v1/activities/{group['id']}/{path}", headers=actors[actor]["headers"], **kwargs
    )


@pytest.fixture
def pending(client, actors, settling):
    return pay(client, actors, settling, "charlie", "alice", 2000).json()


def test_lifecycle_error_codes(client, actors, trip):
    assert_error(
        post(client, actors, trip, "start-settlement", "bob"), 403, "ACTIVITY_OWNER_REQUIRED"
    )
    assert_error(post(client, actors, trip, "archive"), 409, "ACTIVITY_NOT_SETTLED")
    post(client, actors, trip, "start-settlement")
    assert_error(post(client, actors, trip, "start-settlement"), 409, "SETTLEMENT_ALREADY_STARTED")
    assert_error(post(client, actors, trip, "archive", "bob"), 403, "ACTIVITY_OWNER_REQUIRED")


def test_payments_closed_before_settlement(client, actors, trip):
    assert_error(pay(client, actors, trip, "charlie", "alice", 2000), 409, "PAYMENTS_CLOSED")


def test_payment_input_error_codes(client, actors, settling):
    assert_error(pay(client, actors, settling, "charlie", "charlie", 100), 422, "INVALID_PAYMENT")
    assert_error(
        pay(client, actors, settling, "charlie", "alice", 4001), 409, "PAYMENT_QUOTA_EXCEEDED"
    )
    request_id = str(uuid4())
    pay(client, actors, settling, "charlie", "alice", 1000, request_id)
    assert_error(
        pay(client, actors, settling, "charlie", "alice", 1500, request_id),
        409,
        "REQUEST_ID_CONFLICT",
    )


def test_foreign_payee_error_code(client, actors, outsider, settling):
    other = client.post(
        "/api/v1/activities", headers=outsider["headers"], json={"name": "其他活动"}
    ).json()
    foreign = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=outsider["headers"]
    ).json()[0]["id"]
    response = post(
        client,
        actors,
        settling,
        "payments",
        "charlie",
        json={"payee_member_id": foreign, "amount_cents": 100, "request_id": str(uuid4())},
    )
    assert_error(response, 422, "INVALID_PAYMENT")


def test_payment_action_error_codes(client, actors, settling, pending):
    path = f"payments/{pending['id']}"
    assert_error(
        post(client, actors, settling, f"{path}/confirm", "charlie"),
        403,
        "PAYMENT_ACTION_FORBIDDEN",
    )
    assert_error(
        post(client, actors, settling, f"{path}/cancel", "alice"), 403, "PAYMENT_ACTION_FORBIDDEN"
    )
    post(client, actors, settling, f"{path}/reject")
    assert_error(post(client, actors, settling, f"{path}/confirm"), 409, "PAYMENT_STATUS_CONFLICT")
    assert_error(
        post(client, actors, settling, "payments/9007199254740991/confirm"),
        404,
        "PAYMENT_NOT_FOUND",
    )


def test_preview_error_codes(client, actors, outsider, group):
    other = client.post(
        "/api/v1/activities", headers=outsider["headers"], json={"name": "其他活动"}
    ).json()
    foreign = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=outsider["headers"]
    ).json()[0]["id"]
    response = post(
        client,
        actors,
        group,
        "split-preview",
        json={
            "amount_cents": 100,
            "split_method": "EQUAL",
            "participants": [{"member_id": foreign}],
        },
    )
    assert_error(response, 422, "EXPENSE_MEMBER_MISMATCH")


@pytest.mark.parametrize(
    "path", ["balances", "settlement-suggestions", "payments", "statistics", "export.csv"]
)
def test_outsider_gets_activity_not_found(client, outsider, trip, path):
    response = client.get(f"/api/v1/activities/{trip['id']}/{path}", headers=outsider["headers"])
    assert_error(response, 404, "ACTIVITY_NOT_FOUND")


def test_settlement_codes_are_published_in_openapi(client):
    published = set(
        client.get("/openapi.json").json()["components"]["schemas"]["ErrorCode"]["enum"]
    )
    assert {
        ErrorCode.INVALID_PAYMENT,
        ErrorCode.PAYMENT_NOT_FOUND,
        ErrorCode.PAYMENT_ACTION_FORBIDDEN,
        ErrorCode.PAYMENTS_CLOSED,
        ErrorCode.PAYMENT_QUOTA_EXCEEDED,
        ErrorCode.PAYMENT_STATUS_CONFLICT,
        ErrorCode.SETTLEMENT_ALREADY_STARTED,
        ErrorCode.ACTIVITY_NOT_SETTLED,
    } <= published
