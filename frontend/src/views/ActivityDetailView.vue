<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, CopyDocument, EditPen, Refresh } from '@element-plus/icons-vue'
import { activityApi } from '../api'
import { ApiError, errorMessage, isCancelled } from '../api/client'
import type { Activity, Member, Statistics } from '../api/types'
import ActivityFormDialog from '../components/ActivityFormDialog.vue'
import ExpensePanel from '../components/ExpensePanel.vue'
import SettlementPanel from '../components/SettlementPanel.vue'
import SettlementSummary from '../components/SettlementSummary.vue'
import ActivityProgress from '../components/ActivityProgress.vue'
import ExportButton from '../components/ExportButton.vue'
import AuditPanel from '../components/AuditPanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useSessionStore } from '../stores/session'
import { parseActivityId } from '../utils/activity'
import { formatCents } from '../utils/money'
import { avatarTone, initial, labelMembers } from '../utils/members'

const route = useRoute()
const session = useSessionStore()
const activity = ref<Activity | null>(null)
const members = ref<Member[]>([])
const statistics = ref<Statistics | null>(null)
const loading = ref(false)
const error = ref('')
const statisticsError = ref('')
const missing = ref(false)
const tab = ref('expenses')
const showEdit = ref(false)
const refreshToken = ref(0)
let requestNumber = 0
let controller: AbortController | null = null
const currentMember = computed(() => members.value.find((member) => member.user_id === session.user?.id))
const owner = computed(() => activity.value?.owner_id === session.user?.id)
const canEdit = computed(() => owner.value && activity.value?.status === 'ACTIVE')
const memberNames = computed(() => members.value.map((member) => member.display_name).join('、'))
const budgetProgress = computed(() => {
  if (!statistics.value || statistics.value.budget_cents === null) return 0
  if (statistics.value.budget_cents === 0) return statistics.value.total_spent_cents > 0 ? 100 : 0
  return Math.min(100, Math.round(statistics.value.total_spent_cents / statistics.value.budget_cents * 100))
})

async function load() {
  if (!session.authenticated) return
  const currentRequest = ++requestNumber
  controller?.abort()
  const id = parseActivityId(route.params.id)
  if (id === null) { activity.value = null; missing.value = true; loading.value = false; error.value = '活动地址无效'; return }
  controller = new AbortController()
  const signal = controller.signal
  loading.value = true
  error.value = ''
  missing.value = false
  statisticsError.value = ''
  const [detail, memberRows, report] = await Promise.allSettled([
    activityApi.detail(id, signal), activityApi.members(id, signal), activityApi.statistics(id, signal),
  ])
  if (currentRequest !== requestNumber || signal.aborted) return
  if (detail.status === 'fulfilled') activity.value = detail.value
  else if (!isCancelled(detail.reason)) {
    error.value = errorMessage(detail.reason)
    missing.value = detail.reason instanceof ApiError && detail.reason.status === 404
    if (missing.value) activity.value = null
  }
  if (memberRows.status === 'fulfilled') members.value = labelMembers(memberRows.value)
  else if (!isCancelled(memberRows.reason) && !error.value) error.value = errorMessage(memberRows.reason)
  if (report.status === 'fulfilled') statistics.value = report.value
  else if (!isCancelled(report.reason)) { statistics.value = null; statisticsError.value = errorMessage(report.reason) }
  loading.value = false
  refreshToken.value++
}

async function copyInvite() {
  if (!activity.value?.invite_code) return
  try { await navigator.clipboard.writeText(activity.value.invite_code); ElMessage.success('邀请码已复制') }
  catch { ElMessage.info('自动复制不可用，请选中邀请码后手动复制') }
}
/** 标签内容与常驻摘要共用一次刷新通知，读取伙伴最新的成员、费用和付款变化。 */
function select(next: string) { tab.value = next; void load() }
function saved(updated: Activity) { activity.value = updated; ElMessage.success('活动已更新'); void load() }
watch([() => route.params.id, () => session.authenticated], ([id, authenticated], previous) => {
  if (previous && id !== previous[0]) { activity.value = null; members.value = []; statistics.value = null; tab.value = 'expenses'; showEdit.value = false }
  if (authenticated) void load()
}, { immediate: true })
onBeforeUnmount(() => { controller?.abort(); requestNumber++ })
</script>

<template>
  <section class="detail-page">
    <div class="detail-toolbar"><RouterLink to="/activities" class="back-link"><el-icon><ArrowLeft /></el-icon>返回我的活动</RouterLink>
      <div v-if="activity" class="heading-actions"><el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button><el-button v-if="canEdit" :icon="EditPen" @click="showEdit = true">编辑活动</el-button><ExportButton :activity-id="activity.id" :name="activity.name" /></div>
    </div>
    <el-alert v-if="error && !missing" :title="error" type="error" :closable="false" show-icon role="alert" class="section-alert" />
    <div v-if="loading && !activity" class="panel"><el-skeleton :rows="8" animated /></div>
    <div v-else-if="missing" class="empty-state"><h1>{{ error }}</h1><p>活动可能不存在，或当前账号尚未加入。</p><RouterLink to="/activities" class="text-link">返回活动列表 →</RouterLink></div>
    <template v-else-if="activity">
      <header class="detail-hero">
        <div class="hero-main"><div class="detail-title"><h1>{{ activity.name }}</h1><StatusBadge :status="activity.status" /></div>
          <p class="hero-members"><span class="avatar-stack" aria-hidden="true"><span v-for="member in members.slice(0, 5)" :key="member.id" class="avatar mini" :class="avatarTone(member.id)">{{ initial(member.display_name) }}</span></span><span>{{ memberNames }} · {{ members.length }} 位成员</span></p>
        </div>
        <div v-if="statistics" class="hero-total"><small>共同消费</small><strong class="money" data-testid="total-spent">¥ {{ formatCents(statistics.total_spent_cents) }}</strong>
          <span data-testid="budget">预算 <b>{{ statistics.budget_cents === null ? '未设置' : `¥ ${formatCents(statistics.budget_cents)}` }}</b><template v-if="statistics.remaining_budget_cents !== null"> · <span :class="{ over: statistics.over_budget }">{{ statistics.over_budget ? '已超出预算' : '剩余' }}</span> <b :class="{ over: statistics.over_budget }">¥ {{ formatCents(Math.abs(statistics.remaining_budget_cents)) }}</b></template></span>
        </div>
      </header>
      <ActivityProgress :activity="activity" :owner="owner" @changed="load" />
      <div class="detail-layout">
        <div class="detail-main">
          <div class="detail-tabs" aria-label="活动内容">
            <button :class="{ selected: tab === 'expenses' }" :aria-pressed="tab === 'expenses'" @click="select('expenses')">费用明细</button>
            <button :class="{ selected: tab === 'settlement' }" :aria-pressed="tab === 'settlement'" @click="select('settlement')">结算与付款</button>
            <button :class="{ selected: tab === 'overview' }" :aria-pressed="tab === 'overview'" @click="select('overview')">活动概览</button>
            <button :class="{ selected: tab === 'members' }" :aria-pressed="tab === 'members'" @click="select('members')">活动成员 <span>{{ members.length }}</span></button>
            <button :class="{ selected: tab === 'history' }" :aria-pressed="tab === 'history'" @click="select('history')">操作历史</button>
          </div>
          <div v-if="tab === 'overview'" class="overview-content">
            <el-alert v-if="statisticsError" :title="`统计暂不可用：${statisticsError}`" type="warning" :closable="false" show-icon role="alert" />
            <template v-if="statistics">
              <article class="panel"><div class="panel-heading"><h2>预算使用</h2><span class="muted">仅统计费用，不含成员间转账</span></div>
                <div v-if="statistics.budget_cents !== null" class="budget-line"><el-progress :percentage="budgetProgress" :show-text="false" :stroke-width="10" :status="statistics.over_budget ? 'exception' : undefined" /><strong>{{ budgetProgress }}%{{ statistics.over_budget ? ' · 已超预算' : '' }}</strong></div>
                <p v-else class="muted">未设置预算，按需安排即可。</p>
              </article>
              <article class="panel"><div class="panel-heading"><h2>消费分类</h2><span class="muted">共同支出的去向</span></div><div v-if="statistics.by_category.length" class="category-list"><div v-for="category in statistics.by_category" :key="category.category" class="category-item"><div><span>{{ category.category }}</span><strong>¥ {{ formatCents(category.amount_cents) }}</strong></div><el-progress :show-text="false" :stroke-width="6" :percentage="statistics.total_spent_cents ? Math.round(category.amount_cents / statistics.total_spent_cents * 100) : 0" /></div></div><div v-else class="inner-empty"><h3>还没有费用记录</h3><p>共同支出会按分类汇总在这里。</p></div></article>
              <article class="panel"><div class="panel-heading"><h2>成员承担</h2><span class="muted">按费用分摊汇总</span></div><div class="member-share-list"><div v-for="share in statistics.by_member" :key="share.member_id" class="member-share"><span class="avatar small" :class="avatarTone(share.member_id)" aria-hidden="true">{{ initial(members.find((member) => member.id === share.member_id)?.display_name || '?') }}</span><span>{{ members.find((member) => member.id === share.member_id)?.display_name || `成员 ${share.member_id}` }}</span><strong>¥ {{ formatCents(share.owed_cents) }}</strong></div></div><p class="field-help">承担金额表示分到的费用，与实际垫付金额不同。</p></article>
            </template>
          </div>
          <article v-else-if="tab === 'members'" class="panel"><div class="panel-heading"><div><h2>一起记账的伙伴</h2><p class="muted">共 {{ members.length }} 位成员 · 我的身份：{{ currentMember?.role === 'OWNER' ? '创建者' : '成员' }}</p></div></div><div class="member-grid"><div v-for="member in members" :key="member.id" class="member-card"><span class="avatar" :class="avatarTone(member.id)" aria-hidden="true">{{ initial(member.display_name) }}</span><div><strong>{{ member.display_name }} <small v-if="member.user_id === session.user?.id">（我）</small></strong><span class="member-role">{{ member.role === 'OWNER' ? '活动创建者' : '活动成员' }}</span></div></div></div><p v-if="activity.status !== 'ACTIVE'" class="field-help">活动已封账，成员名单已冻结。</p></article>
          <ExpensePanel v-else-if="tab === 'expenses'" :activity="activity" :members="members" :user-id="session.user!.id" :refresh-token="refreshToken" :ready="!loading && !error && !!currentMember" @changed="load" />
          <SettlementPanel v-else-if="tab === 'settlement'" :activity="activity" :members="members" :user-id="session.user!.id" :refresh-token="refreshToken" @changed="load" />
          <AuditPanel v-else-if="tab === 'history'" :activity-id="activity.id" :members="members" :refresh-token="refreshToken" />
        </div>
        <aside class="detail-rail" aria-label="结算摘要">
          <SettlementSummary :activity="activity" :members="members" :user-id="session.user!.id" :refresh-token="refreshToken" :ready="!loading && !error && !!currentMember" @changed="load" @review="select('settlement')" />
          <section v-if="activity.invite_code" class="rail-card invite-card"><h2>邀请伙伴</h2><p class="muted">伙伴登录后输入邀请码即可加入。</p><div class="invite-code-row"><code data-testid="invite-code">{{ activity.invite_code }}</code><el-button text :icon="CopyDocument" @click="copyInvite">复制</el-button></div></section>
        </aside>
      </div>
    </template>
    <div v-else-if="!loading && error" class="empty-state"><p>暂时无法加载活动。</p><el-button @click="load">重新加载</el-button></div>
  </section>
  <ActivityFormDialog v-if="activity" v-model="showEdit" :activity="activity" @saved="saved" @refresh="load" />
</template>
