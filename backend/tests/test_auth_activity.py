from datetime import UTC, datetime, timedelta

import jwt
import pytest
from alembic import command
from sqlalchemy import inspect, select

from app.database import build_engine, transaction
from app.models import Activity, ActivityStatus, User
from app.security import AUDIENCE, ISSUER, verify_password
from tests.conftest import PASSWORD, TEST_SECRET, migration_config, register_actor


def test_register_login_me_and_password_hash(client):
    actor = register_actor(client, "Alice")
    assert actor["user"]["username"] == "alice"
    assert set(actor["user"]) == {"id", "username", "display_name"}
    me = client.get("/api/v1/auth/me", headers=actor["headers"])
    assert me.status_code == 200 and me.json() == actor["user"]
    with transaction(client.app.state.engine) as session:
        user = session.get(User, actor["user"]["id"])
        assert user.password_hash != PASSWORD and verify_password(PASSWORD, user.password_hash)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ALICE",
            "display_name": "other",
            "password": PASSWORD,
        },
    )
    assert duplicate.status_code == 409


def test_unknown_user_and_wrong_password_share_error(client):
    register_actor(client, "alice")
    for username in ["alice", "unknown"]:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": username,
                "password": "wrong-password",
            },
        )
        assert response.status_code == 401
        assert response.json() == {
            "detail": "用户名或密码错误",
            "code": "INVALID_CREDENTIALS",
            "retryable": False,
        }


@pytest.mark.parametrize("auth", [None, "Bearer not-a-jwt", "Basic abc"])
def test_missing_or_invalid_auth(client, auth):
    response = client.get("/api/v1/auth/me", headers={"Authorization": auth} if auth else {})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_and_deleted_subject(client):
    actor = register_actor(client, "alice")
    now = datetime.now(UTC)
    claims = {
        "sub": str(actor["user"]["id"]),
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "iss": ISSUER,
        "aud": AUDIENCE,
    }
    expired = jwt.encode(claims, TEST_SECRET, algorithm="HS256")
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + expired}).status_code
        == 401
    )
    claims.update(sub="99999", exp=now + timedelta(hours=1))
    unknown = jwt.encode(claims, TEST_SECRET, algorithm="HS256")
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + unknown}).status_code
        == 401
    )


def test_validation_does_not_echo_password(client):
    secret = "supersecret-password"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "!",
            "display_name": "A",
            "password": secret,
        },
    )
    assert response.status_code == 422
    assert secret not in response.text and "input" not in response.json()["detail"][0]


def test_activity_members_invite_privacy_and_idempotent_join(client, actors, group):
    base = f"/api/v1/activities/{group['id']}"
    owner = client.get(base, headers=actors["alice"]["headers"]).json()
    member = client.get(base, headers=actors["bob"]["headers"]).json()
    assert owner["invite_code"] and member["invite_code"] is None
    for _ in range(2):
        assert (
            client.post(
                "/api/v1/activities/join",
                headers=actors["bob"]["headers"],
                json={"invite_code": owner["invite_code"]},
            ).status_code
            == 200
        )
    members = client.get(base + "/members", headers=actors["alice"]["headers"]).json()
    assert len(members) == 3 and [m["role"] for m in members].count("OWNER") == 1
    history = client.get(base + "/audit-logs", headers=actors["bob"]["headers"]).json()
    assert len(history) == 3
    assert all(owner["invite_code"] not in str(entry) for entry in history)


def test_activity_isolation_and_owner_only_update(client, actors, outsider, group):
    base = f"/api/v1/activities/{group['id']}"
    for path in [base, base + "/members", base + "/audit-logs"]:
        assert client.get(path, headers=outsider["headers"]).status_code == 404
    assert client.get("/api/v1/activities", headers=outsider["headers"]).json() == []
    assert (
        client.patch(base, headers=actors["bob"]["headers"], json={"name": "越权"}).status_code
        == 403
    )
    updated = client.patch(
        base, headers=actors["alice"]["headers"], json={"name": "新活动", "budget_cents": None}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "新活动" and updated.json()["budget_cents"] is None


@pytest.mark.parametrize(
    "status",
    [
        ActivityStatus.SETTLING,
        ActivityStatus.SETTLED,
        ActivityStatus.ARCHIVED,
    ],
)
def test_closed_activity_rejects_join_and_update(client, actors, outsider, group, status):
    with transaction(client.app.state.engine, write=True) as session:
        session.get(Activity, group["id"]).status = status
    assert (
        client.patch(
            f"/api/v1/activities/{group['id']}",
            headers=actors["alice"]["headers"],
            json={"budget_cents": 30000},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/activities/join",
            headers=outsider["headers"],
            json={"invite_code": group["invite_code"]},
        ).status_code
        == 409
    )


def test_budget_strict_integer_and_unknown_fields(client, actors):
    for payload in [
        {"name": "旅行", "budget_cents": True},
        {"name": "旅行", "budget_cents": 1.5},
        {"name": "旅行", "budget_cents": -1},
        {"name": "旅行", "status": "ARCHIVED"},
        {"name": "   "},
    ]:
        assert (
            client.post(
                "/api/v1/activities", headers=actors["alice"]["headers"], json=payload
            ).status_code
            == 422
        )


def test_migration_roundtrip_and_health(client, settings):
    assert client.get("/health").json()["schema_revision"] == "0003"
    config = migration_config(settings.database_url)
    command.check(config)
    # Empty test database only: verify the migration chain can be reversed.
    command.downgrade(config, "base")
    engine = build_engine(settings.database_url)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
    command.upgrade(config, "head")
    with transaction(client.app.state.engine) as session:
        assert session.scalars(select(User)).all() == []
