import type { ErrorResponse, ValidationIssue } from './types'

type Query = Record<string, string | number | undefined>
interface Options {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Query
  signal?: AbortSignal
  /** Public calls and the candidate token's /me check must not expire an existing session. */
  public?: boolean
  token?: string
}
interface SessionHooks { getToken: () => string | null; onUnauthorized: () => void }
const fieldNames: Record<string, string> = {
  username: '用户名', password: '密码', display_name: '显示名', name: '活动名称',
  budget_cents: '总预算', invite_code: '邀请码', q: '搜索关键词', status: '活动状态',
}

function issueMessage(issue: ValidationIssue): string {
  const field = issue.loc.filter((part) => part !== 'body' && part !== 'query').join('.')
  const label = fieldNames[field] || field || '输入'
  const messages: Record<string, string> = {
    missing: '不能为空', string_too_short: '长度不足', string_too_long: '超过长度限制',
    string_pattern_mismatch: '格式不正确', int_type: '必须为整数',
    greater_than_equal: '低于允许的最小值', less_than_equal: '超过允许的最大值',
  }
  return `${label}：${messages[issue.type] || issue.msg}`
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly retryable = false,
    public readonly retryAfter: number | null = null,
  ) { super(message); this.name = 'ApiError' }
}

export class RequestCancelled extends Error {
  constructor() { super('请求已取消'); this.name = 'AbortError' }
}

export function isCancelled(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作未完成，请稍后再试'
}

/** No automatic retries: POST creation endpoints do not all support idempotency. */
export function createHttpClient(hooks: SessionHooks = {
  getToken: () => null, onUnauthorized: () => {},
}) {
  return async function request<T>(path: string, options: Options = {}): Promise<T> {
    const boundToken = options.public ? null : hooks.getToken()
    const token = options.token ?? boundToken
    const headers = new Headers({ Accept: 'application/json' })
    if (token) headers.set('Authorization', `Bearer ${token}`)
    if (options.body !== undefined) headers.set('Content-Type', 'application/json')
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(options.query || {})) {
      if (value !== undefined && value !== '') query.set(key, String(value))
    }
    const suffix = query.size ? `?${query}` : ''
    let response: Response
    try {
      response = await fetch(`/api/v1${path}${suffix}`, {
        method: options.method || 'GET', headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: options.signal,
      })
    } catch (error) {
      if (isCancelled(error)) throw error
      throw new ApiError(0, 'NETWORK_ERROR', '无法连接服务，请检查后端是否运行。提交结果不确定时，请先刷新列表核对。')
    }
    // A response from an old account must not update a new account's page or expire its token.
    if (boundToken && hooks.getToken() !== boundToken) throw new RequestCancelled()
    const data: unknown = response.status === 204 ? undefined : await response.json().catch(() => undefined)
    if (!response.ok) {
      const payload = (data || {}) as Partial<ErrorResponse>
      const message = typeof payload.detail === 'string' ? payload.detail
        : Array.isArray(payload.detail) ? payload.detail.map(issueMessage).join('；')
        : response.status === 503 ? '服务未就绪，请检查后端和数据库迁移'
        : response.status === 502 || response.status === 504 ? '无法连接后端，请确认后端已启动'
        : `请求失败（${response.status}），请稍后再试`
      const code = typeof payload.code === 'string' ? payload.code : 'HTTP_ERROR'
      if (response.status === 401 && boundToken) hooks.onUnauthorized()
      const retryAfter = Number(response.headers.get('Retry-After'))
      throw new ApiError(response.status, code, message, payload.retryable === true,
        Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null)
    }
    return data as T
  }
}

let sessionHooks: SessionHooks = { getToken: () => null, onUnauthorized: () => {} }
export function configureSession(hooks: SessionHooks) { sessionHooks = hooks }
export const request = createHttpClient({
  getToken: () => sessionHooks.getToken(), onUnauthorized: () => sessionHooks.onUnauthorized(),
})
