from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

BACKEND = Path(__file__).resolve().parents[1]
TEST_SECRET = "test-only-not-for-production-" * 3
PASSWORD = "Course-test-2026"


def migration_config(url: str) -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.attributes["database_url"] = url
    return config


@pytest.fixture
def settings(tmp_path):
    return Settings(
        database_url="sqlite:///" + (tmp_path / "test.db").as_posix(),
        jwt_secret=TEST_SECRET,
    )


@pytest.fixture
def client(settings):
    command.upgrade(migration_config(settings.database_url), "head")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def register_actor(client, name):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": name,
            "display_name": name,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    user = response.json()
    login = client.post("/api/v1/auth/login", json={"username": name, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"user": user, "headers": {"Authorization": "Bearer " + login.json()["access_token"]}}


@pytest.fixture
def actors(client):
    return {name: register_actor(client, name) for name in ["alice", "bob", "charlie"]}


@pytest.fixture
def outsider(client):
    return register_actor(client, "outsider")


@pytest.fixture
def group(client, actors):
    response = client.post(
        "/api/v1/activities",
        headers=actors["alice"]["headers"],
        json={"name": "三人出游", "budget_cents": 20000},
    )
    assert response.status_code == 201, response.text
    activity = response.json()
    for name in ["bob", "charlie"]:
        joined = client.post(
            "/api/v1/activities/join",
            headers=actors[name]["headers"],
            json={"invite_code": activity["invite_code"]},
        )
        assert joined.status_code == 200, joined.text
    members = client.get(
        f"/api/v1/activities/{activity['id']}/members", headers=actors["alice"]["headers"]
    ).json()
    activity["member_ids"] = {member["display_name"]: member["id"] for member in members}
    return activity


@pytest.fixture
def expense_data(group):
    return {
        "title": "餐费",
        "category": "餐饮",
        "amount_cents": 10000,
        "expense_date": "2026-10-27",
        "notes": "三人均摊",
        "payer_member_id": group["member_ids"]["alice"],
        "split_method": "EQUAL",
        "participants": [{"member_id": mid} for mid in group["member_ids"].values()],
    }


def trip_expenses(group):
    """README 三人出游示例：alice 垫付餐费 120 元三人均摊，bob 垫付车费 60 元仅 alice、bob 分摊。"""
    ids = group["member_ids"]
    base = {"category": "餐饮", "expense_date": "2026-10-27", "split_method": "EQUAL"}
    meal = base | {
        "title": "晚餐",
        "amount_cents": 12000,
        "payer_member_id": ids["alice"],
        "participants": [{"member_id": ids[name]} for name in ["alice", "bob", "charlie"]],
    }
    taxi = base | {
        "title": "打车",
        "category": "交通",
        "amount_cents": 6000,
        "payer_member_id": ids["bob"],
        "participants": [{"member_id": ids[name]} for name in ["alice", "bob"]],
    }
    return meal, taxi


@pytest.fixture
def trip(client, actors, group):
    for expense, actor in zip(trip_expenses(group), ["alice", "bob"], strict=True):
        response = client.post(
            f"/api/v1/activities/{group['id']}/expenses",
            headers=actors[actor]["headers"],
            json=expense,
        )
        assert response.status_code == 201, response.text
    return group


@pytest.fixture
def settling(client, actors, trip):
    """三人出游示例，创建者已发起结算。"""
    response = client.post(
        f"/api/v1/activities/{trip['id']}/start-settlement", headers=actors["alice"]["headers"]
    )
    assert response.json()["status"] == "SETTLING", response.text
    return trip
