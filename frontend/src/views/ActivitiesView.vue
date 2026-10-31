<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, CirclePlus, Connection, FolderOpened, Plus, Refresh, Search } from '@element-plus/icons-vue'
import { activityApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
import type { Activity, ActivityStatus } from '../api/types'
import ActivityFormDialog from '../components/ActivityFormDialog.vue'
import JoinActivityDialog from '../components/JoinActivityDialog.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useSessionStore } from '../stores/session'
import { statusDescriptions, statusLabels } from '../utils/activity'
import { formatCents } from '../utils/money'

const router = useRouter()
const session = useSessionStore()
const activities = ref<Activity[]>([])
const filter = reactive<{ q: string; status: ActivityStatus | '' }>({ q: '', status: '' })
const applied = reactive<{ q?: string; status?: ActivityStatus }>({})
const loading = ref(false)
const error = ref('')
const hasMore = ref(false)
const showCreate = ref(false)
const showJoin = ref(false)
const pageSize = 12
let requestNumber = 0
let controller: AbortController | null = null
const activeCount = computed(() => activities.value.filter((item) => item.status === 'ACTIVE').length)
const settlingCount = computed(() => activities.value.filter((item) => item.status === 'SETTLING').length)
const statuses: (ActivityStatus | '')[] = ['', 'ACTIVE', 'SETTLING', 'SETTLED', 'ARCHIVED']

async function load(more = false) {
  if (!session.authenticated) return
  const currentRequest = ++requestNumber
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const rows = await activityApi.list({ ...applied, limit: pageSize,
      before_id: more ? activities.value.at(-1)?.id : undefined }, controller.signal)
    if (currentRequest !== requestNumber) return
    activities.value = more ? [...activities.value, ...rows] : rows
    hasMore.value = rows.length === pageSize
  } catch (cause) {
    if (currentRequest === requestNumber && !isCancelled(cause)) error.value = errorMessage(cause)
  } finally { if (currentRequest === requestNumber) loading.value = false }
}
function search() {
  applied.q = filter.q.trim() || undefined
  applied.status = filter.status || undefined
  activities.value = []
  hasMore.value = false
  void load()
}
function chooseStatus(status: ActivityStatus | '') { filter.status = status; search() }
function openActivity(activity: Activity) { void router.push(`/activities/${activity.id}`) }
watch(() => session.authenticated, (authenticated) => { if (authenticated) void load() }, { immediate: true })
onBeforeUnmount(() => { controller?.abort(); requestNumber++ })
</script>

<template>
  <section>
    <div class="page-heading"><div><div class="eyebrow">我的空间</div><h1>我的活动<span class="heading-dot">.</span></h1><p class="muted">把共同的花费记在一起，让每一次相聚都轻松一点。</p></div>
      <div class="heading-actions"><el-button :icon="Connection" @click="showJoin = true">邀请码加入</el-button><el-button type="primary" :icon="Plus" @click="showCreate = true">创建活动</el-button></div>
    </div>
    <div class="welcome-banner"><div class="banner-text"><span class="eyebrow">新建共同账本</span><h2>下一次相聚，从这里开始。</h2><p>旅行、聚餐、周末小聚，都有一本清楚的共同账。</p><button class="banner-link" @click="showCreate = true">创建一本共同账本 <span aria-hidden="true">↗</span></button></div><div class="banner-art" aria-hidden="true"><div class="floating-note">一起去看看世界 <span>↗</span><i></i><i></i></div><div class="banner-circle"></div><span class="banner-spark">✳</span></div></div>
    <div class="list-context"><p>当前列表 <strong>{{ activities.length }}</strong> 个活动 <span class="context-divider">/</span> <span>{{ activeCount }} 个进行中</span><span class="context-divider">/</span><span>{{ settlingCount }} 个结算中</span></p><el-button text :icon="Refresh" :loading="loading" @click="load()">刷新</el-button></div>
    <div class="list-toolbar"><div class="status-filters" aria-label="按活动状态筛选"><button v-for="status in statuses" :key="status" :class="{ selected: filter.status === status }" :aria-pressed="filter.status === status" @click="chooseStatus(status)">{{ status ? statusLabels[status] : '全部活动' }}</button></div>
      <form class="search-form" role="search" @submit.prevent="search"><el-input v-model="filter.q" aria-label="搜索活动名称" placeholder="搜索活动名称" maxlength="120" clearable :prefix-icon="Search" @clear="search" /><el-button native-type="submit">搜索</el-button></form>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" class="section-alert" />
    <div v-if="loading && activities.length === 0" class="activity-grid" aria-busy="true" aria-label="正在加载活动"><div v-for="item in 3" :key="item" class="activity-card"><el-skeleton :rows="4" animated /></div></div>
    <div v-else-if="activities.length" class="activity-grid"><RouterLink v-for="(activity, index) in activities" :key="activity.id" :to="`/activities/${activity.id}`" class="activity-card" :aria-label="`查看活动：${activity.name}`">
      <div class="card-top"><span class="activity-symbol" :class="`tone-${index % 3}`"><el-icon><FolderOpened /></el-icon></span><StatusBadge :status="activity.status" /></div>
      <h2>{{ activity.name }}</h2><p class="card-description">{{ statusDescriptions[activity.status] }}</p>
      <div class="card-budget"><span>活动总预算</span><strong>{{ activity.budget_cents === null ? '未设置' : `¥ ${formatCents(activity.budget_cents)}` }}</strong></div>
      <div class="card-footer"><span class="role-label">{{ activity.owner_id === session.user?.id ? '我创建的' : '我参与的' }}</span><span>查看活动 <el-icon><ArrowRight /></el-icon></span></div>
    </RouterLink></div>
    <div v-else-if="!error" class="empty-state"><span class="empty-icon"><el-icon><CirclePlus /></el-icon></span><h2>{{ applied.q || applied.status ? '没有找到匹配的活动' : '还没有共同账本' }}</h2><p>{{ applied.q || applied.status ? '试试其他名称，或切换活动状态。' : '创建一个活动邀请伙伴，或使用邀请码加入他们。' }}</p><el-button v-if="!applied.q && !applied.status" type="primary" :icon="Plus" @click="showCreate = true">创建第一个活动</el-button><el-button v-else @click="filter.q = ''; filter.status = ''; search()">查看全部活动</el-button></div>
    <div v-if="hasMore" class="load-more"><el-button :loading="loading" @click="load(true)">加载更多活动</el-button></div>
    <p class="list-footnote">每一段共同的时光，都值得好好记录。</p>
  </section>
  <ActivityFormDialog v-model="showCreate" @saved="openActivity" />
  <JoinActivityDialog v-model="showJoin" @joined="openActivity" />
</template>
