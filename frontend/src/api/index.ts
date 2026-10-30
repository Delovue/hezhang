import { request } from './client'
import type { Activity, ActivityInput, ActivityStatus, Credentials, Member, Registration, Statistics, Token, User } from './types'
import type { Expense, ExpenseCreate, ExpenseInput, Share, SplitInput } from './types'
import type { Balance, Payment, PaymentAction, PaymentCreate, PaymentStatus, Transfer } from './types'

export const settlementApi = {
  balances: (id: number, signal?: AbortSignal) => request<Balance[]>(`/activities/${id}/balances`, { signal }),
  suggestions: (id: number, signal?: AbortSignal) => request<Transfer[]>(`/activities/${id}/settlement-suggestions`, { signal }),
  payments: (id: number, query: { status?: PaymentStatus | ''; limit?: number; offset?: number }, signal?: AbortSignal) =>
    request<Payment[]>(`/activities/${id}/payments`, { query, signal }),
  create: (id: number, body: PaymentCreate) => request<Payment>(`/activities/${id}/payments`, { method: 'POST', body }),
  change: (id: number, payment: number, action: PaymentAction) =>
    request<Payment>(`/activities/${id}/payments/${payment}/${action}`, { method: 'POST' }),
  start: (id: number) => request<Activity>(`/activities/${id}/start-settlement`, { method: 'POST' }),
  archive: (id: number) => request<Activity>(`/activities/${id}/archive`, { method: 'POST' }),
}

export const authApi = {
  register: (body: Registration) => request<User>('/auth/register', { method: 'POST', body, public: true }),
  login: (body: Credentials) => request<Token>('/auth/login', { method: 'POST', body, public: true }),
  me: (token: string) => request<User>('/auth/me', { public: true, token }),
}
export const expenseApi = {
  list: (id: number, query: Record<string, string | number | undefined>, signal?: AbortSignal) =>
    request<Expense[]>(`/activities/${id}/expenses`, { query, signal }),
  detail: (id: number, expense: number) => request<Expense>(`/activities/${id}/expenses/${expense}`),
  create: (id: number, body: ExpenseCreate) => request<Expense>(`/activities/${id}/expenses`, { method: 'POST', body }),
  update: (id: number, expense: number, body: ExpenseInput & { version: number }) =>
    request<Expense>(`/activities/${id}/expenses/${expense}`, { method: 'PATCH', body }),
  remove: (id: number, expense: number, version: number) =>
    request<void>(`/activities/${id}/expenses/${expense}`, { method: 'DELETE', query: { version } }),
  preview: (id: number, body: SplitInput) => request<Share[]>(`/activities/${id}/split-preview`, { method: 'POST', body }),
}
export const activityApi = {
  list: (query: { q?: string; status?: ActivityStatus; before_id?: number; limit?: number }, signal?: AbortSignal) =>
    request<Activity[]>('/activities', { query, signal }),
  create: (body: ActivityInput) => request<Activity>('/activities', { method: 'POST', body }),
  join: (invite_code: string) => request<Activity>('/activities/join', { method: 'POST', body: { invite_code } }),
  detail: (id: number, signal?: AbortSignal) => request<Activity>(`/activities/${id}`, { signal }),
  update: (id: number, body: ActivityInput) => request<Activity>(`/activities/${id}`, { method: 'PATCH', body }),
  members: (id: number, signal?: AbortSignal) => request<Member[]>(`/activities/${id}/members`, { signal }),
  statistics: (id: number, signal?: AbortSignal) => request<Statistics>(`/activities/${id}/statistics`, { signal }),
}
