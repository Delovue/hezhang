/** Contract baseline: origin/main aac4fe1, backend/app/schemas.py. Amounts are integer cents. */
export type ActivityStatus = 'ACTIVE' | 'SETTLING' | 'SETTLED' | 'ARCHIVED'
export interface User { id: number; username: string; display_name: string }
export interface Credentials { username: string; password: string }
export interface Registration extends Credentials { display_name: string }
export interface Token { access_token: string; token_type: 'bearer'; expires_in: number }
export interface Activity {
  id: number
  name: string
  owner_id: number
  budget_cents: number | null
  status: ActivityStatus
  invite_code: string | null
}
export interface ActivityInput { name: string; budget_cents: number | null }
export interface Member { id: number; user_id: number; display_name: string; role: 'OWNER' | 'MEMBER' }
export interface Statistics {
  total_spent_cents: number
  budget_cents: number | null
  remaining_budget_cents: number | null
  over_budget: boolean
  by_category: { category: string; amount_cents: number }[]
  by_member: { member_id: number; owed_cents: number }[]
}
export interface ValidationIssue { loc: (string | number)[]; msg: string; type: string }
export interface ErrorResponse { detail: string | ValidationIssue[]; code: string; retryable: boolean }

export type SplitMethod = 'EQUAL' | 'EXACT' | 'SHARES'
export interface Participant { member_id: number; amount_cents?: number; shares?: number }
export interface SplitInput { amount_cents: number; split_method: SplitMethod; participants: Participant[] }
export interface Share { member_id: number; amount_cents: number; shares: number | null }
export interface ExpenseInput extends SplitInput {
  title: string; category: string; expense_date: string; notes: string | null; payer_member_id: number
}
export interface Expense extends Omit<ExpenseInput, 'participants'> {
  id: number; activity_id: number; created_by_id: number; version: number; shares: Share[]
}
export interface ExpenseCreate extends ExpenseInput { request_id: string }
