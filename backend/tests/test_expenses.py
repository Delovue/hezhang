from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

from sqlalchemy import event

from app.database import transaction
from app.models import Activity, ActivityStatus


def create(client, actors, group, data, actor="alice"):
    response = client.post(
        f"/api/v1/activities/{group['id']}/expenses", headers=actors[actor]["headers"], json=data
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_audit(client, actors, group, expense_data):
    expense = create(client, actors, group, expense_data)
    assert expense["version"] == 1
    assert [share["amount_cents"] for share in expense["shares"]] == [3334, 3333, 3333]
    path = f"/api/v1/activities/{group['id']}/expenses/{expense['id']}"
    headers = actors["alice"]["headers"]
    assert client.get(path, headers=headers).json() == expense
    history = client.get(f"/api/v1/activities/{group['id']}/audit-logs", headers=headers).json()
    assert history[0]["action"] == "EXPENSE_CREATED"
    assert history[0]["after"]["amount_cents"] == 10000


def test_create_rejects_foreign_members(client, actors, outsider, group, expense_data):
    other = client.post(
        "/api/v1/activities", headers=outsider["headers"], json={"name": "其他活动"}
    ).json()
    foreign = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=outsider["headers"]
    ).json()[0]["id"]
    path = f"/api/v1/activities/{group['id']}/expenses"
    for override in [{"payer_member_id": foreign}, {"participants": [{"member_id": foreign}]}]:
        assert (
            client.post(
                path, headers=actors["alice"]["headers"], json=expense_data | override
            ).status_code
            == 422
        )
    assert client.get(path, headers=actors["alice"]["headers"]).json() == []


def test_partial_participation_and_other_split_methods(client, actors, group, expense_data):
    a, b, c = [group["member_ids"][name] for name in ["alice", "bob", "charlie"]]
    expense_data.update(amount_cents=6000, participants=[{"member_id": a}, {"member_id": b}])
    expense = create(client, actors, group, expense_data)
    assert {share["member_id"]: share["amount_cents"] for share in expense["shares"]} == {
        a: 3000,
        b: 3000,
    }
    assert c not in {share["member_id"] for share in expense["shares"]}
    path = f"/api/v1/activities/{group['id']}/expenses/{expense['id']}"
    exact = client.patch(
        path,
        headers=actors["alice"]["headers"],
        json={
            "version": 1,
            "split_method": "EXACT",
            "participants": [
                {"member_id": a, "amount_cents": 1000},
                {"member_id": b, "amount_cents": 5000},
            ],
        },
    )
    assert exact.status_code == 200, exact.text
    assert [s["amount_cents"] for s in exact.json()["shares"]] == [1000, 5000]
    invalid = client.patch(
        path, headers=actors["alice"]["headers"], json={"version": 2, "amount_cents": 6001}
    )
    assert invalid.status_code == 422
    weighted = client.patch(
        path,
        headers=actors["alice"]["headers"],
        json={
            "version": 2,
            "split_method": "SHARES",
            "participants": [{"member_id": a, "shares": 2}, {"member_id": b, "shares": 1}],
        },
    )
    assert weighted.status_code == 200
    assert [s["amount_cents"] for s in weighted.json()["shares"]] == [4000, 2000]


def test_cross_activity_references_and_access_rejected(
    client,
    actors,
    outsider,
    group,
    expense_data,
):
    other = client.post(
        "/api/v1/activities", headers=outsider["headers"], json={"name": "其他活动"}
    ).json()
    other_member = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=outsider["headers"]
    ).json()[0]["id"]
    base = f"/api/v1/activities/{group['id']}/expenses"
    original = create(client, actors, group, expense_data)
    for path in [base, base + f"/{original['id']}"]:
        assert client.get(path, headers=outsider["headers"]).status_code == 404
    assert (
        client.patch(
            base + f"/{original['id']}",
            headers=outsider["headers"],
            json={"version": 1, "title": "越权"},
        ).status_code
        == 404
    )
    for override in [
        {"payer_member_id": other_member},
        {"participants": [{"member_id": other_member}]},
    ]:
        response = client.post(
            base, headers=actors["alice"]["headers"], json=expense_data | override
        )
        assert response.status_code == 422
    assert len(client.get(base, headers=actors["alice"]["headers"]).json()) == 1


def test_expense_filters_and_pagination(client, actors, group, expense_data):
    for index in range(3):
        create(
            client,
            actors,
            group,
            expense_data
            | {
                "title": str(index),
                "category": "餐饮" if index < 2 else "交通",
                "expense_date": f"2026-10-{25 + index}",
            },
        )
    base = f"/api/v1/activities/{group['id']}/expenses"
    headers = actors["alice"]["headers"]
    assert [
        e["title"]
        for e in client.get(base, headers=headers, params={"limit": 1, "offset": 1}).json()
    ] == ["1"]
    assert len(client.get(base, headers=headers, params={"category": "餐饮"}).json()) == 2
    assert [
        e["title"]
        for e in client.get(
            base, headers=headers, params={"start_date": "2026-10-26", "end_date": "2026-10-26"}
        ).json()
    ] == ["1"]
    assert (
        client.get(
            base, headers=headers, params={"start_date": "2026-10-28", "end_date": "2026-10-26"}
        ).status_code
        == 422
    )


def test_simultaneous_edits_have_exactly_one_winner(client, actors, group, expense_data):
    original = create(client, actors, group, expense_data)
    path = f"/api/v1/activities/{group['id']}/expenses/{original['id']}"
    barrier = Barrier(2)

    def edit(title):
        barrier.wait(timeout=5)
        return client.patch(
            path, headers=actors["alice"]["headers"], json={"version": 1, "title": title}
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(edit, ["修改一", "修改二"]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json() for response in responses if response.status_code == 200)
    final = client.get(path, headers=actors["alice"]["headers"]).json()
    assert final["version"] == 2 and final["title"] == winner["title"]


def test_edit_waits_for_seal_then_rechecks_status(client, actors, group, expense_data):
    original = create(client, actors, group, expense_data)
    engine = client.app.state.engine
    attempted = Event()
    path = f"/api/v1/activities/{group['id']}/expenses/{original['id']}"

    def observe_begin(_conn, _cursor, statement, _parameters, _context, _many):
        if statement == "BEGIN IMMEDIATE":
            attempted.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction(engine, write=True) as sealing:
            sealing.get(Activity, group["id"]).status = ActivityStatus.SETTLING
            sealing.flush()
            event.listen(engine, "before_cursor_execute", observe_begin)
            future = executor.submit(
                client.patch,
                path,
                headers=actors["alice"]["headers"],
                json={"version": 1, "title": "晚到的修改"},
            )
            try:
                assert attempted.wait(timeout=5), "edit did not attempt its own write transaction"
            finally:
                event.remove(engine, "before_cursor_execute", observe_begin)
        response = future.result(timeout=5)
    assert response.status_code == 409
    assert client.get(path, headers=actors["alice"]["headers"]).json() == original
