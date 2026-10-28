"""Add durable request records without rewriting existing ledger tables.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "expense_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expense_requests")),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_expense_requests_activity_id_activities"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_expense_requests_created_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["expense_id", "activity_id"],
            ["expenses.id", "expenses.activity_id"],
            name=op.f("fk_expense_requests_expense_id_expenses"),
        ),
        sa.UniqueConstraint(
            "activity_id",
            "created_by_id",
            "request_id",
            name=op.f("uq_expense_requests_activity_id"),
        ),
        sa.UniqueConstraint("expense_id", name=op.f("uq_expense_requests_expense_id")),
        sa.CheckConstraint(
            "length(request_id) = 36", name=op.f("ck_expense_requests_request_id_length")
        ),
        sa.CheckConstraint(
            "length(payload_hash) = 64", name=op.f("ck_expense_requests_payload_hash_length")
        ),
    )


def downgrade() -> None:
    # Existing expenses, shares and audit events remain; deduplication records do not.
    op.drop_table("expense_requests")
