"""转账建议生成。

使用扣除待确认占用后的可登记额度。每轮把债务人和债权人分别按剩余额度降序、
成员 ID 升序排序，取双方首位匹配二者额度的较小值，直至一方额度耗尽。
建议只是计算结果，不修改余额；保证执行后余额归零，但不保证全局转账次数最少。
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.balance import MemberBalance


@dataclass(frozen=True)
class Transfer:
    payer_id: int
    payee_id: int
    amount_cents: int


def _pick(remaining: dict[int, int]) -> int:
    return min(remaining, key=lambda member_id: (-remaining[member_id], member_id))


def suggest_transfers(balances: Sequence[MemberBalance]) -> list[Transfer]:
    debtors = {b.member_id: b.available_out_cents for b in balances if b.available_out_cents > 0}
    creditors = {b.member_id: b.available_in_cents for b in balances if b.available_in_cents > 0}

    transfers: list[Transfer] = []
    while debtors and creditors:
        payer_id, payee_id = _pick(debtors), _pick(creditors)
        amount = min(debtors[payer_id], creditors[payee_id])
        transfers.append(Transfer(payer_id, payee_id, amount))

        debtors[payer_id] -= amount
        creditors[payee_id] -= amount
        if debtors[payer_id] == 0:
            del debtors[payer_id]
        if creditors[payee_id] == 0:
            del creditors[payee_id]
    return transfers
