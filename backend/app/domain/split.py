"""费用分摊计算。

金额一律使用整数分。所有分摊结果按成员 ID 升序返回，
并保证各成员份额之和严格等于费用总额。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.domain.errors import InvalidInputError


class SplitMethod(StrEnum):
    EQUAL = "EQUAL"
    EXACT = "EXACT"
    SHARES = "SHARES"


@dataclass(frozen=True)
class SplitParticipant:
    """分摊输入：EXACT 需要 amount_cents，SHARES 需要 shares，EQUAL 两者都不用。"""

    member_id: int
    amount_cents: int | None = None
    shares: int | None = None


@dataclass(frozen=True)
class ShareResult:
    member_id: int
    amount_cents: int
    shares: int | None = None


def _is_int(value: object) -> bool:
    # bool 是 int 的子类，金额和 ID 中出现 True/False 视为非法输入
    return isinstance(value, int) and not isinstance(value, bool)


def validate_amount(amount_cents: object) -> int:
    """校验费用总额为正整数分。"""
    if not _is_int(amount_cents):
        raise InvalidInputError("金额必须是整数分")
    if amount_cents <= 0:
        raise InvalidInputError("金额必须大于 0")
    return amount_cents


def validate_members(member_ids: Sequence[object]) -> list[int]:
    """校验分摊成员非空、为整数 ID 且不重复，返回升序排列的 ID。"""
    if not member_ids:
        raise InvalidInputError("至少需要一名分摊成员")
    for member_id in member_ids:
        if not _is_int(member_id):
            raise InvalidInputError("成员 ID 必须是整数")
    if len(set(member_ids)) != len(member_ids):
        raise InvalidInputError("分摊成员不能重复")
    return sorted(member_ids)


def split_equal(amount_cents: int, member_ids: Sequence[int]) -> dict[int, int]:
    """均摊：每人先得总额除以人数的整数部分，余下的分按成员 ID 升序逐一补 1 分。

    例：10000 分分给三人得到 3334、3333、3333。
    """
    amount_cents = validate_amount(amount_cents)
    ordered = validate_members(member_ids)
    base, remainder = divmod(amount_cents, len(ordered))
    return {
        member_id: base + (1 if index < remainder else 0)
        for index, member_id in enumerate(ordered)
    }


def split_exact(amount_cents: int, amounts: Mapping[int, int]) -> dict[int, int]:
    """指定金额：各成员份额为非负整数分，合计必须严格等于总额。"""
    amount_cents = validate_amount(amount_cents)
    ordered = validate_members(list(amounts))
    for member_id in ordered:
        share = amounts[member_id]
        if not _is_int(share):
            raise InvalidInputError("指定金额必须是整数分")
        if share < 0:
            raise InvalidInputError("指定金额不能为负数")
    total = sum(amounts.values())
    if total != amount_cents:
        raise InvalidInputError(f"指定金额合计 {total} 分，与总额 {amount_cents} 分不一致")
    return {member_id: amounts[member_id] for member_id in ordered}


def split_shares(amount_cents: int, shares: Mapping[int, int]) -> dict[int, int]:
    """按份数：先取每人精确金额的整数部分，再按小数余数从大到小逐一补 1 分，
    余数相同按成员 ID 升序。

    例：60000 分按 2:2:1:1 得到 20000、20000、10000、10000。
    """
    amount_cents = validate_amount(amount_cents)
    ordered = validate_members(list(shares))
    for member_id in ordered:
        count = shares[member_id]
        if not _is_int(count):
            raise InvalidInputError("份数必须是整数")
        if count <= 0:
            raise InvalidInputError("份数必须是正整数")
    total_shares = sum(shares.values())

    # 用整数除法得到整数部分和余数，避免浮点误差
    result: dict[int, int] = {}
    remainders: dict[int, int] = {}
    for member_id in ordered:
        result[member_id], remainders[member_id] = divmod(
            amount_cents * shares[member_id], total_shares
        )
    leftover = amount_cents - sum(result.values())
    by_remainder = sorted(ordered, key=lambda member_id: (-remainders[member_id], member_id))
    for member_id in by_remainder[:leftover]:
        result[member_id] += 1
    return result


def compute_split(
    amount_cents: int, method: SplitMethod, participants: Sequence[SplitParticipant]
) -> list[ShareResult]:
    """分摊统一入口，费用保存和分摊预览共用。结果按成员 ID 升序。"""
    member_ids = validate_members([p.member_id for p in participants])
    by_member = {p.member_id: p for p in participants}

    if method == SplitMethod.EQUAL:
        amounts = split_equal(amount_cents, member_ids)
        return [ShareResult(m, amounts[m]) for m in member_ids]
    if method == SplitMethod.EXACT:
        if any(p.amount_cents is None for p in participants):
            raise InvalidInputError("指定金额分摊需要填写每位成员的金额")
        amounts = split_exact(amount_cents, {m: by_member[m].amount_cents for m in member_ids})
        return [ShareResult(m, amounts[m]) for m in member_ids]
    if method == SplitMethod.SHARES:
        if any(p.shares is None for p in participants):
            raise InvalidInputError("按份数分摊需要填写每位成员的份数")
        counts = {m: by_member[m].shares for m in member_ids}
        amounts = split_shares(amount_cents, counts)
        return [ShareResult(m, amounts[m], counts[m]) for m in member_ids]
    raise InvalidInputError(f"不支持的分摊方式：{method}")
