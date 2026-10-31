<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { settlementApi } from '../api'
import { ApiError, errorMessage, isCancelled } from '../api/client'
import type { Activity, Balance, Member, PaymentCreate, Transfer } from '../api/types'
import { centsToInput, formatCents, parseYuan } from '../utils/money'

const props = defineProps<{ modelValue: boolean; activity: Activity; balances: Balance[]; members: Member[]; memberId?: number; suggestion?: Transfer }>()
const emit = defineEmits<{ 'update:modelValue': [boolean]; saved: []; refresh: [] }>()
const payee = ref(0), amount = ref(''), busy = ref(false), error = ref(''), pending = ref<PaymentCreate | null>(null)
const own = computed(() => props.balances.find(row => row.member_id === props.memberId))
const receivers = computed(() => props.balances.filter(row => row.available_in_cents > 0 && row.member_id !== props.memberId))
watch(() => props.modelValue, open => {
  if (!open) return
  payee.value = props.suggestion?.payee_member_id || receivers.value[0]?.member_id || 0
  amount.value = props.suggestion ? centsToInput(props.suggestion.amount_cents) : ''
  pending.value = null; error.value = ''
})
async function submit() {
  if (busy.value || props.activity.status !== 'SETTLING') return
  error.value = ''
  try {
    if (!pending.value) {
      const cents = parseYuan(amount.value)!
      if (cents <= 0) throw new Error('付款金额必须大于 0')
      const receiver = receivers.value.find(row => row.member_id === payee.value)
      if (!receiver) throw new Error('请选择仍有可收款额度的成员')
      if (cents > Math.min(own.value?.available_out_cents || 0, receiver.available_in_cents)) throw new Error('付款金额超过双方可登记额度，请刷新后核对')
      pending.value = { payee_member_id: payee.value, amount_cents: cents, request_id: crypto.randomUUID() }
    }
    busy.value = true
    await settlementApi.create(props.activity.id, pending.value)
    pending.value = null; emit('update:modelValue', false); emit('saved')
  } catch (cause) {
    if (!isCancelled(cause)) error.value = errorMessage(cause)
    if (!(cause instanceof ApiError) || (cause.status > 0 && cause.status < 500)) pending.value = null
    if (cause instanceof ApiError && cause.status === 409) emit('refresh')
  } finally { busy.value = false }
}
function close() { if (!busy.value) { emit('update:modelValue', false); emit('refresh') } }
</script>

<template>
  <el-dialog :model-value="modelValue" title="登记已付款" width="490px" :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy" @update:model-value="close">
    <form class="stack-form" @submit.prevent="submit">
      <p class="dialog-intro">请在实际转账后登记。收款人确认后，系统才会更新已结算金额。</p>
      <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
      <p v-if="pending" class="notice-box">上次提交结果尚待确认。重试使用同一请求编号和原金额，不会重复登记。</p>
      <p v-if="activity.status !== 'SETTLING'" role="alert">活动当前不接受新的付款登记。</p>
      <fieldset class="ledger-fieldset" :disabled="busy || !!pending || activity.status !== 'SETTLING'">
        <label class="form-field">收款人<select v-model="payee" aria-label="收款人"><option v-for="row in receivers" :key="row.member_id" :value="row.member_id">{{ members.find(m => m.id === row.member_id)?.display_name }} · 可收 ¥ {{ formatCents(row.available_in_cents) }}</option></select></label>
        <label class="form-field payment-amount">付款金额（元）<input v-model="amount" inputmode="decimal" required /></label>
      </fieldset>
      <p class="field-help">我还可登记付出 ¥ {{ formatCents(own?.available_out_cents || 0) }}。可填写部分金额。</p>
      <div class="dialog-actions"><el-button :disabled="busy" @click="close">{{ pending ? '关闭并核对记录' : '取消' }}</el-button><el-button type="primary" native-type="submit" :loading="busy" :disabled="activity.status !== 'SETTLING'">{{ pending ? '重试原付款' : '提交付款登记' }}</el-button></div>
    </form>
  </el-dialog>
</template>
