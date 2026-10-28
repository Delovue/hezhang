from datetime import UTC, date, datetime
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models import MAX_CENTS, MAX_IDENTIFIER, ActivityStatus, SplitMethod

Cents = Annotated[int, Field(strict=True, ge=0, le=MAX_CENTS)]
PositiveCents = Annotated[int, Field(strict=True, gt=0, le=MAX_CENTS)]
PositiveId = Annotated[int, Field(strict=True, gt=0, le=MAX_IDENTIFIER)]
ShortName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Category = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-zA-Z0-9_]{3,32}$")]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class Login(Schema):
    username: Username
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class Register(Login):
    display_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]


class UserRead(Schema):
    id: int
    username: str
    display_name: str


class TokenRead(Schema):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class ActivityCreate(Schema):
    name: ShortName
    budget_cents: Cents | None = None


class ActivityPatch(Schema):
    name: ShortName | None = None
    budget_cents: Cents | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("至少提供一个要修改的字段")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("活动名称不能为 null")
        return self


class ActivityRead(Schema):
    id: int
    name: str
    owner_id: int
    budget_cents: int | None
    status: ActivityStatus
    invite_code: str | None


class JoinActivity(Schema):
    invite_code: str = Field(min_length=1, max_length=64)


class MemberRead(Schema):
    id: int
    user_id: int
    display_name: str
    role: Literal["OWNER", "MEMBER"]


class Participant(Schema):
    member_id: PositiveId
    amount_cents: Cents | None = None
    shares: Annotated[int, Field(strict=True, gt=0, le=1_000_000)] | None = None


class SplitInput(Schema):
    amount_cents: PositiveCents
    split_method: SplitMethod
    participants: list[Participant] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_participants(self) -> Self:
        ids = [item.member_id for item in self.participants]
        if len(ids) != len(set(ids)):
            raise ValueError("分摊成员不能重复")
        for item in self.participants:
            if self.split_method == SplitMethod.EQUAL:
                if item.amount_cents is not None or item.shares is not None:
                    raise ValueError("均摊只需要 member_id")
            elif self.split_method == SplitMethod.EXACT:
                if item.amount_cents is None or item.shares is not None:
                    raise ValueError("指定金额需要 amount_cents，不能包含 shares")
            elif item.shares is None or item.amount_cents is not None:
                raise ValueError("按份数分摊需要 shares，不能包含 amount_cents")
        if self.split_method == SplitMethod.EXACT:
            if sum(item.amount_cents for item in self.participants) != self.amount_cents:
                raise ValueError("指定分摊金额合计必须等于费用总额")
        return self


class ExpenseCreate(SplitInput):
    payer_member_id: PositiveId
    title: Title
    category: Category
    expense_date: date
    notes: str | None = Field(default=None, max_length=1000)


class ExpensePatch(Schema):
    version: PositiveId
    payer_member_id: PositiveId | None = None
    title: Title | None = None
    category: Category | None = None
    expense_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)
    amount_cents: PositiveCents | None = None
    split_method: SplitMethod | None = None
    participants: list[Participant] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        changes = self.model_fields_set - {"version"}
        if not changes:
            raise ValueError("至少提供一个要修改的费用字段")
        if any(getattr(self, key) is None for key in changes - {"notes"}):
            raise ValueError("除 notes 外，费用字段不能为 null")
        if "split_method" in changes and "participants" not in changes:
            raise ValueError("修改分摊方式时必须同时提交 participants")
        return self


class ShareRead(Schema):
    member_id: int
    amount_cents: int
    shares: int | None


class ExpenseRead(Schema):
    id: int
    activity_id: int
    created_by_id: int
    payer_member_id: int
    title: str
    category: str
    amount_cents: int
    expense_date: date
    notes: str | None
    split_method: SplitMethod
    version: int
    shares: list[ShareRead]


class AuditRead(Schema):
    id: int
    actor_user_id: int
    action: str
    object_type: str
    object_id: int
    before: dict | None
    after: dict | None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def include_timezone(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
