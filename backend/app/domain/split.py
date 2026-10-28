"""费用分摊计算。

金额一律使用整数分。所有分摊结果按成员 ID 升序返回，
并保证各成员份额之和严格等于费用总额。
"""

from collections.abc import Mapping, Sequence

from app.domain.errors import InvalidInputError


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
