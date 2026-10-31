import { expect, it } from 'vitest'
import { auditChanges } from '../src/utils/audit'
import type { AuditEntry, Member } from '../src/api/types'
const members: Member[] = [{ id: 4, user_id: 8, display_name: '小王', role: 'OWNER' }]
const entry: AuditEntry = { id: 1, actor_user_id: 8, action: 'EXPENSE_UPDATED', object_type: 'expense', object_id: 3, created_at: '',
  before: { id: 3, amount_cents: 100, notes: '原备注', payer_member_id: 4 }, after: { id: 3, amount_cents: 101, notes: null, payer_member_id: 4 } }
it('shows only changed fields, with exact cents and explicit cleared values', () => {
  expect(auditChanges(entry, members)).toEqual([
    { key: 'amount_cents', label: '金额', before: '¥ 1.00', after: '¥ 1.01' },
    { key: 'notes', label: '备注', before: '原备注', after: '未设置' },
  ])
})
it('renders member and share snapshots without exposing raw JSON', () => {
  const changes = auditChanges({ ...entry, before: null, after: { payer_member_id: 4, shares: [{ member_id: 4, amount_cents: 101, shares: 2 }], status: 'PENDING' } }, members)
  expect(changes.map(row => row.after)).toEqual(['小王', '小王 ¥ 1.01（2 份）', '待收款人确认'])
})
it('does not translate user-entered text that happens to match a status code', () => {
  expect(auditChanges({ ...entry, before: null, after: { title: 'ACTIVE', notes: 'EQUAL' } }, members).map(row => row.after)).toEqual(['ACTIVE', 'EQUAL'])
})
