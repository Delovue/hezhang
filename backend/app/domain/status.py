"""活动与付款状态的中文名称。接口和数据库使用英文值，页面与提示展示中文。"""

from app.models import ActivityStatus, PaymentStatus

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
