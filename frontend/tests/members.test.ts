import { expect, it } from 'vitest'
import type { Member } from '../src/api/types'
import { avatarTone, initial, labelMembers } from '../src/utils/members'
it('distinguishes repeated names in every expense and payment choice without changing IDs', () => {
  const rows: Member[] = [
    { id: 3, user_id: 10, display_name: '小王', role: 'OWNER' },
    { id: 6, user_id: 12, display_name: '小王', role: 'MEMBER' },
    { id: 8, user_id: 15, display_name: '小李', role: 'MEMBER' },
  ]
  const labeled = labelMembers(rows)
  expect(labeled.map(row => row.display_name)).toEqual(['小王（#3）', '小王（#6）', '小李'])
  expect(labeled.map(row => row.id)).toEqual([3,6,8])
  expect(rows[0]!.display_name).toBe('小王')
})

it('uses a distinguishing avatar character for Chinese, Latin and numbered duplicate names', () => {
  expect(['小王', '小李', '王小明', 'alice', '小王（#6）', 'A', ' '].map(initial)).toEqual(['王', '李', '明', 'A', '王', 'A', '?'])
})

it('keeps the same avatar tone for the same member', () => {
  expect(avatarTone(3)).toBe(avatarTone(3))
  expect(new Set([1, 2, 3, 4, 5].map(avatarTone)).size).toBe(5)
})
