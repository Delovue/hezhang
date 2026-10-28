<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, Check, Lock, User as UserIcon } from '@element-plus/icons-vue'
import BrandMark from '../components/BrandMark.vue'
import { authApi } from '../api'
import { ApiError, errorMessage } from '../api/client'
import { useSessionStore } from '../stores/session'
import { safeRedirect } from '../utils/activity'

const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const register = computed(() => route.path === '/register')
const form = reactive({ username: '', display_name: '', password: '' })
const busy = ref(false)
const error = ref('')
const notice = ref('')
const registrationDone = ref(false)
watch(() => route.path, () => { error.value = ''; form.password = ''; registrationDone.value = false })
async function submit() {
  if (busy.value) return
  error.value = ''
  const username = form.username.trim().toLowerCase()
  if (!/^[a-z0-9_]{3,32}$/.test(username)) { error.value = '用户名请输入 3–32 位英文字母、数字或下划线'; return }
  if (form.password.length < 8 || form.password.length > 128) { error.value = '密码请输入 8–128 个字符'; return }
  if (register.value && !form.display_name.trim()) { error.value = '请输入显示名'; return }
  busy.value = true
  try {
    if (register.value && !registrationDone.value) {
      await authApi.register({ username, password: form.password, display_name: form.display_name.trim() })
      registrationDone.value = true
    }
    // If registration succeeded but login failed, the next click only retries login.
    await session.login(username, form.password)
    form.password = ''
    await router.replace(safeRedirect(route.query.redirect))
  } catch (cause) {
    error.value = errorMessage(cause)
    if (register.value && registrationDone.value) notice.value = '账号已创建。请再次登录，无需重复注册。'
    if (cause instanceof ApiError && cause.code === 'USERNAME_EXISTS') notice.value = '已有账号？可以直接切换到登录。'
  } finally { busy.value = false }
}
</script>

<template>
  <div class="auth-page">
    <section class="auth-story">
      <RouterLink to="/login" class="brand"><BrandMark /><span>合账<small>HEZHANG</small></span></RouterLink>
      <div class="story-body"><div class="eyebrow light"><span></span>属于你们的共同账本</div>
        <h1>一起出发，<br />把账算清楚。</h1><p class="story-description">一场旅行，一次聚餐。<br />共同的花费，一起记，轻松分。</p>
        <div class="ledger-art" aria-hidden="true"><div class="art-label">OUR SHARED MOMENTS <span>↗</span></div>
          <div class="art-row"><span class="art-icon">↗</span><div><strong>每一笔支出</strong><small>有人垫付，大家分担</small></div><span class="art-check">✓</span></div>
          <div class="art-connection"></div>
          <div class="art-row"><span class="art-icon peach">≋</span><div><strong>每一次相聚</strong><small>费用清晰，相处轻松</small></div><span class="art-check">✓</span></div>
          <div class="art-rule"></div><div class="art-bottom"><span>小账本 · 大默契</span><span class="art-avatars">A <i>B</i> <i>C</i></span></div>
        </div>
      </div>
      <p class="story-footer">共同记录 <span>·</span> 清晰分摊 <span>·</span> 安心结算</p>
    </section>
    <main class="auth-main"><div class="auth-top-note">{{ register ? '已有合账账号？' : '第一次使用合账？' }}
      <RouterLink :to="{ path: register ? '/login' : '/register', query: route.query }">{{ register ? '去登录' : '创建账号' }} <span aria-hidden="true">↗</span></RouterLink></div>
      <div class="auth-form-wrap"><span class="eyebrow">LET’S GET TOGETHER</span><h2>{{ register ? '开启你们的共同账本' : '欢迎回来' }}</h2><p class="muted auth-subtitle">{{ register ? '创建账号，让每一笔共同花费都有记录。' : '登录合账，继续记录下一段美好时光。' }}</p>
        <form class="stack-form" @submit.prevent="submit">
          <el-alert v-if="notice" :title="notice" type="info" :closable="false" />
          <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
          <div class="form-field"><label for="username">用户名</label><el-input id="username" v-model="form.username" autocomplete="username" placeholder="3–32 位字母、数字或下划线" :prefix-icon="UserIcon" :disabled="busy || registrationDone" maxlength="32" required /></div>
          <div v-if="register" class="form-field"><label for="display-name">显示名</label><el-input id="display-name" v-model="form.display_name" autocomplete="nickname" placeholder="伙伴们怎么称呼你？" :disabled="busy || registrationDone" maxlength="50" required /></div>
          <div class="form-field"><label for="password">密码</label><el-input id="password" v-model="form.password" type="password" :autocomplete="register ? 'new-password' : 'current-password'" placeholder="8–128 个字符" :prefix-icon="Lock" show-password :disabled="busy" minlength="8" maxlength="128" required /></div>
          <el-button type="primary" size="large" native-type="submit" :loading="busy" class="auth-submit">{{ register && !registrationDone ? '创建账号并登录' : '登录合账' }}<el-icon v-if="!busy"><ArrowRight /></el-icon></el-button>
        </form>
        <p class="session-note"><el-icon><Check /></el-icon>登录状态仅在当前页面保留，刷新后需重新登录。</p>
      </div><p class="auth-bottom">一人记账，大家心里有数。</p>
    </main>
  </div>
</template>
