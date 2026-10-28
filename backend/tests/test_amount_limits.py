"""活动有效费用总额不超过 MAX_CENTS，保证余额、统计与转账建议都在单笔上限和 JS 安全整数内。"""

from uuid import uuid4

from app.models import MAX_CENTS
from tests.test_api_errors import assert_error
from tests.test_expenses import create


def bob_only(group, expense_data, amount):
    ids = group["member_ids"]
    return expense_data | {
        "amount_cents": amount,
        "payer_member_id": ids["alice"],
        "participants": [{"member_id": ids["bob"]}],
    }


def post_expense(client, actors, group, data):
    return client.post(
        f"/api/v1/activities/{group['id']}/expenses",
        headers=actors["alice"]["headers"],
        json=data,
    )


def get(client, actors, group, path):
    return client.get(
        f"/api/v1/activities/{group['id']}/{path}", headers=actors["alice"]["headers"]
    ).json()


def test_review_case_second_expense_over_total_limit_is_rejected(
    client, actors, group, expense_data
):
    create(client, actors, group, bob_only(group, expense_data, MAX_CENTS))

    response = post_expense(client, actors, group, bob_only(group, expense_data, 2))

    assert_error(response, 422, "INVALID_EXPENSE")
    assert len(get(client, actors, group, "expenses")) == 1
    suggestions = get(client, actors, group, "settlement-suggestions")
    assert [s["amount_cents"] for s in suggestions] == [MAX_CENTS]


def test_suggestion_at_total_limit_is_executable(client, actors, group, expense_data):
    create(client, actors, group, bob_only(group, expense_data, MAX_CENTS))
    client.post(
        f"/api/v1/activities/{group['id']}/start-settlement", headers=actors["alice"]["headers"]
    )
    [suggestion] = get(client, actors, group, "settlement-suggestions")

    payment = client.post(
        f"/api/v1/activities/{group['id']}/payments",
        headers=actors["bob"]["headers"],
        json={
            "payee_member_id": suggestion["payee_member_id"],
            "amount_cents": suggestion["amount_cents"],
            "request_id": str(uuid4()),
        },
    )
    assert payment.status_code == 201, payment.text
    confirmed = client.post(
        f"/api/v1/activities/{group['id']}/payments/{payment.json()['id']}/confirm",
        headers=actors["alice"]["headers"],
    )
    assert confirmed.status_code == 200
    activity = client.get(
        f"/api/v1/activities/{group['id']}", headers=actors["alice"]["headers"]
    ).json()
    assert activity["status"] == "SETTLED"


def test_update_over_total_limit_is_rejected(client, actors, group, expense_data):
    create(client, actors, group, bob_only(group, expense_data, MAX_CENTS - 10))
    small = create(client, actors, group, bob_only(group, expense_data, 5))
    path = f"/api/v1/activities/{group['id']}/expenses/{small['id']}"
    headers = actors["alice"]["headers"]

    over = client.patch(path, headers=headers, json={"version": 1, "amount_cents": 11})
    assert_error(over, 422, "INVALID_EXPENSE")
    assert client.get(path, headers=headers).json()["version"] == 1
    # 修改时排除自身原金额，恰好达到上限可以保存
    exact = client.patch(path, headers=headers, json={"version": 1, "amount_cents": 10})
    assert exact.status_code == 200, exact.text


def test_deleted_expense_does_not_count_toward_limit(client, actors, group, expense_data):
    big = create(client, actors, group, bob_only(group, expense_data, MAX_CENTS))
    client.delete(
        f"/api/v1/activities/{group['id']}/expenses/{big['id']}?version=1",
        headers=actors["alice"]["headers"],
    )

    assert (
        post_expense(client, actors, group, bob_only(group, expense_data, MAX_CENTS)).status_code
        == 201
    )


def test_aggregates_stay_within_limit_near_total_limit(client, actors, group, expense_data):
    ids = group["member_ids"]
    half = MAX_CENTS // 2
    for payer, amount in [("alice", half), ("bob", MAX_CENTS - half)]:
        create(
            client,
            actors,
            group,
            expense_data
            | {
                "amount_cents": amount,
                "payer_member_id": ids[payer],
                "participants": [{"member_id": ids["charlie"]}],
            },
        )

    rows = get(client, actors, group, "balances")
    assert max(abs(r[k]) for r in rows for k in r if k.endswith("_cents")) == MAX_CENTS
    assert all(
        s["amount_cents"] <= MAX_CENTS for s in get(client, actors, group, "settlement-suggestions")
    )
    assert get(client, actors, group, "statistics")["total_spent_cents"] == MAX_CENTS
