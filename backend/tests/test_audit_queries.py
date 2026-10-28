from app.database import transaction
from app.models import Activity, ActivityStatus
from tests.test_expenses import create


def test_trace_deleted_expense_in_archived_activity(client, actors, group, expense_data):
    expense = create(client, actors, group, expense_data, actor="bob")
    other = create(client, actors, group, expense_data | {"title": "另一笔费用"})
    base = f"/api/v1/activities/{group['id']}"
    path = f"{base}/expenses/{expense['id']}"
    headers = actors["bob"]["headers"]
    assert (
        client.patch(path, headers=headers, json={"version": 1, "amount_cents": 12000}).status_code
        == 200
    )
    assert client.delete(path, headers=headers, params={"version": 2}).status_code == 204
    with transaction(client.app.state.engine, write=True) as session:
        session.get(Activity, group["id"]).status = ActivityStatus.ARCHIVED
    response = client.get(
        base + "/audit-logs",
        headers=headers,
        params={"object_type": "expense", "object_id": expense["id"]},
    )
    assert response.status_code == 200
    history = response.json()
    assert [item["action"] for item in history] == [
        "EXPENSE_DELETED",
        "EXPENSE_UPDATED",
        "EXPENSE_CREATED",
    ]
    assert history[0]["after"]["is_deleted"] is True
    assert history[1]["before"]["amount_cents"] == 10000
    assert history[1]["after"]["amount_cents"] == 12000
    assert all(item["actor_user_id"] == actors["bob"]["user"]["id"] for item in history)
    assert client.get(path, headers=headers).status_code == 404
    all_expenses = client.get(
        base + "/audit-logs", headers=headers, params={"object_type": "expense"}
    ).json()
    assert len(all_expenses) == 4
    assert {item["object_id"] for item in all_expenses} == {expense["id"], other["id"]}


def test_actor_action_and_object_filters_combine(client, actors, group):
    path = f"/api/v1/activities/{group['id']}/audit-logs"
    headers = actors["alice"]["headers"]
    initial = client.get(path, headers=headers).json()
    response = client.get(
        path,
        headers=headers,
        params={
            "actor_user_id": actors["bob"]["user"]["id"],
            "action": "MEMBER_JOINED",
            "object_type": "membership",
            "object_id": group["member_ids"]["bob"],
        },
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["after"]["user_id"] == actors["bob"]["user"]["id"]
    assert (
        client.get(
            path, headers=headers, params={"actor_user_id": actors["bob"]["user"]["id"]}
        ).json()
        == response.json()
    )
    assert len(client.get(path, headers=headers, params={"action": "MEMBER_JOINED"}).json()) == 2
    assert client.get(path, headers=headers, params={"action": "PAYMENT_CONFIRMED"}).json() == []
    assert client.get(path, headers=headers).json() == initial  # Queries never append audit events.


def test_history_cursor_survives_new_entries(client, actors, group, expense_data):
    path = f"/api/v1/activities/{group['id']}/audit-logs"
    headers = actors["alice"]["headers"]
    initial = client.get(path, headers=headers).json()
    first = client.get(path, headers=headers, params={"limit": 2}).json()
    create(client, actors, group, expense_data)
    second = client.get(
        path, headers=headers, params={"limit": 2, "before_id": first[-1]["id"]}
    ).json()
    assert first + second == initial
    assert client.get(path, headers=headers, params={"before_id": second[-1]["id"]}).json() == []
    assert client.get(path, headers=headers, params={"limit": 2, "offset": 1}).json() == first


def test_audit_filters_keep_activity_isolation(client, actors, outsider, group):
    path = f"/api/v1/activities/{group['id']}/audit-logs"
    other = client.post(
        "/api/v1/activities", headers=actors["alice"]["headers"], json={"name": "私人活动"}
    ).json()
    assert (
        client.get(
            path, headers=outsider["headers"], params={"action": "MEMBER_JOINED"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            path,
            headers=actors["alice"]["headers"],
            params={"object_type": "activity", "object_id": other["id"]},
        ).json()
        == []
    )
    assert (
        client.get(
            path,
            headers=actors["alice"]["headers"],
            params={"actor_user_id": outsider["user"]["id"]},
        ).json()
        == []
    )


def test_invalid_audit_filters(client, actors, group):
    path = f"/api/v1/activities/{group['id']}/audit-logs"
    for params in [
        {"object_id": 1},
        {"object_type": "expense", "object_id": 0},
        {"object_type": "x" * 31},
        {"action": ""},
        {"action": "x" * 41},
        {"actor_user_id": -1},
        {"actor_user_id": 10**100},
        {"before_id": 0},
        {"before_id": 3, "offset": 1},
    ]:
        response = client.get(path, headers=actors["alice"]["headers"], params=params)
        assert response.status_code == 422, (params, response.text)
