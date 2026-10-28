import { request } from './client'
import type { Activity, ActivityInput, ActivityStatus, Credentials, Member, Registration, Statistics, Token, User } from './types'

export const authApi = {
  register: (body: Registration) => request<User>('/auth/register', { method: 'POST', body, public: true }),
  login: (body: Credentials) => request<Token>('/auth/login', { method: 'POST', body, public: true }),
  me: (token: string) => request<User>('/auth/me', { public: true, token }),
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
