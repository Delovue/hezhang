import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { authApi } from '../src/api'
import { useSessionStore } from '../src/stores/session'

beforeEach(() => {
  vi.restoreAllMocks()
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'login').mockResolvedValue({ access_token: 'valid', token_type: 'bearer', expires_in: 3600 })
  vi.spyOn(authApi, 'me').mockResolvedValue({ id: 7, username: 'alice', display_name: '小王' })
})

describe('session ownership', () => {
  it('only establishes a session after verifying /me', async () => {
    vi.mocked(authApi.me).mockRejectedValue(new Error('unavailable'))
    const session = useSessionStore()
    await expect(session.login('alice', 'password')).rejects.toThrow('unavailable')
    expect(session.token).toBeNull()
    expect(session.user).toBeNull()
  })
  it('keeps the account identity during expiry so the same account can resume its draft', async () => {
    const session = useSessionStore()
    await session.login('alice', 'password')
    session.expire()
    expect(session.authenticated).toBe(false)
    expect(session.expired).toBe(true)
    expect(session.user?.id).toBe(7)
    expect(session.generation).toBe(0)
    await session.login('alice', 'password', true)
    expect(session.authenticated).toBe(true)
    expect(session.expired).toBe(false)
  })
  it('does not resume another user into an existing draft', async () => {
    const session = useSessionStore()
    await session.login('alice', 'password')
    session.expire()
    vi.mocked(authApi.me).mockResolvedValue({ id: 8, username: 'bob', display_name: '小李' })
    await expect(session.login('bob', 'password', true)).rejects.toMatchObject({ code: 'ACCOUNT_MISMATCH' })
    expect(session.user?.id).toBe(7)
    expect(session.token).toBeNull()
  })
  it('clears account and increments the view key on logout', async () => {
    const session = useSessionStore()
    await session.login('alice', 'password')
    session.logout()
    expect(session.user).toBeNull()
    expect(session.token).toBeNull()
    expect(session.generation).toBe(1)
  })
  it('does not restore a session when an in-flight login finishes after logout', async () => {
    const session = useSessionStore()
    let finish!: (user: { id: number; username: string; display_name: string }) => void
    vi.mocked(authApi.me).mockImplementation(() => new Promise((resolve) => { finish = resolve }))
    const login = session.login('alice', 'password')
    await vi.waitFor(() => expect(authApi.me).toHaveBeenCalled())
    session.logout()
    finish({ id: 7, username: 'alice', display_name: '小王' })
    await login
    expect(session.authenticated).toBe(false)
  })
})
