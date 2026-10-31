import { describe, expect, it } from 'vitest'
import { expenseInput, type ExpenseDraft } from '../src/utils/expense'

function draft(): ExpenseDraft {
  return { title: ' 餐费 ', category: '餐饮', amount: '0.30', date: '2026-10-30', notes: '', payer: 7, method: 'EXACT',
    participants: [{ member_id: 7, selected: true, amount: '0.10', count: '1' }, { member_id: 9, selected: true, amount: '0.20', count: '2' }] }
}
describe('expense form rules', () => {
  it('sums decimal inputs exactly and excludes unselected members', () => {
    const value = draft()
    value.participants.push({ member_id: 10, selected: false, amount: 'invalid', count: 'invalid' })
    expect(expenseInput(value)).toMatchObject({ title: '餐费', amount_cents: 30, notes: null,
      participants: [{ member_id: 7, amount_cents: 10 }, { member_id: 9, amount_cents: 20 }] })
  })
  it('rejects an exact allocation that is one cent short', () => {
    const value = draft(); value.amount = '0.31'
    expect(() => expenseInput(value)).toThrow('合计')
  })
  it('sends only the inputs relevant to each split method', () => {
    const value = draft(); value.method = 'EQUAL'
    expect(expenseInput(value).participants).toEqual([{ member_id: 7 }, { member_id: 9 }])
    value.method = 'SHARES'
    expect(expenseInput(value).participants).toEqual([{ member_id: 7, shares: 1 }, { member_id: 9, shares: 2 }])
  })
  it.each(['0', '-1', '1.5', '1e2', '1000001'])('rejects invalid share count %s', count => {
    const value = draft(); value.method = 'SHARES'; value.participants[0]!.count = count
    expect(() => expenseInput(value)).toThrow('份数')
  })
  it('rejects zero expense and empty participants', () => {
    const value = draft(); value.amount = '0'
    expect(() => expenseInput(value)).toThrow('大于 0')
    value.amount = '1'; value.participants.forEach(row => row.selected = false)
    expect(() => expenseInput(value)).toThrow('至少')
  })
})
