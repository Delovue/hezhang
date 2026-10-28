import pytest


def preview(client, actors, group, payload, actor="alice"):
    return client.post(
        f"/api/v1/activities/{group['id']}/split-preview",
        headers=actors[actor]["headers"],
        json=payload,
    )


def participants(group, **values):
    ids = group["member_ids"]
    return [{"member_id": ids[name], **extra} for name, extra in values.items()]


def test_t01_preview_equal_split(client, actors, group):
    response = preview(
        client,
        actors,
        group,
        {
            "amount_cents": 10000,
            "split_method": "EQUAL",
            "participants": participants(group, charlie={}, alice={}, bob={}),
        },
    )

    assert response.status_code == 200, response.text
    assert [row["amount_cents"] for row in response.json()] == [3334, 3333, 3333]


def test_t03_preview_shares_split_keeps_share_counts(client, actors, group):
    response = preview(
        client,
        actors,
        group,
        {
            "amount_cents": 30000,
            "split_method": "SHARES",
            "participants": participants(group, alice={"shares": 2}, bob={"shares": 1}),
        },
    )

    assert [(row["amount_cents"], row["shares"]) for row in response.json()] == [
        (20000, 2),
        (10000, 1),
    ]


def test_preview_matches_saved_expense(client, actors, group, expense_data):
    split = {key: expense_data[key] for key in ["amount_cents", "split_method", "participants"]}
    previewed = preview(client, actors, group, split, actor="bob").json()
    saved = client.post(
        f"/api/v1/activities/{group['id']}/expenses",
        headers=actors["alice"]["headers"],
        json=expense_data,
    ).json()

    assert previewed == saved["shares"]


def test_preview_does_not_create_expense(client, actors, group, expense_data):
    split = {key: expense_data[key] for key in ["amount_cents", "split_method", "participants"]}
    preview(client, actors, group, split)

    expenses = client.get(
        f"/api/v1/activities/{group['id']}/expenses", headers=actors["alice"]["headers"]
    )
    assert expenses.json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"amount_cents": 0, "split_method": "EQUAL"},
        {"amount_cents": 100, "split_method": "EXACT"},  # 缺少指定金额
        {"amount_cents": 100, "split_method": "UNKNOWN"},
    ],
)
def test_t04_preview_rejects_invalid_input(client, actors, group, payload):
    payload = payload | {"participants": participants(group, alice={}, bob={})}
    assert preview(client, actors, group, payload).status_code == 422


def test_preview_rejects_exact_amounts_not_matching_total(client, actors, group):
    payload = {
        "amount_cents": 10000,
        "split_method": "EXACT",
        "participants": participants(
            group, alice={"amount_cents": 3000}, bob={"amount_cents": 3000}
        ),
    }
    assert preview(client, actors, group, payload).status_code == 422


def test_preview_rejects_members_of_other_activity(client, actors, outsider, group):
    other = client.post(
        "/api/v1/activities", headers=outsider["headers"], json={"name": "其他活动"}
    ).json()
    foreign = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=outsider["headers"]
    ).json()[0]["id"]
    payload = {
        "amount_cents": 100,
        "split_method": "EQUAL",
        "participants": [{"member_id": group["member_ids"]["alice"]}, {"member_id": foreign}],
    }
    assert preview(client, actors, group, payload).status_code == 422


def test_t12_outsider_cannot_preview(client, outsider, group):
    response = client.post(
        f"/api/v1/activities/{group['id']}/split-preview",
        headers=outsider["headers"],
        json={
            "amount_cents": 100,
            "split_method": "EQUAL",
            "participants": [{"member_id": group["member_ids"]["alice"]}],
        },
    )
    assert response.status_code == 404
