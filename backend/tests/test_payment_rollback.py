"""T15：付款与状态变更在写入历史时失败，必须整体回滚。"""

from uuid import uuid4

import pytest

from app.services import lifecycle as lifecycle_service
from app.services import payment as payment_service
from tests.test_payments_api import balance_rows, ledger, pay


def failing(original):
    def fail_after_audit(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected failure after audit flush")

    return fail_after_audit


def test_t15_failed_registration_leaves_no_payment_and_frees_request_id(
    client, actors, settling, monkeypatch
):
    request_id = str(uuid4())
    with monkeypatch.context() as patch:
        patch.setattr(payment_service, "record_audit", failing(payment_service.record_audit))
        with pytest.raises(RuntimeError, match="injected failure"):
            pay(client, actors, settling, "charlie", "alice", 2000, request_id)

    assert ledger(client, actors, settling, "payments") == []
    assert balance_rows(client, actors, settling)["charlie"]["pending_out_cents"] == 0
    assert pay(client, actors, settling, "charlie", "alice", 2000, request_id).status_code == 201


def test_t15_failed_final_confirmation_rolls_back_payment_and_activity(
    client, actors, settling, monkeypatch
):
    charlie = pay(client, actors, settling, "charlie", "alice", 4000).json()
    bob = pay(client, actors, settling, "bob", "alice", 1000).json()
    client.post(
        f"/api/v1/activities/{settling['id']}/payments/{charlie['id']}/confirm",
        headers=actors["alice"]["headers"],
    )
    history_before = ledger(client, actors, settling, "audit-logs")
    confirm_path = f"/api/v1/activities/{settling['id']}/payments/{bob['id']}/confirm"

    # 最后一笔确认会触发自动结清；在写入结清历史时失败
    with monkeypatch.context() as patch:
        patch.setattr(lifecycle_service, "record_audit", failing(lifecycle_service.record_audit))
        with pytest.raises(RuntimeError, match="injected failure"):
            client.post(confirm_path, headers=actors["alice"]["headers"])

    assert ledger(client, actors, settling, "payments")[0]["status"] == "PENDING"
    assert balance_rows(client, actors, settling)["bob"]["balance_cents"] == -1000
    activity = client.get(
        f"/api/v1/activities/{settling['id']}", headers=actors["alice"]["headers"]
    ).json()
    assert activity["status"] == "SETTLING"
    assert ledger(client, actors, settling, "audit-logs") == history_before

    retry = client.post(confirm_path, headers=actors["alice"]["headers"])
    assert retry.json()["status"] == "CONFIRMED"
