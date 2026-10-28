"""活动与付款状态枚举，接口和数据库中使用英文值，页面展示中文。"""

from enum import StrEnum


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
