import type { Expense, ExpenseInput, SplitMethod } from '../api/types'
import { parseYuan } from './money'

export const splitLabels: Record<SplitMethod, string> = { EQUAL: '均摊', EXACT: '指定金额', SHARES: '按份数' }
export interface DraftParticipant { member_id: number; selected: boolean; amount: string; count: string }
export interface ExpenseDraft {
  title: string; category: string; amount: string; date: string; notes: string
  payer: number; method: SplitMethod; participants: DraftParticipant[]
}
export function expenseInput(draft: ExpenseDraft): ExpenseInput {
  const amount = parseYuan(draft.amount)!
  if (amount <= 0) throw new Error('费用总额必须大于 0')
  if (!draft.title.trim()) throw new Error('请填写费用名称')
  if (!draft.category.trim()) throw new Error('请填写费用分类')
  if (!draft.date) throw new Error('请选择费用日期')
  if (!Number.isSafeInteger(draft.payer) || draft.payer <= 0) throw new Error('请选择垫付人')
  const selected = draft.participants.filter(row => row.selected)
  if (!selected.length) throw new Error('至少选择一名分摊成员')
  const participants = selected.map(row => {
    if (draft.method === 'EXACT') return { member_id: row.member_id, amount_cents: parseYuan(row.amount)! }
    if (draft.method === 'SHARES') {
      if (!/^\d+$/.test(row.count) || Number(row.count) < 1 || Number(row.count) > 1_000_000) throw new Error('份数须为 1–1000000 的整数')
      return { member_id: row.member_id, shares: Number(row.count) }
    }
    return { member_id: row.member_id }
  })
  if (draft.method === 'EXACT' && participants.reduce((sum, row) => sum + BigInt('amount_cents' in row ? row.amount_cents! : 0), 0n) !== BigInt(amount)) {
    throw new Error('指定金额合计必须等于费用总额')
  }
  return { title: draft.title.trim(), category: draft.category.trim(), amount_cents: amount,
    expense_date: draft.date, notes: draft.notes.trim() || null, payer_member_id: draft.payer,
    split_method: draft.method, participants }
}

const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
/** 账目按天分组的标题，例如“10月26日 周一”；日期按日历日解析，不受时区影响。 */
export function dayLabel(date: string): string {
  const [year, month, day] = date.split('-').map(Number)
  return `${month}月${day}日 ${weekdays[new Date(Date.UTC(year!, month! - 1, day)).getUTCDay()]}`
}

/** 将已按日期排序的费用合并为连续的日期分组，并累计当天金额。 */
export function groupByDay(rows: Expense[]): { date: string; total: number; rows: Expense[] }[] {
  const groups: { date: string; total: number; rows: Expense[] }[] = []
  for (const row of rows) {
    const last = groups.at(-1)
    if (last?.date === row.expense_date) { last.rows.push(row); last.total += row.amount_cents }
    else groups.push({ date: row.expense_date, total: row.amount_cents, rows: [row] })
  }
  return groups
}

const knownCategories: Record<string, number> = { 餐饮: 0, 交通: 1, 住宿: 2, 门票: 3, 娱乐: 3, 购物: 4 }
/** 分类图标配色：常见分类固定颜色，其他分类按名称取一个稳定的颜色。 */
export function categoryTone(category: string): string {
  const known = knownCategories[category.trim()]
  if (known !== undefined) return `cat-${known}`
  const sum = Array.from(category).reduce((total, char) => total + char.codePointAt(0)!, 0)
  return `cat-${sum % 5}`
}
