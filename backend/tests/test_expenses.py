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
