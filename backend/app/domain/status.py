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


ACTIVITY_STATUS_LABELS = {
    ActivityStatus.ACTIVE: "进行中",
    ActivityStatus.SETTLING: "结算中",
    ActivityStatus.SETTLED: "已结清",
    ActivityStatus.ARCHIVED: "已归档",
}

PAYMENT_STATUS_LABELS = {
    PaymentStatus.PENDING: "待确认",
    PaymentStatus.CONFIRMED: "已确认",
    PaymentStatus.REJECTED: "已拒绝",
    PaymentStatus.CANCELLED: "已撤销",
}
