import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, createHttpClient, RequestCancelled } from '../src/api/client'

afterEach(() => vi.unstubAllGlobals())
function reply(body: unknown, status = 200, headers?: Record<string, string>) {
  return new Response(JSON.stringify(body), { status, headers })
}

describe('API request and error contracts', () => {
  it('sends the memory token and safely encodes filter text', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply([]))
    vi.stubGlobal('fetch', fetcher)
    const request = createHttpClient({ getToken: () => 'session-token', onUnauthorized: vi.fn() })
    await request('/activities', { query: { q: '杭州 & 上海', status: undefined, limit: 12 } })
    const [url, options] = fetcher.mock.calls[0]!
    expect(new URL(url, 'http://localhost').searchParams.get('q')).toBe('杭州 & 上海')
    expect(url).not.toContain('undefined')
    expect(options.headers.get('Authorization')).toBe('Bearer session-token')
  })
  it('supports DELETE 204 without JSON parsing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    expect(await createHttpClient()('/activities/1', { method: 'DELETE' })).toBeUndefined()
  })
  it('preserves stable codes and Retry-After without automatically repeating a POST', async () => {
    const fetcher = vi.fn().mockResolvedValue(reply({ detail: '账本正在更新', code: 'DATABASE_BUSY', retryable: true }, 409, { 'Retry-After': '1' }))
    vi.stubGlobal('fetch', fetcher)
    await expect(createHttpClient()('/activities', { method: 'POST', body: { name: '旅行' } }))
      .rejects.toMatchObject({ status: 409, code: 'DATABASE_BUSY', retryable: true, retryAfter: 1 })
    expect(fetcher).toHaveBeenCalledTimes(1)
  })
  it('turns 422 field arrays into readable messages', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({ code: 'VALIDATION_ERROR', retryable: false,
      detail: [{ loc: ['body', 'name'], type: 'string_too_long', msg: 'Too long' }] }, 422)))
    await expect(createHttpClient()('/activities')).rejects.toThrow('活动名称：超过长度限制')
  })
  it('expires protected sessions but does not treat incorrect login as session expiry', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(reply({ detail: '请登录', code: 'AUTHENTICATION_REQUIRED' }, 401))))
    const onUnauthorized = vi.fn()
    const request = createHttpClient({ getToken: () => 'old-token', onUnauthorized })
    await expect(request('/auth/login', { public: true, method: 'POST' })).rejects.toBeInstanceOf(ApiError)
    expect(onUnauthorized).not.toHaveBeenCalled()
    await expect(request('/activities')).rejects.toBeInstanceOf(ApiError)
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })
  it('ignores a stale account response and never expires the replacement session', async () => {
    let token = 'first'
    let resolve!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise<Response>((done) => { resolve = done })))
    const onUnauthorized = vi.fn()
    const pending = createHttpClient({ getToken: () => token, onUnauthorized })('/activities')
    token = 'second'
    resolve(reply({ detail: 'expired' }, 401))
    await expect(pending).rejects.toBeInstanceOf(RequestCancelled)
    expect(onUnauthorized).not.toHaveBeenCalled()
  })
  it('reports network failures without echoing request credentials', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))
    await expect(createHttpClient()('/auth/login', { body: { password: 'private-password' } }))
      .rejects.toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
  })
  it('reports a proxy outage without trying to render an HTML body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 })))
    await expect(createHttpClient()('/activities')).rejects.toThrow('无法连接后端')
  })
})
