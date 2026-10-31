<script setup lang="ts">
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { expenseApi } from '../api'
import { ApiError, errorMessage, isCancelled } from '../api/client'
import type { Activity, Expense, Member } from '../api/types'
import { formatCents } from '../utils/money'
import { splitLabels } from '../utils/expense'
import ExpenseEditor from './ExpenseEditor.vue'

const props = defineProps<{ activity: Activity; members: Member[]; userId: number; refreshToken: number }>()
const emit = defineEmits<{ changed: [] }>()
const rows = ref<Expense[]>([]), busy = ref(false), error = ref(''), more = ref(false), editing = ref<Expense>(), dialog = ref(false), deleting = ref(0)
const actionError = ref('')
const filters = reactive({ q: '', category: '', payer_member_id: '', participant_member_id: '', start_date: '', end_date: '' })
let controller: AbortController | null = null
let applied = { ...filters }
async function load(append = false) {
  if (!append) applied = { ...filters }
  controller?.abort(); const current = new AbortController(); controller = current; busy.value = true; error.value = ''
  try {
    const next = await expenseApi.list(props.activity.id, { ...applied, limit: 20, offset: append ? rows.value.length : 0 }, current.signal)
    if (current.signal.aborted) return
    rows.value = append ? [...rows.value, ...next] : next; more.value = next.length === 20
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { if (controller === current) busy.value = false }
}
function editable(row: Expense) { return props.activity.status === 'ACTIVE' && [props.activity.owner_id, row.created_by_id].includes(props.userId) }
function edit(row?: Expense) { editing.value = row; dialog.value = true }
async function remove(row: Expense) {
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
  <section class="panel ledger-panel">
    <div class="panel-heading"><div><h2>共同费用</h2><p class="muted">记录垫付与分摊，每一笔都有据可查。</p></div><el-button v-if="activity.status === 'ACTIVE'" type="primary" @click="edit()">新增费用</el-button></div>
    <p v-if="activity.status !== 'ACTIVE'" class="notice-box">活动已封账，费用与分摊明细只读。</p>
    <form class="filter-grid" @submit.prevent="load()">
      <label>费用关键词<input v-model="filters.q" maxlength="120" placeholder="名称或备注" /></label>
      <label>分类筛选<input v-model="filters.category" maxlength="40" placeholder="全部分类" /></label>
      <label>垫付人筛选<select v-model="filters.payer_member_id"><option value="">所有成员</option><option v-for="member in members" :key="member.id" :value="member.id">{{ member.display_name }}</option></select></label>
      <label>分摊成员筛选<select v-model="filters.participant_member_id"><option value="">所有成员</option><option v-for="member in members" :key="member.id" :value="member.id">{{ member.display_name }}</option></select></label>
      <label>开始日期<input v-model="filters.start_date" type="date" /></label><label>结束日期<input v-model="filters.end_date" type="date" /></label>
      <el-button native-type="submit" :loading="busy">筛选费用</el-button>
    </form>
    <el-alert v-if="error || actionError" :title="actionError || error" type="error" :closable="false" role="alert" />
    <div v-if="!rows.length && !busy && !error" class="inner-empty"><h3>暂无符合条件的费用</h3><p>新增共同支出，或调整筛选条件。</p></div>
    <article v-for="row in rows" :key="row.id" class="expense-card" :data-testid="`expense-${row.id}`">
      <div class="entry-heading"><div><h3>{{ row.title }}</h3><p class="muted">{{ row.expense_date }} · {{ row.category }} · {{ members.find(m => m.id === row.payer_member_id)?.display_name }} 垫付</p></div><strong class="money">¥ {{ formatCents(row.amount_cents) }}</strong></div>
      <p v-if="row.notes" class="entry-notes">{{ row.notes }}</p>
      <details><summary>{{ splitLabels[row.split_method] }} · {{ row.shares.length }} 人承担</summary><div class="share-list"><span v-for="share in row.shares" :key="share.member_id">{{ members.find(m => m.id === share.member_id)?.display_name }} ¥ {{ formatCents(share.amount_cents) }}{{ share.shares ? `（${share.shares} 份）` : '' }}</span></div></details>
      <div v-if="editable(row)" class="entry-actions"><el-button :disabled="!!deleting" @click="edit(row)">编辑费用</el-button><el-button type="danger" plain :loading="deleting === row.id" :disabled="!!deleting" @click="remove(row)">删除费用</el-button></div>
    </article>
    <el-button v-if="more" :loading="busy" @click="load(true)">加载更多费用</el-button>
    <ExpenseEditor v-model="dialog" :activity="activity" :members="members" :expense="editing" :user-id="userId" @saved="saved" @refresh="emit('changed')" />
  </section>
</template>
