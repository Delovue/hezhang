import pytest

from app.database import transaction
from app.models import Activity, ActivityStatus


@pytest.fixture
def catalog(client, actors, group):
    activities = {ActivityStatus.ACTIVE: group}
    for status in [ActivityStatus.SETTLING, ActivityStatus.SETTLED, ActivityStatus.ARCHIVED]:
        created = client.post(
            "/api/v1/activities",
            headers=actors["alice"]["headers"],
            json={"name": f"三人出游 {status}"},
        )
        assert created.status_code == 201
        activity = created.json()
        if status == ActivityStatus.ARCHIVED:
            assert (
                client.post(
                    "/api/v1/activities/join",
                    headers=actors["bob"]["headers"],
                    json={"invite_code": activity["invite_code"]},
                ).status_code
                == 200
            )
        # Lifecycle endpoints belong to role C; seed states solely to verify read queries.
        with transaction(client.app.state.engine, write=True) as session:
            session.get(Activity, activity["id"]).status = status
        activities[status] = activity
    return activities


def test_status_filters_owned_and_joined_activities(client, actors, outsider, catalog):
    path = "/api/v1/activities"
    client.post(path, headers=outsider["headers"], json={"name": "三人出游 私人"})
    for status, activity in catalog.items():
        owner = client.get(
            path, headers=actors["alice"]["headers"], params={"status": status, "q": "三人"}
        )
        assert owner.status_code == 200
        assert [row["id"] for row in owner.json()] == [activity["id"]]
        assert bool(owner.json()[0]["invite_code"]) == (status == ActivityStatus.ACTIVE)
        member = client.get(
            path, headers=actors["bob"]["headers"], params={"status": status, "q": "三人"}
        ).json()
        expected = (
            [activity["id"]] if status in {ActivityStatus.ACTIVE, ActivityStatus.ARCHIVED} else []
        )
        assert [row["id"] for row in member] == expected
        assert all(row["invite_code"] is None for row in member)
    all_owned = client.get(path, headers=actors["alice"]["headers"]).json()
    assert len(all_owned) == 4


def test_activity_name_search_is_literal(client, actors):
    path = "/api/v1/activities"
    headers = actors["alice"]["headers"]
    literal = client.post(path, headers=headers, json={"name": "露营 100%_/Camping"}).json()
    client.post(path, headers=headers, json={"name": "露营普通活动"})
    for keyword in ["%", "_", "/", "100%_/", "  CAMPING  "]:
        response = client.get(path, headers=headers, params={"q": keyword})
        assert response.status_code == 200
        assert response.json() == [literal]
    assert client.get(path, headers=actors["bob"]["headers"], params={"q": "露营"}).json() == []


def test_activity_cursor_keeps_existing_order_when_new_activity_is_added(client, actors, catalog):
    path = "/api/v1/activities"
    headers = actors["alice"]["headers"]
    initial = client.get(path, headers=headers, params={"q": "出游"}).json()
    first = client.get(path, headers=headers, params={"q": "出游", "limit": 2}).json()
    assert len(first) == 2
    client.post(path, headers=headers, json={"name": "新的出游"})
    second = client.get(
        path, headers=headers, params={"q": "出游", "limit": 2, "before_id": first[-1]["id"]}
    ).json()
    assert first + second == initial
    assert client.get(path, headers=headers, params={"before_id": second[-1]["id"]}).json() == []
    filtered = client.get(
        path,
        headers=headers,
        params={
            "before_id": first[-1]["id"],
            "status": "ACTIVE",
            "q": "出游",
        },
    ).json()
    assert [row["id"] for row in filtered] == [catalog[ActivityStatus.ACTIVE]["id"]]
    assert client.get(path, headers=headers, params={"offset": 1, "limit": 2}).json() == first


def test_invalid_activity_search_filters(client, actors):
    for params in [
        {"status": "invalid"},
        {"q": ""},
        {"q": "   "},
        {"q": "x" * 121},
        {"before_id": 0},
        {"before_id": 10**100},
        {"before_id": 2, "offset": 1},
    ]:
        response = client.get(
            "/api/v1/activities", headers=actors["alice"]["headers"], params=params
        )
        assert response.status_code == 422, response.text
