<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { expenseApi } from '../api'
import { ApiError, errorMessage, isCancelled } from '../api/client'
import type { Activity, Expense, ExpenseCreate, Member, Share } from '../api/types'
import { expenseInput, splitLabels, type ExpenseDraft } from '../utils/expense'
import { centsToInput, formatCents } from '../utils/money'

const props = defineProps<{ modelValue: boolean; activity: Activity; members: Member[]; expense?: Expense; userId: number }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; saved: []; refresh: [] }>()
const draft = reactive<ExpenseDraft>({ title: '', category: '餐饮', amount: '', date: '', notes: '', payer: 0, method: 'EQUAL', participants: [] })
const busy = ref(false), error = ref(''), previewRows = ref<Share[]>([]), version = ref(1)
const pending = ref<ExpenseCreate | null>(null), conflict = ref(false), latest = ref<Expense | null>(null)
watch(() => props.modelValue, open => {
  if (!open) return
  const value = props.expense
  const now = new Date()
  Object.assign(draft, { title: value?.title || '', category: value?.category || '餐饮', amount: value ? centsToInput(value.amount_cents) : '',
    date: value?.expense_date || `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`,
    notes: value?.notes || '', payer: value?.payer_member_id || props.members.find(m => m.user_id === props.userId)?.id || 0,
    method: value?.split_method || 'EQUAL', participants: props.members.map(member => {
      const share = value?.shares.find(row => row.member_id === member.id)
      return { member_id: member.id, selected: value ? !!share : true, amount: share ? centsToInput(share.amount_cents) : '', count: String(share?.shares || 1) }
    }) })
  version.value = value?.version || 1; error.value = ''; previewRows.value = []; pending.value = null; conflict.value = false; latest.value = null
}, { immediate: true })
watch(draft, () => { previewRows.value = [] }, { deep: true })
async function preview() {
  if (busy.value) return
  error.value = ''
  try {
    const input = expenseInput(draft); busy.value = true
    previewRows.value = await expenseApi.preview(props.activity.id, { amount_cents: input.amount_cents, split_method: input.split_method, participants: input.participants })
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function loadVersion() {
  if (!props.expense || busy.value) return
  busy.value = true
  try { latest.value = await expenseApi.detail(props.activity.id, props.expense.id); version.value = latest.value.version; conflict.value = false; error.value = '' }
  catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { busy.value = false }
}
async function submit() {
  if (busy.value || conflict.value || props.activity.status !== 'ACTIVE') return
  error.value = ''
  try {
    const input = pending.value || expenseInput(draft)
    busy.value = true
    if (props.expense) await expenseApi.update(props.activity.id, props.expense.id, { ...input, version: version.value })
    else {
      pending.value ||= { ...input, request_id: crypto.randomUUID() }
      await expenseApi.create(props.activity.id, pending.value)
    }
    pending.value = null; emit('update:modelValue', false); emit('saved')
  } catch (cause) {
    if (!isCancelled(cause)) error.value = errorMessage(cause)
    if (!(cause instanceof ApiError) || (cause.status > 0 && cause.status < 500)) pending.value = null
    if (cause instanceof ApiError && cause.code === 'EXPENSE_VERSION_CONFLICT') conflict.value = true
    if (cause instanceof ApiError && cause.code === 'ACTIVITY_LOCKED') emit('refresh')
  } finally { busy.value = false }
}
function close() { if (!busy.value) { emit('update:modelValue', false); emit('refresh') } }
</script>

<template>
  <el-dialog :model-value="modelValue" :title="expense ? '编辑费用' : '新增费用'" width="680px" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="close">
    <form class="stack-form" @submit.prevent="submit">
      <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
      <p v-if="pending" class="field-help">上次提交结果尚待确认。重试会使用原内容和同一请求编号，不会重复记账。</p>
      <p v-if="activity.status !== 'ACTIVE'" role="alert">活动已封账，费用不能继续修改。</p>
      <fieldset :disabled="busy || !!pending || activity.status !== 'ACTIVE'" class="ledger-fieldset">
        <div class="form-grid">
          <label class="form-field">费用名称<input v-model="draft.title" maxlength="120" required /></label>
          <label class="form-field">费用分类<input v-model="draft.category" maxlength="40" required /></label>
          <label class="form-field">费用总额（元）<input v-model="draft.amount" inputmode="decimal" required /></label>
          <label class="form-field">费用日期<input v-model="draft.date" type="date" required /></label>
          <label class="form-field">垫付人<select v-model="draft.payer" aria-label="垫付人"><option v-for="member in members" :key="member.id" :value="member.id">{{ member.display_name }}</option></select></label>
          <label class="form-field">分摊方式<select v-model="draft.method" aria-label="分摊方式"><option v-for="(label, key) in splitLabels" :key="key" :value="key">{{ label }}</option></select></label>
        </div>
        <p class="field-help">只勾选参与这笔费用的成员。分摊结果由后端计算。</p>
        <div class="split-grid">
          <div v-for="row in draft.participants" :key="row.member_id" class="split-row">
            <label><input v-model="row.selected" type="checkbox" :aria-label="`参与分摊：${members.find(m => m.id === row.member_id)?.display_name}`" /> {{ members.find(m => m.id === row.member_id)?.display_name }}</label>
            <label v-if="row.selected && draft.method === 'EXACT'">承担（元）<input v-model="row.amount" inputmode="decimal" :aria-label="`${members.find(m => m.id === row.member_id)?.display_name}承担金额`" /></label>
            <label v-if="row.selected && draft.method === 'SHARES'">份数<input v-model="row.count" inputmode="numeric" :aria-label="`${members.find(m => m.id === row.member_id)?.display_name}份数`" /></label>
          </div>
        </div>
        <label class="form-field">备注<textarea v-model="draft.notes" maxlength="1000" rows="2" /></label>
      </fieldset>
      <div class="preview-box"><el-button :disabled="busy || !!pending" @click="preview">预览分摊</el-button><span v-for="row in previewRows" :key="row.member_id">{{ members.find(m => m.id === row.member_id)?.display_name }}：¥ {{ formatCents(row.amount_cents) }}</span></div>
      <div v-if="conflict" class="notice-box"><p>他人已更新这笔费用，当前输入已保留。加载最新版本后，请核对再保存。</p><el-button :disabled="busy" @click="loadVersion">加载最新版本，保留输入</el-button></div>
      <p v-if="latest" class="field-help">最新记录：{{ latest.title }} · ¥ {{ formatCents(latest.amount_cents) }} · 版本 {{ latest.version }}。保存会使用当前表单内容。</p>
      <div class="dialog-actions"><el-button :disabled="busy" @click="close">{{ pending ? '关闭并核对费用' : '取消' }}</el-button><el-button type="primary" native-type="submit" :loading="busy" :disabled="conflict || activity.status !== 'ACTIVE'">{{ pending ? '重试原请求' : '保存费用' }}</el-button></div>
    </form>
  </el-dialog>
</template>
