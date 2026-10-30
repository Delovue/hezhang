import type { ActivityStatus } from '../api/types'

export const statusLabels: Record<ActivityStatus, string> = {
  ACTIVE: '进行中', SETTLING: '结算中', SETTLED: '已结清', ARCHIVED: '已归档',
}
export const statusDescriptions: Record<ActivityStatus, string> = {
  ACTIVE: '成员可以加入活动，共同记录支出。',
  SETTLING: '账目已冻结，等待成员完成付款确认。',
  SETTLED: '全部账目已结清，等待创建者归档。',
  ARCHIVED: '活动已归档，可以继续查看账目和统计。',
}
export function parseActivityId(value: unknown): number | null {
  if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) return null
  const id = Number(value)
  return Number.isSafeInteger(id) ? id : null
}
export function safeRedirect(value: unknown): string {
  return typeof value === 'string' && /^\/activities(?:\/[1-9]\d*)?$/.test(value) ? value : '/activities'
}
