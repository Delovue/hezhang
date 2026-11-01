<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { expenseApi } from '../api'
import { ApiError, errorMessage, isCancelled } from '../api/client'
import type { Activity, Expense, Member } from '../api/types'
import { formatCents } from '../utils/money'
import { categoryTone, dayLabel, groupByDay, splitLabels } from '../utils/expense'
import ExpenseEditor from './ExpenseEditor.vue'

const props = defineProps<{ activity: Activity; members: Member[]; userId: number; refreshToken: number; ready: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const rows = ref<Expense[]>([]), busy = ref(false), error = ref(''), more = ref(false), editing = ref<Expense>(), dialog = ref(false), deleting = ref(0)
const actionError = ref('')
const filters = reactive({ q: '', category: '', payer_member_id: '', participant_member_id: '', start_date: '', end_date: '' })
const scope = ref<'all' | 'joined' | 'paid' | ''>('all')
const me = computed(() => props.members.find(m => m.user_id === props.userId)?.id)
const groups = computed(() => groupByDay(rows.value))
let controller: AbortController | null = null
let applied = { ...filters }
function scopeOf(payer: string, participant: string) {
  if (!payer && !participant) return 'all'
  if (!payer && participant === String(me.value)) return 'joined'
  if (payer === String(me.value) && !participant) return 'paid'
  return ''
}
function choose(next: 'all' | 'joined' | 'paid') {
  filters.payer_member_id = next === 'paid' ? String(me.value) : ''
  filters.participant_member_id = next === 'joined' ? String(me.value) : ''
  void load()
}
function name(id: number) { return id === me.value ? '我' : props.members.find(m => m.id === id)?.display_name || `成员 ${id}` }
function myShare(row: Expense) { return row.shares.find(share => share.member_id === me.value) }
async function load(append = false) {
  if (!append) { applied = { ...filters }; scope.value = scopeOf(String(applied.payer_member_id), String(applied.participant_member_id)) }
  controller?.abort(); const current = new AbortController(); controller = current; busy.value = true; error.value = ''
  try {
    const next = await expenseApi.list(props.activity.id, { ...applied, limit: 20, offset: append ? rows.value.length : 0 }, current.signal)
    if (current.signal.aborted) return
    rows.value = append ? [...rows.value, ...next] : next; more.value = next.length === 20
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { if (controller === current) busy.value = false }
}
function editable(row: Expense) { return props.activity.status === 'ACTIVE' && [props.activity.owner_id, row.created_by_id].includes(props.userId) }
function edit(row?: Expense) { if (props.ready) { editing.value = row; dialog.value = true } }
async function remove(row: Expense) {
  if (!props.ready) return
  try { await ElMessageBox.confirm(`删除“${row.title}”（¥ ${formatCents(row.amount_cents)}）？操作历史会保留。`, '删除费用', { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }) }
  catch { return }
  deleting.value = row.id; actionError.value = ''
  try { await expenseApi.remove(props.activity.id, row.id, row.version); ElMessage.success('费用已删除'); emit('changed') }
  catch (cause) {
    if (!isCancelled(cause)) actionError.value = errorMessage(cause)
    if (cause instanceof ApiError && cause.status === 409) emit('changed')
  }
  finally { deleting.value = 0; void load() }
}
function saved() { ElMessage.success('费用已保存'); emit('changed') }
watch(() => [props.activity.id, props.activity.status, props.refreshToken], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="panel ledger-panel expense-panel">
    <div class="panel-heading"><h2>账目</h2>
      <div class="panel-tools"><div class="segmented" aria-label="快速筛选账目"><button v-for="(label, key) in { all: '全部', joined: '我参与的', paid: '我垫付的' }" :key="key" type="button" :class="{ selected: scope === key }" :aria-pressed="scope === key" :disabled="!me && key !== 'all'" @click="choose(key)">{{ label }}</button></div><el-button v-if="activity.status === 'ACTIVE'" type="primary" :disabled="!ready" @click="edit()">新增费用</el-button></div>
    </div>
    <p v-if="activity.status !== 'ACTIVE'" class="notice-box">活动已封账，费用与分摊明细只读。</p>
    <form class="expense-search" @submit.prevent="load()">
      <label class="search-field"><span class="sr-only">费用关键词</span><input v-model="filters.q" maxlength="120" placeholder="搜索名称或备注" /></label>
      <el-button native-type="submit" :loading="busy">筛选费用</el-button>
      <details class="more-filters"><summary>更多条件</summary>
        <div class="filter-grid">
          <label>分类筛选<input v-model="filters.category" maxlength="40" placeholder="全部分类" /></label>
          <label>垫付人筛选<select v-model="filters.payer_member_id"><option value="">所有成员</option><option v-for="member in members" :key="member.id" :value="String(member.id)">{{ member.display_name }}</option></select></label>
          <label>分摊成员筛选<select v-model="filters.participant_member_id"><option value="">所有成员</option><option v-for="member in members" :key="member.id" :value="String(member.id)">{{ member.display_name }}</option></select></label>
          <label>开始日期<input v-model="filters.start_date" type="date" /></label><label>结束日期<input v-model="filters.end_date" type="date" /></label>
        </div>
      </details>
    </form>
    <el-alert v-if="error || actionError" :title="actionError || error" type="error" :closable="false" role="alert" />
    <div v-if="!rows.length && !busy && !error" class="inner-empty"><h3>暂无符合条件的费用</h3><p>新增共同支出，或调整筛选条件。</p></div>
    <div v-for="(group, index) in groups" :key="`${group.date}-${index}`" class="day-group">
      <div class="day-head"><span>{{ dayLabel(group.date) }}</span><span class="money">已加载小计 ¥ {{ formatCents(group.total) }}</span></div>
      <article v-for="row in group.rows" :key="row.id" class="expense-card" :data-testid="`expense-${row.id}`">
        <div class="expense-row">
          <span class="category-icon" :class="categoryTone(row.category)" aria-hidden="true">{{ Array.from(row.category)[0] }}</span>
          <div class="expense-main"><h3>{{ row.title }}</h3><p class="muted">{{ row.category }} · {{ name(row.payer_member_id) }}垫付 · {{ row.shares.length }} 人{{ splitLabels[row.split_method] }}</p></div>
          <div class="expense-amount"><strong class="money">¥ {{ formatCents(row.amount_cents) }}</strong><span v-if="myShare(row)">我承担 ¥ {{ formatCents(myShare(row)!.amount_cents) }}</span><span v-else>我不参与</span></div>
        </div>
        <p v-if="row.notes" class="entry-notes">{{ row.notes }}</p>
        <div class="expense-foot">
          <details><summary>分摊明细</summary><div class="share-list"><span v-for="share in row.shares" :key="share.member_id">{{ members.find(m => m.id === share.member_id)?.display_name }} ¥ {{ formatCents(share.amount_cents) }}{{ share.shares ? `（${share.shares} 份）` : '' }}</span></div></details>
          <div v-if="editable(row)" class="entry-actions"><el-button text size="small" :disabled="!ready || !!deleting" @click="edit(row)">编辑费用</el-button><el-button text size="small" type="danger" :loading="deleting === row.id" :disabled="!ready || !!deleting" @click="remove(row)">删除费用</el-button></div>
        </div>
      </article>
    </div>
    <el-button v-if="more" :loading="busy" @click="load(true)">加载更多费用</el-button>
    <ExpenseEditor v-model="dialog" :activity="activity" :members="members" :expense="editing" :user-id="userId" @saved="saved" @refresh="emit('changed')" />
  </section>
</template>
