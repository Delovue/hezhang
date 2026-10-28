import pytest

from tests.test_expenses import create


@pytest.fixture
def searchable_expenses(client, actors, group, expense_data):
    alice, bob, charlie = [group["member_ids"][name] for name in ["alice", "bob", "charlie"]]
    meal = create(
        client,
        actors,
        group,
        expense_data
        | {"title": "晚餐 Dining", "notes": "餐厅满减 100%_/优惠", "amount_cents": 12000},
    )
    taxi = create(
        client,
        actors,
        group,
        expense_data
        | {
            "title": "去机场打车",
            "category": "交通",
            "notes": None,
            "amount_cents": 6000,
            "payer_member_id": bob,
            "participants": [{"member_id": alice}, {"member_id": bob}],
        },
    )
    gift = create(
        client,
        actors,
        group,
        expense_data
        | {
            "title": "纪念品",
            "category": "购物",
            "notes": "晚餐之后买的",
            "amount_cents": 1000,
            "payer_member_id": bob,
            "split_method": "EXACT",
            "participants": [
                {"member_id": alice, "amount_cents": 1000},
                {"member_id": charlie, "amount_cents": 0},
            ],
        },
    )
    return {"meal": meal, "taxi": taxi, "gift": gift}


def test_keyword_searches_title_and_notes_literally(client, actors, group, searchable_expenses):
    path = f"/api/v1/activities/{group['id']}/expenses"
    headers = actors["alice"]["headers"]
    meal = searchable_expenses["meal"]
    gift = searchable_expenses["gift"]
    for query, expected in [
        ("晚餐", [gift["id"], meal["id"]]),
        ("  DINING  ", [meal["id"]]),
        ("%", [meal["id"]]),
        ("_", [meal["id"]]),
        ("/", [meal["id"]]),
        ("100%_/", [meal["id"]]),
        ("不存在的账单", []),
    ]:
        response = client.get(path, headers=headers, params={"q": query})
        assert response.status_code == 200, response.text
        assert [expense["id"] for expense in response.json()] == expected


def test_participant_is_distinct_from_payer_and_keeps_zero_shares(
    client, actors, group, searchable_expenses
):
    path = f"/api/v1/activities/{group['id']}/expenses"
    headers = actors["bob"]["headers"]
    params = {"participant_member_id": group["member_ids"]["charlie"]}
    filtered = client.get(path, headers=headers, params=params).json()
    assert [expense["id"] for expense in filtered] == [
        searchable_expenses["gift"]["id"],
        searchable_expenses["meal"]["id"],
    ]
    combined = client.get(
        path,
        headers=headers,
        params=params
        | {
            "payer_member_id": group["member_ids"]["bob"],
            "q": "晚餐",
            "category": "购物",
            "start_date": "2026-10-27",
            "end_date": "2026-10-27",
        },
    ).json()
    assert combined == [searchable_expenses["gift"]]
    page = client.get(path, headers=headers, params=params | {"limit": 1, "offset": 1}).json()
    assert page == [searchable_expenses["meal"]]


def test_search_excludes_soft_deleted_expenses(client, actors, group, searchable_expenses):
    path = f"/api/v1/activities/{group['id']}/expenses"
    headers = actors["alice"]["headers"]
    meal = searchable_expenses["meal"]
    assert (
        client.delete(f"{path}/{meal['id']}", headers=headers, params={"version": 1}).status_code
        == 204
    )
    for params in [
        {"q": "DINING"},
        {"q": "%"},
        {"participant_member_id": group["member_ids"]["charlie"], "category": "餐饮"},
    ]:
        assert client.get(path, headers=headers, params=params).json() == []


def test_expense_search_never_leaks_other_activities(client, actors, outsider, group, expense_data):
    headers = actors["alice"]["headers"]
    other = client.post("/api/v1/activities", headers=headers, json={"name": "另一趟旅行"}).json()
    foreign_member = client.get(
        f"/api/v1/activities/{other['id']}/members", headers=headers
    ).json()[0]["id"]
    create(
        client,
        actors,
        other,
        expense_data
        | {
            "notes": "只在别的活动出现",
            "payer_member_id": foreign_member,
            "participants": [{"member_id": foreign_member}],
        },
    )
    path = f"/api/v1/activities/{group['id']}/expenses"
    for params in [{"q": "只在别的活动出现"}, {"participant_member_id": foreign_member}]:
        response = client.get(path, headers=headers, params=params)
        assert response.status_code == 200 and response.json() == []
        assert client.get(path, headers=outsider["headers"], params=params).status_code == 404


def test_invalid_expense_search_parameters(client, actors, group):
    path = f"/api/v1/activities/{group['id']}/expenses"
    for params in [
        {"q": ""},
        {"q": "   "},
        {"q": "x" * 121},
        {"participant_member_id": 0},
        {"participant_member_id": 10**100},
    ]:
        assert (
            client.get(path, headers=actors["alice"]["headers"], params=params).status_code == 422
        )
