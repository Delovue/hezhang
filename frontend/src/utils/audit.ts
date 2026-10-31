import type { AuditEntry, Member } from '../api/types'
import { statusLabels } from './activity'
import { paymentLabels } from './payment'
import { splitLabels } from './expense'
import { formatCents } from './money'

export const actionLabels: Record<string, string> = {
  ACTIVITY_CREATED: '创建活动', ACTIVITY_UPDATED: '修改活动', MEMBER_JOINED: '加入活动',
  EXPENSE_CREATED: '新增费用', EXPENSE_UPDATED: '修改费用', EXPENSE_DELETED: '删除费用',
  SETTLEMENT_STARTED: '发起结算', ACTIVITY_SETTLED: '自动结清', ACTIVITY_ARCHIVED: '归档活动',
  PAYMENT_CREATED: '登记付款', PAYMENT_CONFIRMED: '确认收款', PAYMENT_REJECTED: '拒绝付款', PAYMENT_CANCELLED: '撤销登记',
}
export const objectLabels: Record<string, string> = { activity: '活动', membership: '成员', expense: '费用', payment: '付款' }
const fields: Record<string, string> = { name: '活动名称', title: '费用名称', category: '分类', amount_cents: '金额', budget_cents: '预算',
  status: '状态', expense_date: '费用日期', notes: '备注', version: '版本', split_method: '分摊方式', shares: '成员分摊',
  payer_member_id: '付款成员', payee_member_id: '收款成员', owner_id: '创建者', created_by_id: '记录者', member_id: '成员', user_id: '用户', is_deleted: '已删除' }
const states: Record<string, string> = { ...statusLabels, ...paymentLabels, ...splitLabels }
function valueText(key: string, value: unknown, members: Member[]): string {
  if (value === undefined) return '—'
  if (value === null || value === '') return '未设置'
  if (key.endsWith('_cents') && typeof value === 'number') return `¥ ${formatCents(value)}`
  if (['payer_member_id', 'payee_member_id', 'member_id'].includes(key)) return members.find(m => m.id === value)?.display_name || `成员 ${value}`
  if (['owner_id', 'created_by_id', 'user_id'].includes(key)) return members.find(m => m.user_id === value)?.display_name || `用户 ${value}`
  if (key === 'shares' && Array.isArray(value)) return value.map(row => `${valueText('member_id', row.member_id, members)} ¥ ${formatCents(row.amount_cents)}${row.shares ? `（${row.shares} 份）` : ''}`).join('；')
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return ['status', 'split_method'].includes(key) ? states[String(value)] || String(value) : String(value)
}
export function auditChanges(entry: AuditEntry, members: Member[]) {
  const before = entry.before || {}, after = entry.after || {}
  return [...new Set([...Object.keys(before), ...Object.keys(after)])]
    .filter(key => !['id', 'activity_id'].includes(key) && JSON.stringify(before[key]) !== JSON.stringify(after[key]))
    .map(key => ({ key, label: fields[key] || key, before: valueText(key, before[key], members), after: valueText(key, after[key], members) }))
}
