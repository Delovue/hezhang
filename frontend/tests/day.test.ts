import { expect, it } from 'vitest'
import type { Expense } from '../src/api/types'
import { categoryTone, dayLabel, groupByDay } from '../src/utils/expense'
import { signedCents } from '../src/utils/money'

function expense(id: number, date: string, amount: number): Expense {
  return { id, activity_id: 1, created_by_id: 1, version: 1, title: `费用 ${id}`, category: '餐饮', amount_cents: amount,
    expense_date: date, notes: null, payer_member_id: 1, split_method: 'EQUAL', shares: [] }
}

it('labels calendar days with the weekday regardless of time zone', () => {
  expect(dayLabel('2026-10-26')).toBe('10月26日 周一')
  expect(dayLabel('2026-01-04')).toBe('1月4日 周日')
})

it('groups consecutive expenses of the same day and sums each day exactly', () => {
  const groups = groupByDay([expense(3, '2026-10-26', 8600), expense(2, '2026-10-25', 22500), expense(1, '2026-10-25', 52000)])
  expect(groups.map(group => [group.date, group.total, group.rows.map(row => row.id)])).toEqual([
    ['2026-10-26', 8600, [3]], ['2026-10-25', 74500, [2, 1]],
  ])
  expect(groupByDay([])).toEqual([])
})

it('keeps a stable icon tone for every category', () => {
  expect(categoryTone('餐饮')).toBe('cat-0')
  expect(categoryTone(' 交通 ')).toBe('cat-1')
  expect(categoryTone('装备')).toBe(categoryTone('装备'))
  expect(categoryTone('装备')).toMatch(/^cat-[0-4]$/)
})

it('signs balances so receivable and payable amounts read differently', () => {
  expect([26700, -30100, 0].map(signedCents)).toEqual(['+267.00', '−301.00', '0.00'])
})

it('treats object prototype names as ordinary custom categories', () => {
  for (const category of ['constructor', '__proto__', 'toString']) {
    expect(categoryTone(category)).toMatch(/^cat-[0-4]$/)
  }
})
