from tests.test_expenses import create
from tests.test_payments_api import pay


def get(client, actors, group, path, actor="alice"):
    response = client.get(
        f"/api/v1/activities/{group['id']}/{path}", headers=actors[actor]["headers"]
    )
    assert response.status_code == 200, response.text
    return response


def test_trip_statistics(client, actors, trip):
    ids = trip["member_ids"]
    stats = get(client, actors, trip, "statistics").json()

    assert stats == {
        "total_spent_cents": 18000,
        "budget_cents": 20000,
        "remaining_budget_cents": 2000,
        "over_budget": False,
        "by_category": [
            {"category": "餐饮", "amount_cents": 12000},
            {"category": "交通", "amount_cents": 6000},
        ],
        "by_member": [
            {"member_id": ids["alice"], "owed_cents": 7000},
            {"member_id": ids["bob"], "owed_cents": 7000},
            {"member_id": ids["charlie"], "owed_cents": 4000},
        ],
    }


def test_over_budget_warning(client, actors, trip, expense_data):
    create(client, actors, trip, expense_data | {"amount_cents": 3000})
    stats = get(client, actors, trip, "statistics").json()

    assert stats["total_spent_cents"] == 21000
    assert stats["remaining_budget_cents"] == -1000
    assert stats["over_budget"] is True


def test_no_budget_skips_budget_check(client, actors):
    activity = client.post(
        "/api/v1/activities", headers=actors["alice"]["headers"], json={"name": "无预算"}
    ).json()
    stats = get(client, actors, activity, "statistics").json()

    assert stats["budget_cents"] is None
    assert stats["remaining_budget_cents"] is None
    assert stats["over_budget"] is False


def test_t18_payments_are_not_counted_as_spending(client, actors, trip):
    client.post(
        f"/api/v1/activities/{trip['id']}/start-settlement", headers=actors["alice"]["headers"]
    )
    payment = pay(client, actors, trip, "charlie", "alice", 4000).json()
    client.post(
        f"/api/v1/activities/{trip['id']}/payments/{payment['id']}/confirm",
        headers=actors["alice"]["headers"],
    )

    stats = get(client, actors, trip, "statistics").json()
    assert stats["total_spent_cents"] == 18000
    assert stats["remaining_budget_cents"] == 2000


def test_t12_outsider_cannot_read_statistics(client, outsider, trip):
    response = client.get(
        f"/api/v1/activities/{trip['id']}/statistics", headers=outsider["headers"]
    )
    assert response.status_code == 404
