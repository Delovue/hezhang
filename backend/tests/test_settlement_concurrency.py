"""T09–T11、T13 并发场景。

TestClient 在线程中并发调用，引擎使用 NullPool，每个请求是独立的 SQLite 连接，
与真实部署中多个请求访问同一数据库文件的情况一致。
"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

from sqlalchemy import event

from app.database import transaction
from app.models import Payment
from tests.test_payments_api import balance_rows, ledger, pay


def run_together(*calls):
    barrier = Barrier(len(calls))

    def run(call):
        barrier.wait(timeout=5)
        return call()

    with ThreadPoolExecutor(max_workers=len(calls)) as executor:
        return list(executor.map(run, calls))


def act(client, actors, group, payment, action, actor):
    return client.post(
        f"/api/v1/activities/{group['id']}/payments/{payment['id']}/{action}",
        headers=actors[actor]["headers"],
    )


def test_t10_concurrent_registrations_cannot_overuse_quota(client, actors, settling):
    responses = run_together(
        lambda: pay(client, actors, settling, "charlie", "alice", 3000),
        lambda: pay(client, actors, settling, "charlie", "alice", 3000),
    )

    assert sorted(r.status_code for r in responses) == [201, 409]
    assert balance_rows(client, actors, settling)["charlie"]["pending_out_cents"] == 3000


def test_t09_concurrent_retries_register_once(client, actors, settling):
    request_id = str(uuid4())
    responses = run_together(
        lambda: pay(client, actors, settling, "charlie", "alice", 2000, request_id),
        lambda: pay(client, actors, settling, "charlie", "alice", 2000, request_id),
    )

    assert sorted(r.status_code for r in responses) == [200, 201]
    assert responses[0].json() == responses[1].json()
    assert len(ledger(client, actors, settling, "payments")) == 1
    assert len(ledger(client, actors, settling, "audit-logs?action=PAYMENT_CREATED")) == 1


def test_t09_concurrent_confirms_count_once(client, actors, settling):
    payment = pay(client, actors, settling, "charlie", "alice", 4000).json()
    responses = run_together(
        lambda: act(client, actors, settling, payment, "confirm", "alice"),
        lambda: act(client, actors, settling, payment, "confirm", "alice"),
    )

    assert [r.status_code for r in responses] == [200, 200]
    assert balance_rows(client, actors, settling)["alice"]["balance_cents"] == 1000
    assert len(ledger(client, actors, settling, "audit-logs?action=PAYMENT_CONFIRMED")) == 1


def test_t11_confirm_and_cancel_race_has_one_terminal_state(client, actors, settling):
    payment = pay(client, actors, settling, "charlie", "alice", 4000).json()
    confirm, cancel = run_together(
        lambda: act(client, actors, settling, payment, "confirm", "alice"),
        lambda: act(client, actors, settling, payment, "cancel", "charlie"),
    )

    assert sorted([confirm.status_code, cancel.status_code]) == [200, 409]
    winner = confirm if confirm.status_code == 200 else cancel
    final = ledger(client, actors, settling, "payments")[0]
    assert final["status"] == winner.json()["status"]
    charlie = balance_rows(client, actors, settling)["charlie"]
    assert charlie["balance_cents"] == (0 if final["status"] == "CONFIRMED" else -4000)
    assert charlie["pending_out_cents"] == 0
    history = ledger(client, actors, settling, "audit-logs?object_type=payment")
    assert [row["action"] for row in history] == [
        {"CONFIRMED": "PAYMENT_CONFIRMED", "CANCELLED": "PAYMENT_CANCELLED"}[final["status"]],
        "PAYMENT_CREATED",
    ]


def test_t10_registration_waits_for_lock_then_sees_reserved_quota(client, actors, settling):
    """持有写锁期间插入一笔待确认付款，并发登记必须等待写锁，并基于最新占用拒绝超额。"""
    engine = client.app.state.engine
    ids = settling["member_ids"]
    attempted = Event()

    def observe_begin(_conn, _cursor, statement, _parameters, _context, _many):
        if statement == "BEGIN IMMEDIATE":
            attempted.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with transaction(engine, write=True) as holder:
            holder.add(
                Payment(
                    activity_id=settling["id"],
                    payer_member_id=ids["charlie"],
                    payee_member_id=ids["alice"],
                    amount_cents=3000,
                    request_id=str(uuid4()),
                )
            )
            holder.flush()
            event.listen(engine, "before_cursor_execute", observe_begin)
            future = executor.submit(pay, client, actors, settling, "charlie", "alice", 3000)
            try:
                assert attempted.wait(timeout=5), "registration did not request the write lock"
            finally:
                event.remove(engine, "before_cursor_execute", observe_begin)
        response = future.result(timeout=5)

    assert response.status_code == 409
    assert len(ledger(client, actors, settling, "payments")) == 1


def test_t13_seal_and_edit_race_never_changes_sealed_ledger(client, actors, trip):
    expense = client.get(
        f"/api/v1/activities/{trip['id']}/expenses", headers=actors["alice"]["headers"]
    ).json()[-1]
    seal, edit = run_together(
        lambda: client.post(
            f"/api/v1/activities/{trip['id']}/start-settlement",
            headers=actors["alice"]["headers"],
        ),
        lambda: client.patch(
            f"/api/v1/activities/{trip['id']}/expenses/{expense['id']}",
            headers=actors["alice"]["headers"],
            json={"version": expense["version"], "amount_cents": 15000},
        ),
    )

    assert seal.status_code == 200
    assert edit.status_code in {200, 409}
    actions = [
        row["action"]
        for row in reversed(ledger(client, actors, trip, "audit-logs"))
        if row["action"] in {"EXPENSE_UPDATED", "SETTLEMENT_STARTED"}
    ]
    # 封账之后不能再出现费用修改
    assert actions[-1] == "SETTLEMENT_STARTED"
    expected_alice = 7000 if edit.status_code == 200 else 5000
    assert balance_rows(client, actors, trip)["alice"]["balance_cents"] == expected_alice
