import pytest

from tests.test_expenses import create


def post(client, actors, group, path, actor="alice", **kwargs):
    return client.post(
        f"/api/v1/activities/{group['id']}/{path}", headers=actors[actor]["headers"], **kwargs
    )


def status_of(client, actors, group):
    return client.get(
        f"/api/v1/activities/{group['id']}", headers=actors["alice"]["headers"]
    ).json()["status"]


def test_start_settlement_with_debts_enters_settling(client, actors, trip):
    response = post(client, actors, trip, "start-settlement")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "SETTLING"
    assert response.json()["invite_code"] is None
    history = client.get(
        f"/api/v1/activities/{trip['id']}/audit-logs", headers=actors["alice"]["headers"]
    ).json()
    assert history[0]["action"] == "SETTLEMENT_STARTED"
    assert (history[0]["before"]["status"], history[0]["after"]["status"]) == (
        "ACTIVE",
        "SETTLING",
    )


def test_t17_empty_activity_is_settled_immediately(client, actors, group):
    response = post(client, actors, group, "start-settlement")
    assert response.json()["status"] == "SETTLED"


def test_t17_net_zero_activity_is_settled_immediately(client, actors, group, expense_data):
    ids = group["member_ids"]
    for payer in ["alice", "bob"]:
        create(
            client,
            actors,
            group,
            expense_data
            | {
                "payer_member_id": ids[payer],
                "participants": [{"member_id": ids["alice"]}, {"member_id": ids["bob"]}],
            },
        )

    assert post(client, actors, group, "start-settlement").json()["status"] == "SETTLED"


def test_only_creator_can_start_settlement(client, actors, trip):
    assert post(client, actors, trip, "start-settlement", actor="bob").status_code == 403
    assert status_of(client, actors, trip) == "ACTIVE"


def test_cannot_start_settlement_twice(client, actors, trip):
    post(client, actors, trip, "start-settlement")
    assert post(client, actors, trip, "start-settlement").status_code == 409


def test_t13_settlement_freezes_expenses_and_members(client, actors, trip, expense_data, outsider):
    expense = client.get(
        f"/api/v1/activities/{trip['id']}/expenses", headers=actors["alice"]["headers"]
    ).json()[0]
    invite_code = client.get(
        f"/api/v1/activities/{trip['id']}", headers=actors["alice"]["headers"]
    ).json()["invite_code"]
    post(client, actors, trip, "start-settlement")
    path = f"/api/v1/activities/{trip['id']}/expenses"
    headers = actors["alice"]["headers"]

    assert client.post(path, headers=headers, json=expense_data).status_code == 409
    assert (
        client.patch(
            f"{path}/{expense['id']}", headers=headers, json={"version": 1, "amount_cents": 1}
        ).status_code
        == 409
    )
    assert client.delete(f"{path}/{expense['id']}?version=1", headers=headers).status_code == 409
    joined = client.post(
        "/api/v1/activities/join", headers=outsider["headers"], json={"invite_code": invite_code}
    )
    assert joined.status_code == 409


def test_t16_archive_settled_activity(client, actors, group):
    post(client, actors, group, "start-settlement")
    response = post(client, actors, group, "archive")

    assert response.status_code == 200
    assert response.json()["status"] == "ARCHIVED"
    balances = client.get(
        f"/api/v1/activities/{group['id']}/balances", headers=actors["bob"]["headers"]
    )
    assert balances.status_code == 200


@pytest.mark.parametrize("started", [False, True])
def test_t16_cannot_archive_unsettled_activity(client, actors, trip, started):
    if started:
        post(client, actors, trip, "start-settlement")
    assert post(client, actors, trip, "archive").status_code == 409


def test_only_creator_can_archive(client, actors, group):
    post(client, actors, group, "start-settlement")
    assert post(client, actors, group, "archive", actor="charlie").status_code == 403
    assert status_of(client, actors, group) == "SETTLED"


def test_t12_outsider_cannot_change_lifecycle(client, actors, outsider, group):
    for path in ["start-settlement", "archive"]:
        response = client.post(
            f"/api/v1/activities/{group['id']}/{path}", headers=outsider["headers"]
        )
        assert response.status_code == 404
    assert status_of(client, actors, group) == "ACTIVE"
