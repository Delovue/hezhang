"""Add settlement payments registered between activity members.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("payer_member_id", sa.Integer(), nullable=False),
        sa.Column("payee_member_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "CONFIRMED",
                "REJECTED",
                "CANCELLED",
                name="payment_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name=op.f("fk_payments_activity_id_activities"),
        ),
        sa.ForeignKeyConstraint(
            ["payer_member_id", "activity_id"],
            ["memberships.id", "memberships.activity_id"],
            name=op.f("fk_payments_payer_member_id_memberships"),
        ),
        sa.ForeignKeyConstraint(
            ["payee_member_id", "activity_id"],
            ["memberships.id", "memberships.activity_id"],
            name=op.f("fk_payments_payee_member_id_memberships"),
        ),
        sa.UniqueConstraint(
            "activity_id",
            "payer_member_id",
            "request_id",
            name=op.f("uq_payments_activity_id"),
        ),
        sa.CheckConstraint(
            "amount_cents BETWEEN 1 AND 9007199254740991",
            name=op.f("ck_payments_amount_range"),
        ),
        sa.CheckConstraint(
            "payer_member_id <> payee_member_id", name=op.f("ck_payments_distinct_parties")
        ),
        sa.CheckConstraint("length(request_id) = 36", name=op.f("ck_payments_request_id_length")),
    )
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_payments_activity_id"), ["activity_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_payments_activity_id"))
    op.drop_table("payments")
