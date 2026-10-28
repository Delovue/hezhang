from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MAX_CENTS = 9_007_199_254_740_991
MAX_IDENTIFIER = 9_007_199_254_740_991


class ActivityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    SETTLING = "SETTLING"
    SETTLED = "SETTLED"
    ARCHIVED = "ARCHIVED"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SplitMethod(StrEnum):
    EQUAL = "EQUAL"
    EXACT = "EXACT"
    SHARES = "SHARES"


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            f"budget_cents IS NULL OR budget_cents BETWEEN 0 AND {MAX_CENTS}", name="budget_range"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    budget_cents: Mapped[int | None] = mapped_column(Integer)
    invite_code: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[ActivityStatus] = mapped_column(
        Enum(ActivityStatus, native_enum=False, create_constraint=True, name="activity_status"),
        default=ActivityStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("activity_id", "user_id"),
        UniqueConstraint("id", "activity_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint("id", "activity_id"),
        ForeignKeyConstraint(
            ["payer_member_id", "activity_id"], ["memberships.id", "memberships.activity_id"]
        ),
        CheckConstraint(f"amount_cents BETWEEN 1 AND {MAX_CENTS}", name="amount_range"),
        CheckConstraint("version >= 1", name="positive_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    payer_member_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))
    amount_cents: Mapped[int] = mapped_column(Integer)
    expense_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(1000))
    split_method: Mapped[SplitMethod] = mapped_column(
        Enum(SplitMethod, native_enum=False, create_constraint=True, name="split_method")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(), server_default=func.now(), onupdate=func.now()
    )
    shares: Mapped[list["ExpenseShare"]] = relationship(
        cascade="all, delete-orphan", order_by="ExpenseShare.member_id", lazy="selectin"
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    __table_args__ = (
        UniqueConstraint("expense_id", "member_id"),
        ForeignKeyConstraint(
            ["expense_id", "activity_id"],
            ["expenses.id", "expenses.activity_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["member_id", "activity_id"], ["memberships.id", "memberships.activity_id"]
        ),
        CheckConstraint(f"amount_cents BETWEEN 0 AND {MAX_CENTS}", name="amount_range"),
        CheckConstraint("shares IS NULL OR shares > 0", name="positive_shares"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(Integer)
    expense_id: Mapped[int] = mapped_column(Integer, index=True)
    member_id: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)


class ExpenseRequest(Base):
    __tablename__ = "expense_requests"
    __table_args__ = (
        UniqueConstraint("activity_id", "created_by_id", "request_id"),
        UniqueConstraint("expense_id"),
        ForeignKeyConstraint(
            ["expense_id", "activity_id"], ["expenses.id", "expenses.activity_id"]
        ),
        CheckConstraint("length(request_id) = 36", name="request_id_length"),
        CheckConstraint("length(payload_hash) = 64", name="payload_hash_length"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    payload_hash: Mapped[str] = mapped_column(String(64))
    expense_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    object_type: Mapped[str] = mapped_column(String(30))
    object_id: Mapped[int] = mapped_column(Integer)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(), server_default=func.now())
