import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '../api'
import { ApiError } from '../api/client'
import type { User } from '../api/types'

/** Intentionally memory-only. Refresh requires signing in again; drafts stay mounted on expiry. */
export const useSessionStore = defineStore('session', () => {
  const token = ref<string | null>(null)
  const user = ref<User | null>(null)
  const expired = ref(false)
  const generation = ref(0)
  const authenticated = computed(() => token.value !== null && user.value !== null)
  let attempt = 0

  async function login(username: string, password: string, resume = false) {
    const currentAttempt = ++attempt
    const candidate = await authApi.login({ username, password })
    const profile = await authApi.me(candidate.access_token)
    if (currentAttempt !== attempt) return
    if (resume && user.value && profile.id !== user.value.id) {
      throw new ApiError(403, 'ACCOUNT_MISMATCH', '请使用原账号重新登录，以保留当前草稿')
    }
    user.value = profile
    token.value = candidate.access_token
    expired.value = false
  }

  function expire() {
    if (!token.value) return
    token.value = null
    expired.value = true
  }
  function logout() {
    attempt++
    token.value = null
    user.value = null
    expired.value = false
    generation.value++
  }
  return { token, user, expired, generation, authenticated, login, expire, logout }
})
