import csv
import io
from urllib.parse import quote

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


def export_rows(client, actors, group, actor="alice"):
    response = get(client, actors, group, "export.csv", actor)
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.content.startswith(b"\xef\xbb\xbf")
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_t18_export_matches_page_amounts(client, actors, trip):
    rows = export_rows(client, actors, trip)

    assert rows == [
        [
            "日期",
            "分类",
            "说明",
            "付款人",
            "总额（元）",
            "分摊方式",
            "alice 承担（元）",
            "bob 承担（元）",
            "charlie 承担（元）",
        ],
        ["2026-10-27", "餐饮", "晚餐", "alice", "120.00", "均摊", "40.00", "40.00", "40.00"],
        ["2026-10-27", "交通", "打车", "bob", "60.00", "均摊", "30.00", "30.00", "0.00"],
    ]


def test_export_filename_supports_chinese(client, actors, trip):
    response = get(client, actors, trip, "export.csv")
    disposition = response.headers["content-disposition"]

    assert f'filename="activity-{trip["id"]}.csv"' in disposition
    assert "filename*=UTF-8''" + quote("三人出游-费用明细.csv", safe="") in disposition


def test_export_excludes_deleted_expenses_and_escapes_formulas(client, actors, group, expense_data):
    create(client, actors, group, expense_data | {"title": "=HYPERLINK(1)"})
    removed = create(client, actors, group, expense_data | {"title": "已删除"})
    client.delete(
        f"/api/v1/activities/{group['id']}/expenses/{removed['id']}?version=1",
        headers=actors["alice"]["headers"],
    )

    rows = export_rows(client, actors, group)
    assert [row[2] for row in rows[1:]] == ["'=HYPERLINK(1)"]
    assert rows[1][4] == "100.00"


def test_duplicate_display_names_are_distinguished(client, actors, group):
    client.post(
        "/api/v1/auth/register",
        json={"username": "bob_two", "display_name": "bob", "password": "Course-test-2026"},
    )
    token = client.post(
        "/api/v1/auth/login", json={"username": "bob_two", "password": "Course-test-2026"}
    ).json()["access_token"]
    invite_code = client.get(
        f"/api/v1/activities/{group['id']}", headers=actors["alice"]["headers"]
    ).json()["invite_code"]
    client.post(
        "/api/v1/activities/join",
        headers={"Authorization": "Bearer " + token},
        json={"invite_code": invite_code},
    )

    header = export_rows(client, actors, group)[0]
    bob_columns = [name for name in header if name.startswith("bob")]
    assert len(bob_columns) == 2 and all("（#" in name for name in bob_columns)


def test_export_after_archive(client, actors, group):
    for path in ["start-settlement", "archive"]:
        client.post(f"/api/v1/activities/{group['id']}/{path}", headers=actors["alice"]["headers"])
    assert len(export_rows(client, actors, group, actor="charlie")) == 1


def test_t12_outsider_cannot_export(client, outsider, trip):
    response = client.get(
        f"/api/v1/activities/{trip['id']}/export.csv", headers=outsider["headers"]
    )
    assert response.status_code == 404
