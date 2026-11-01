"""结算主流程冒烟测试：对真实运行的后端服务执行演示流程并逐项核对结果。

脚本会注册 demo_alice、demo_bob、demo_charlie 并创建“三人出游”活动，只能指向临时数据库
启动的服务，不要对开发库或演示库运行。在 backend 目录执行：

    uv run --locked python ../scripts/settlement_smoke.py --base-url http://127.0.0.1:8765 \
        --state smoke-state.json
    # 重启服务后核对数据仍在
    uv run --locked python ../scripts/settlement_smoke.py --base-url http://127.0.0.1:8765 \
        --state smoke-state.json --verify-only
"""

import argparse
import json
import sys
import uuid

import httpx

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--base-url", required=True, help="后端服务地址，例如 http://127.0.0.1:8765")
parser.add_argument("--state", required=True, help="保存活动编号的文件，供重启后核对")
parser.add_argument("--verify-only", action="store_true", help="只核对重启后数据是否仍在")
args = parser.parse_args()

BASE = args.base_url.rstrip("/")
API = BASE + "/api/v1"
PASSWORD = "Demo-pass-2026"
STATE_FILE = args.state

# This harness targets a locally started, isolated server. Shell proxy settings
# must not route its loopback requests through an unrelated proxy.
c = httpx.Client(timeout=10, trust_env=False)
results = []


def check(label, condition, actual):
    results.append(condition)
    print(f"[{'通过' if condition else '失败'}] {label}：{actual}")


def login(name):
    r = c.post(API + "/auth/login", json={"username": name, "password": PASSWORD})
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def yuan_balances(aid, h, names):
    rows = c.get(f"{API}/activities/{aid}/balances", headers=h).json()
    return {names[r["member_id"]]: r for r in rows}


if args.verify_only:
    with open(STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)
    aid = state["activity_id"]
    h = login("demo_alice")
    act = c.get(f"{API}/activities/{aid}", headers=h).json()
    check("重启后活动状态", act["status"] == "ARCHIVED", act["status"])
    stats = c.get(f"{API}/activities/{aid}/statistics", headers=h).json()
    check("重启后消费总额（分）", stats["total_spent_cents"] == 18000, stats["total_spent_cents"])
    pays = c.get(f"{API}/activities/{aid}/payments", headers=h).json()
    check(
        "重启后付款记录",
        sorted((p["amount_cents"], p["status"]) for p in pays)
        == [(1000, "CONFIRMED"), (2000, "CONFIRMED"), (2000, "CONFIRMED")],
        [(p["amount_cents"], p["status"]) for p in pays],
    )
    sys.exit(0 if all(results) else 1)

health = c.get(BASE + "/health").json()
check("GET /health", health.get("status") == "ok", health)
paths = c.get(BASE + "/openapi.json").json()["paths"]
ops = sum(1 for p, m in paths.items() if p.startswith("/api/v1") for _ in m)
print(f"OpenAPI 业务操作数：{ops}")

for name in ["alice", "bob", "charlie"]:
    c.post(
        API + "/auth/register",
        json={"username": "demo_" + name, "display_name": name, "password": PASSWORD},
    )
H = {name: login("demo_" + name) for name in ["alice", "bob", "charlie"]}

act = c.post(
    API + "/activities", headers=H["alice"], json={"name": "三人出游", "budget_cents": 50000}
).json()
aid = act["id"]
for name in ["bob", "charlie"]:
    c.post(API + "/activities/join", headers=H[name], json={"invite_code": act["invite_code"]})
members = c.get(f"{API}/activities/{aid}/members", headers=H["alice"]).json()
ids = {m["display_name"]: m["id"] for m in members}
names = {v: k for k, v in ids.items()}

base = {"category": "餐饮", "expense_date": "2026-10-27", "split_method": "EQUAL"}
meal = base | {
    "title": "晚餐",
    "amount_cents": 12000,
    "payer_member_id": ids["alice"],
    "participants": [{"member_id": ids[n]} for n in ["alice", "bob", "charlie"]],
    "request_id": str(uuid.uuid4()),
}
taxi = base | {
    "title": "打车",
    "category": "交通",
    "amount_cents": 6000,
    "payer_member_id": ids["bob"],
    "participants": [{"member_id": ids[n]} for n in ["alice", "bob"]],
    "request_id": str(uuid.uuid4()),
}
preview = c.post(
    f"{API}/activities/{aid}/split-preview",
    headers=H["alice"],
    json={k: meal[k] for k in ["amount_cents", "split_method", "participants"]},
).json()
check(
    "分摊预览 120 元三人均摊（分）",
    [s["amount_cents"] for s in preview] == [4000] * 3,
    [s["amount_cents"] for s in preview],
)
r1 = c.post(f"{API}/activities/{aid}/expenses", headers=H["alice"], json=meal)
r2 = c.post(f"{API}/activities/{aid}/expenses", headers=H["bob"], json=taxi)
check(
    "录入两笔费用", (r1.status_code, r2.status_code) == (201, 201), (r1.status_code, r2.status_code)
)

b = yuan_balances(aid, H["alice"], names)
check(
    "T06 余额 alice/bob/charlie（分）",
    [b[n]["balance_cents"] for n in ["alice", "bob", "charlie"]] == [5000, -1000, -4000],
    [b[n]["balance_cents"] for n in ["alice", "bob", "charlie"]],
)
sug = c.get(f"{API}/activities/{aid}/settlement-suggestions", headers=H["alice"]).json()
check(
    "转账建议",
    [(names[s["payer_member_id"]], names[s["payee_member_id"]], s["amount_cents"]) for s in sug]
    == [("charlie", "alice", 4000), ("bob", "alice", 1000)],
    [(names[s["payer_member_id"]], names[s["payee_member_id"]], s["amount_cents"]) for s in sug],
)

early = c.post(
    f"{API}/activities/{aid}/payments",
    headers=H["charlie"],
    json={"payee_member_id": ids["alice"], "amount_cents": 2000, "request_id": str(uuid.uuid4())},
)
check(
    "封账前登记付款被拒绝",
    (early.status_code, early.json()["code"]) == (409, "PAYMENTS_CLOSED"),
    (early.status_code, early.json()["code"]),
)
st = c.post(f"{API}/activities/{aid}/start-settlement", headers=H["alice"]).json()
check("创建者发起结算", st["status"] == "SETTLING", st["status"])
frozen = c.patch(
    f"{API}/activities/{aid}/expenses/{r1.json()['id']}",
    headers=H["alice"],
    json={"version": 1, "amount_cents": 1},
)
check(
    "T13 封账后修改费用被拒绝",
    (frozen.status_code, frozen.json()["code"]) == (409, "ACTIVITY_LOCKED"),
    (frozen.status_code, frozen.json()["code"]),
)

rid = str(uuid.uuid4())
p1 = c.post(
    f"{API}/activities/{aid}/payments",
    headers=H["charlie"],
    json={"payee_member_id": ids["alice"], "amount_cents": 2000, "request_id": rid},
)
p1_retry = c.post(
    f"{API}/activities/{aid}/payments",
    headers=H["charlie"],
    json={"payee_member_id": ids["alice"], "amount_cents": 2000, "request_id": rid},
)
check(
    "T09 登记 20 元及同编号重试",
    (p1.status_code, p1_retry.status_code, p1_retry.json()["id"] == p1.json()["id"])
    == (201, 200, True),
    (p1.status_code, p1_retry.status_code),
)
b = yuan_balances(aid, H["alice"], names)
check(
    "T07 待确认时余额不变、额度减少",
    (
        b["charlie"]["balance_cents"],
        b["charlie"]["available_out_cents"],
        b["alice"]["available_in_cents"],
    )
    == (-4000, 2000, 3000),
    (
        b["charlie"]["balance_cents"],
        b["charlie"]["available_out_cents"],
        b["alice"]["available_in_cents"],
    ),
)
over = c.post(
    f"{API}/activities/{aid}/payments",
    headers=H["charlie"],
    json={"payee_member_id": ids["alice"], "amount_cents": 3000, "request_id": str(uuid.uuid4())},
)
check(
    "T10 超出可登记额度被拒绝",
    (over.status_code, over.json()["code"]) == (409, "PAYMENT_QUOTA_EXCEEDED"),
    (over.status_code, over.json()["code"]),
)
wrong = c.post(f"{API}/activities/{aid}/payments/{p1.json()['id']}/confirm", headers=H["bob"])
check(
    "T12 非收款人确认被拒绝",
    (wrong.status_code, wrong.json()["code"]) == (403, "PAYMENT_ACTION_FORBIDDEN"),
    (wrong.status_code, wrong.json()["code"]),
)
c.post(f"{API}/activities/{aid}/payments/{p1.json()['id']}/confirm", headers=H["alice"])
again = c.post(f"{API}/activities/{aid}/payments/{p1.json()['id']}/confirm", headers=H["alice"])
b = yuan_balances(aid, H["alice"], names)
check(
    "T08 确认后余额 alice/bob/charlie（分）",
    [b[n]["balance_cents"] for n in ["alice", "bob", "charlie"]] == [3000, -1000, -2000],
    [b[n]["balance_cents"] for n in ["alice", "bob", "charlie"]],
)
check(
    "T09 重复确认只入账一次",
    again.status_code == 200 and b["alice"]["balance_cents"] == 3000,
    (again.status_code, b["alice"]["balance_cents"]),
)

for payer, amount in [("charlie", 2000), ("bob", 1000)]:
    p = c.post(
        f"{API}/activities/{aid}/payments",
        headers=H[payer],
        json={
            "payee_member_id": ids["alice"],
            "amount_cents": amount,
            "request_id": str(uuid.uuid4()),
        },
    ).json()
    c.post(f"{API}/activities/{aid}/payments/{p['id']}/confirm", headers=H["alice"])
act = c.get(f"{API}/activities/{aid}", headers=H["alice"]).json()
b = yuan_balances(aid, H["alice"], names)
check(
    "全部确认后自动结清",
    act["status"] == "SETTLED" and all(r["balance_cents"] == 0 for r in b.values()),
    (act["status"], [r["balance_cents"] for r in b.values()]),
)
arch = c.post(f"{API}/activities/{aid}/archive", headers=H["alice"]).json()
check("T16 归档", arch["status"] == "ARCHIVED", arch["status"])

stats = c.get(f"{API}/activities/{aid}/statistics", headers=H["bob"]).json()
check(
    "T18 消费总额不含付款（分）",
    (stats["total_spent_cents"], stats["remaining_budget_cents"]) == (18000, 32000),
    (stats["total_spent_cents"], stats["remaining_budget_cents"]),
)
csv_resp = c.get(f"{API}/activities/{aid}/export.csv", headers=H["charlie"])
lines = csv_resp.content.decode("utf-8-sig").splitlines()
check(
    "T18 归档后导出 CSV",
    csv_resp.status_code == 200 and csv_resp.content[:3] == b"\xef\xbb\xbf" and len(lines) == 3,
    lines,
)
history = c.get(f"{API}/activities/{aid}/audit-logs?limit=100", headers=H["alice"]).json()
print("操作历史动作（由旧到新）：", [h["action"] for h in reversed(history)])

with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump({"activity_id": aid}, f)
print(f"共 {len(results)} 项检查，失败 {results.count(False)} 项")
sys.exit(0 if all(results) else 1)
