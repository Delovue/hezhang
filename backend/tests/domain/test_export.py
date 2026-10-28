import csv
import io
from datetime import date

import pytest

from app.domain.export import ExportExpense, build_expense_csv, escape_formula
from app.domain.split import split_equal
from app.models import SplitMethod

A, B, C = 1, 2, 3
MEMBERS = [(A, "小A"), (B, "小B"), (C, "小C")]

TRIP_EXPORT = [
    ExportExpense(
        date(2026, 10, 1), "餐饮", "第一天晚餐", "小A", 12000, SplitMethod.EQUAL,
        split_equal(12000, [A, B, C]),
    ),
    ExportExpense(
        date(2026, 10, 2), "交通", "打车", "小B", 6000, SplitMethod.EQUAL,
        split_equal(6000, [A, B]),
    ),
]


def parse(data: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))


def test_csv_starts_with_utf8_bom():
    assert build_expense_csv(MEMBERS, TRIP_EXPORT).startswith(b"\xef\xbb\xbf")


def test_csv_rows_match_page_amounts():
    rows = parse(build_expense_csv(MEMBERS, TRIP_EXPORT))

    assert rows == [
        ["日期", "分类", "说明", "付款人", "总额（元）", "分摊方式",
         "小A 承担（元）", "小B 承担（元）", "小C 承担（元）"],
        ["2026-10-01", "餐饮", "第一天晚餐", "小A", "120.00", "均摊", "40.00", "40.00", "40.00"],
        ["2026-10-02", "交通", "打车", "小B", "60.00", "均摊", "30.00", "30.00", "0.00"],
    ]


def test_csv_share_columns_sum_to_total():
    expense = ExportExpense(
        date(2026, 10, 3), "门票", "", "小A", 10000, SplitMethod.EQUAL,
        split_equal(10000, [A, B, C]),
    )
    row = parse(build_expense_csv(MEMBERS, [expense]))[1]

    assert row[6:] == ["33.34", "33.33", "33.33"]


def test_csv_quotes_commas_quotes_and_newlines():
    expense = ExportExpense(
        date(2026, 10, 3), "餐饮", '烧烤, 含"啤酒"\n第二行', "小A", 100, SplitMethod.EXACT,
        {A: 100},
    )
    row = parse(build_expense_csv(MEMBERS, [expense]))[1]

    assert row[2] == '烧烤, 含"啤酒"\n第二行'
    assert row[5] == "指定金额"


@pytest.mark.parametrize("text", ["=1+1", "+SUM(A1)", "-2", "@cmd", "\tx", "\rx"])
def test_formula_like_text_is_escaped(text):
    assert escape_formula(text) == "'" + text


def test_plain_text_is_unchanged():
    assert escape_formula("晚餐=好吃") == "晚餐=好吃"


def test_csv_escapes_user_text_fields():
    members = [(A, "=HYPERLINK()")]
    expense = ExportExpense(
        date(2026, 10, 3), "+分类", "=cmd|' /C calc'!A0", "@付款人", 100,
        SplitMethod.EQUAL, {A: 100},
    )
    rows = parse(build_expense_csv(members, [expense]))

    assert rows[0][6] == "'=HYPERLINK() 承担（元）"
    assert rows[1][1:4] == ["'+分类", "'=cmd|' /C calc'!A0", "'@付款人"]


def test_empty_export_has_header_only():
    assert len(parse(build_expense_csv(MEMBERS, []))) == 1
