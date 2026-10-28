<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { ArrowRight, FolderOpened, SwitchButton } from '@element-plus/icons-vue'
import { useSessionStore } from './stores/session'
import { errorMessage } from './api/client'
import BrandMark from './components/BrandMark.vue'

const session = useSessionStore()
const router = useRouter()
const password = ref('')
const busy = ref(false)
const error = ref('')
watch(() => session.expired, () => { password.value = ''; error.value = '' })
async function resume() {
  if (busy.value || !session.user) return
  busy.value = true
  error.value = ''
  try { await session.login(session.user.username, password.value, true) }
  catch (cause) { error.value = errorMessage(cause) }
  finally { password.value = ''; busy.value = false }
}
function logout() {
  session.logout()
  void router.replace('/login')
}
</script>

<template>
  <ElConfigProvider :locale="zhCn">
  <div v-if="session.user" class="app-shell">
    <aside class="sidebar">
      <RouterLink to="/activities" class="brand"><BrandMark /><span>合账<small>HEZHANG</small></span></RouterLink>
      <p class="nav-label">我的空间</p>
      <RouterLink to="/activities" class="side-link"><el-icon><FolderOpened /></el-icon>我的活动<el-icon class="nav-arrow"><ArrowRight /></el-icon></RouterLink>
      <div class="sidebar-note"><span class="note-symbol" aria-hidden="true">↗</span><strong>一起出发，轻松合账</strong><p>记下共同的花费，<br />把时间留给相聚。</p></div>
      <div class="sidebar-bottom"><span class="tiny-dot"></span>小组活动协作记账</div>
    </aside>
    <div class="main-shell">
      <header class="topbar"><RouterLink to="/activities" class="mobile-brand"><BrandMark />合账</RouterLink><span class="topbar-caption">每一笔，都明明白白。</span>
        <div class="account"><span class="avatar small">{{ session.user.display_name.slice(0, 1) }}</span><span class="account-name">{{ session.user.display_name }}</span><el-button text :icon="SwitchButton" aria-label="退出登录" @click="logout">退出</el-button></div>
      </header>
      <main id="main-content" class="page-content"><RouterView :key="session.generation" /></main>
      <footer class="page-footer"><span>合账 · 让相聚更简单</span><span>共同记录 · 清晰分摊</span></footer>
    </div>
  </div>
  <RouterView v-else :key="session.generation" />

  <el-dialog :model-value="session.expired" title="重新登录，继续当前操作" width="440px" :show-close="false"
    :close-on-click-modal="false" :close-on-press-escape="false" :z-index="4000">
    <p class="dialog-intro">登录已失效，当前页面与未提交内容已保留。请使用原账号重新登录。</p>
    <form class="stack-form" @submit.prevent="resume">
      <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
      <div class="form-field"><label for="resume-account">账号</label><el-input id="resume-account" :model-value="session.user?.username" disabled /></div>
      <div class="form-field"><label for="resume-password">密码</label><el-input id="resume-password" v-model="password" type="password" autocomplete="current-password" show-password :disabled="busy" minlength="8" maxlength="128" required /></div>
      <div class="dialog-actions"><el-button :disabled="busy" @click="logout">退出并返回登录</el-button><el-button type="primary" native-type="submit" :loading="busy">重新登录</el-button></div>
    </form>
  </el-dialog>
  </ElConfigProvider>
</template>
