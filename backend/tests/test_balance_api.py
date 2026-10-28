import pytest

from tests.test_expenses import create


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
    meal, taxi = trip_expenses(group)
    create(client, actors, group, meal)
    create(client, actors, group, taxi, actor="bob")
    return group


def get(client, actors, group, path, actor="alice"):
    response = client.get(
        f"/api/v1/activities/{group['id']}/{path}", headers=actors[actor]["headers"]
    )
    assert response.status_code == 200, response.text
    return response.json()


def balances_by_name(client, actors, group, actor="alice"):
    names = {member_id: name for name, member_id in group["member_ids"].items()}
    return {names[row["member_id"]]: row for row in get(client, actors, group, "balances", actor)}


def test_t06_trip_balances(client, actors, trip):
    rows = balances_by_name(client, actors, trip)

    assert {name: row["balance_cents"] for name, row in rows.items()} == {
        "alice": 5000,
        "bob": -1000,
        "charlie": -4000,
    }
    assert rows["alice"]["paid_cents"] == 12000
    assert rows["charlie"]["owed_cents"] == 4000
    assert rows["charlie"]["available_out_cents"] == 4000
    assert rows["alice"]["available_in_cents"] == 5000


def test_every_member_can_read_balances(client, actors, trip):
    expected = get(client, actors, trip, "balances")
    for name in ["bob", "charlie"]:
        assert get(client, actors, trip, "balances", actor=name) == expected


def test_trip_settlement_suggestions(client, actors, trip):
    ids = trip["member_ids"]

    assert get(client, actors, trip, "settlement-suggestions") == [
        {"payer_member_id": ids["charlie"], "payee_member_id": ids["alice"], "amount_cents": 4000},
        {"payer_member_id": ids["bob"], "payee_member_id": ids["alice"], "amount_cents": 1000},
    ]
    # 生成建议不修改余额
    assert balances_by_name(client, actors, trip)["alice"]["balance_cents"] == 5000


def test_soft_deleted_expense_is_excluded(client, actors, group):
    meal, _ = trip_expenses(group)
    expense = create(client, actors, group, meal)
    deleted = client.delete(
        f"/api/v1/activities/{group['id']}/expenses/{expense['id']}?version=1",
        headers=actors["alice"]["headers"],
    )
    assert deleted.status_code == 204

    rows = balances_by_name(client, actors, group)
    assert all(row["balance_cents"] == 0 for row in rows.values())
    assert get(client, actors, group, "settlement-suggestions") == []


def test_edited_expense_updates_balances(client, actors, group):
    meal, _ = trip_expenses(group)
    expense = create(client, actors, group, meal)
    client.patch(
        f"/api/v1/activities/{group['id']}/expenses/{expense['id']}",
        headers=actors["alice"]["headers"],
        json={"version": 1, "amount_cents": 15000},
    )

    assert balances_by_name(client, actors, group)["alice"]["balance_cents"] == 10000


@pytest.mark.parametrize("path", ["balances", "settlement-suggestions"])
def test_t12_outsider_cannot_read_ledger(client, outsider, trip, path):
    response = client.get(f"/api/v1/activities/{trip['id']}/{path}", headers=outsider["headers"])
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["balances", "settlement-suggestions"])
def test_ledger_requires_login(client, trip, path):
    assert client.get(f"/api/v1/activities/{trip['id']}/{path}").status_code == 401
