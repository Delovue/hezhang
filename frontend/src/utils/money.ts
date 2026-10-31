/** Parse decimal text with integer arithmetic; blank optional budget differs from zero budget. */
export function parseYuan(input: string, optional = false): number | null {
  const text = input.trim()
  if (!text && optional) return null
  if (!/^\d+(?:\.\d{1,2})?$/.test(text)) throw new Error('金额请输入非负数字，最多保留两位小数')
  const [whole = '0', decimal = ''] = text.split('.')
  const cents = BigInt(whole) * 100n + BigInt(decimal.padEnd(2, '0'))
  if (cents > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('金额超出允许范围')
  return Number(cents)
}

export function formatCents(cents: number | null): string {
  if (cents === null) return '未设置'
  if (!Number.isSafeInteger(cents)) throw new Error('金额必须为安全整数分')
  const value = BigInt(cents)
  const absolute = value < 0 ? -value : value
  return `${value < 0 ? '-' : ''}${(absolute / 100n).toLocaleString('zh-CN')}.${String(absolute % 100n).padStart(2, '0')}`
}

export function centsToInput(cents: number | null): string {
  return cents === null ? '' : formatCents(cents).replaceAll(',', '')
}

/** 带正负号的余额：应收为“+”，应付为“−”，平账不带符号。 */
export function signedCents(cents: number): string {
  if (cents === 0) return formatCents(0)
  return `${cents > 0 ? '+' : '−'}${formatCents(Math.abs(cents))}`
}
