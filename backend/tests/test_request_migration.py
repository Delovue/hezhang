from datetime import date
from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.database import build_engine, transaction
from app.main import create_app
from app.models import (
    Activity,
    AuditLog,
    Expense,
    ExpenseRequest,
    ExpenseShare,
    Membership,
    SplitMethod,
    User,
)
from tests.conftest import migration_config
from tests.test_expenses import create


def test_health_requires_current_migration(settings):
    config = migration_config(settings.database_url)
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 503
        command.upgrade(config, "0001")
        old = client.get("/health")
        assert old.status_code == 503
        assert old.json()["expected_schema_revision"] == "0003"
        command.upgrade(config, "head")
        assert client.get("/health").json() == {"status": "ok", "schema_revision": "0003"}
        with transaction(client.app.state.engine, write=True) as session:
            session.execute(text("UPDATE alembic_version SET version_num = 'unknown'"))
        assert client.get("/health").status_code == 503
        with transaction(client.app.state.engine, write=True) as session:
            session.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0002')"))
        assert client.get("/health").status_code == 503


def ledger_snapshot(engine):
    tables = ["users", "activities", "memberships", "expenses", "expense_shares", "audit_logs"]
    with transaction(engine) as session:
        return {
            table: list(session.execute(text(f"SELECT * FROM {table} ORDER BY id")).mappings())
            for table in tables
        }


def test_upgrade_preserves_existing_ledger_and_only_adds_request_table(settings):
    config = migration_config(settings.database_url)
    command.upgrade(config, "0001")
    engine = build_engine(settings.database_url)
    try:
        with transaction(engine, write=True) as session:
            user = User(username="legacy", display_name="旧用户", password_hash="test-only-hash")
            session.add(user)
            session.flush()
            activity = Activity(name="已有旅行", owner_id=user.id, invite_code="legacy-test-code")
            session.add(activity)
            session.flush()
            member = Membership(activity_id=activity.id, user_id=user.id)
            session.add(member)
            session.flush()
            for deleted in [False, True]:
                expense = Expense(
                    activity_id=activity.id,
                    created_by_id=user.id,
                    payer_member_id=member.id,
                    title="已删除旧账" if deleted else "保留旧账",
                    category="餐饮",
                    amount_cents=6001,
                    expense_date=date(2026, 10, 27),
                    notes="保留中文及原有版本",
                    split_method=SplitMethod.EQUAL,
                    version=3,
                    is_deleted=deleted,
                    shares=[
                        ExpenseShare(
                            activity_id=activity.id, member_id=member.id, amount_cents=6001
                        )
                    ],
                )
                session.add(expense)
                session.flush()
                session.add(
                    AuditLog(
                        activity_id=activity.id,
                        actor_user_id=user.id,
                        action="EXPENSE_CREATED",
                        object_type="expense",
                        object_id=expense.id,
                        after={"amount_cents": 6001},
                    )
                )
        before = ledger_snapshot(engine)
        command.upgrade(config, "head")
        assert "expense_requests" in inspect(engine).get_table_names()
        assert ledger_snapshot(engine) == before
        command.check(config)
        with transaction(engine, write=True) as session:
            expense = session.scalar(select(Expense).where(Expense.is_deleted.is_(False)))
            session.add(
                ExpenseRequest(
                    activity_id=expense.activity_id,
                    created_by_id=expense.created_by_id,
                    expense_id=expense.id,
                    request_id=str(uuid4()),
                    payload_hash="0" * 64,
                )
            )
        # This populated database is test-only. Downgrade removes only deduplication metadata.
        command.downgrade(config, "0001")
        assert "expense_requests" not in inspect(engine).get_table_names()
        assert ledger_snapshot(engine) == before
        command.upgrade(config, "head")
        assert ledger_snapshot(engine) == before
        with transaction(engine) as session:
            assert session.scalars(select(ExpenseRequest)).all() == []
    finally:
        engine.dispose()


def test_request_unique_keys_and_activity_reference_are_enforced(
    client, actors, group, expense_data
):
    first = create(client, actors, group, expense_data)
    second = create(client, actors, group, expense_data)
    other = client.post(
        "/api/v1/activities", headers=actors["alice"]["headers"], json={"name": "另一活动"}
    ).json()
    key = str(uuid4())
    values = {
        "activity_id": group["id"],
        "created_by_id": actors["alice"]["user"]["id"],
        "expense_id": first["id"],
        "request_id": key,
        "payload_hash": "0" * 64,
    }
    with transaction(client.app.state.engine, write=True) as session:
        session.add(ExpenseRequest(**values))
    for change in [
        {"expense_id": second["id"]},
        {"request_id": str(uuid4())},
        {"expense_id": second["id"], "activity_id": other["id"], "request_id": str(uuid4())},
    ]:
        with (
            pytest.raises(IntegrityError),
            transaction(client.app.state.engine, write=True) as session,
        ):
            session.add(ExpenseRequest(**(values | change)))
