"""成员余额与可登记额度计算。

余额 = 累计垫付 - 累计承担 + 已确认付出 - 已确认收到，正数应收、负数应付。
待确认付款不改变余额，但占用双方的可登记额度：
    可登记付出 = max(-余额, 0) - 待确认付出合计
    可登记收到 = max( 余额, 0) - 待确认收到合计
余额不落库，每次由有效费用、分摊和付款流水重新计算。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.domain.status import PaymentStatus


@dataclass(frozen=True)
class ExpenseEntry:
    """一笔有效费用：付款人垫付 amount_cents，按 shares 由各成员承担。"""

    payer_id: int
    amount_cents: int
    shares: Mapping[int, int]


@dataclass(frozen=True)
class PaymentEntry:
    payer_id: int
    payee_id: int
    amount_cents: int
    status: PaymentStatus


@dataclass(frozen=True)
class MemberBalance:
    member_id: int
    paid_cents: int  # 累计垫付
    owed_cents: int  # 累计承担
    confirmed_out_cents: int  # 已确认付出
    confirmed_in_cents: int  # 已确认收到
    pending_out_cents: int  # 待确认付出
    pending_in_cents: int  # 待确认收到

    @property
    def balance_cents(self) -> int:
        return (
            self.paid_cents
            - self.owed_cents
            + self.confirmed_out_cents
            - self.confirmed_in_cents
        )

    @property
    def available_out_cents(self) -> int:
        return max(-self.balance_cents, 0) - self.pending_out_cents

    @property
    def available_in_cents(self) -> int:
        return max(self.balance_cents, 0) - self.pending_in_cents


def compute_balances(
    member_ids: Sequence[int],
    expenses: Sequence[ExpenseEntry],
    payments: Sequence[PaymentEntry],
) -> list[MemberBalance]:
    """计算活动内每位成员的余额明细，按成员 ID 升序返回。

    expenses 只应包含未删除的费用；payments 可包含任意状态，
    已拒绝和已撤销的付款不计入。数据引用非成员或分摊不守恒时抛出 ValueError，
    这类情况说明存储数据已损坏，而不是用户输入错误。
    """
    totals = {
        member_id: dict(paid=0, owed=0, c_out=0, c_in=0, p_out=0, p_in=0)
        for member_id in member_ids
    }

    def row(member_id: int) -> dict[str, int]:
        if member_id not in totals:
            raise ValueError(f"成员 {member_id} 不属于该活动")
        return totals[member_id]

    for expense in expenses:
        if sum(expense.shares.values()) != expense.amount_cents:
            raise ValueError("费用分摊合计与总额不一致")
        row(expense.payer_id)["paid"] += expense.amount_cents
        for member_id, share in expense.shares.items():
            row(member_id)["owed"] += share

    for payment in payments:
        if payment.status == PaymentStatus.CONFIRMED:
            row(payment.payer_id)["c_out"] += payment.amount_cents
            row(payment.payee_id)["c_in"] += payment.amount_cents
        elif payment.status == PaymentStatus.PENDING:
            row(payment.payer_id)["p_out"] += payment.amount_cents
            row(payment.payee_id)["p_in"] += payment.amount_cents

    return [
        MemberBalance(
            member_id=member_id,
            paid_cents=t["paid"],
            owed_cents=t["owed"],
            confirmed_out_cents=t["c_out"],
            confirmed_in_cents=t["c_in"],
            pending_out_cents=t["p_out"],
            pending_in_cents=t["p_in"],
        )
        for member_id, t in sorted(totals.items())
    ]
