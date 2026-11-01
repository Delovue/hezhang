<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { settlementApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
import type { Activity, Balance, Member, Payment, PaymentAction, PaymentStatus } from '../api/types'
import { formatCents } from '../utils/money'
import { allowedPaymentActions, paymentActions, paymentLabels } from '../utils/payment'
import { avatarTone, initial } from '../utils/members'

const props = defineProps<{ activity: Activity; members: Member[]; userId: number; refreshToken: number }>()
const emit = defineEmits<{ changed: [] }>()
const balances = ref<Balance[]>([]), payments = ref<Payment[]>([])
const busy = ref(false), changing = ref(false), error = ref(''), actionError = ref(''), more = ref(false)
const status = ref<PaymentStatus | ''>('')
const currentMember = computed(() => props.members.find(row => row.user_id === props.userId)?.id)
let controller: AbortController | null = null
function name(id: number) { return props.members.find(row => row.id === id)?.display_name || `成员 ${id}` }
async function load(append = false) {
  controller?.abort(); const current = new AbortController(); controller = current
  busy.value = true; error.value = ''
  try {
    const [balanceRows, paymentRows] = await Promise.all([
      settlementApi.balances(props.activity.id, current.signal),
      settlementApi.payments(props.activity.id, { status: status.value, limit: 20, offset: append ? payments.value.length : 0 }, current.signal),
    ])
    if (current.signal.aborted) return
    balances.value = balanceRows
    payments.value = append ? [...payments.value, ...paymentRows] : paymentRows; more.value = paymentRows.length === 20
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { if (controller === current) busy.value = false }
}
async function change(row: Payment, action: PaymentAction) {
  if (changing.value) return
  const detail = `${name(row.payer_member_id)} → ${name(row.payee_member_id)} · ¥ ${formatCents(row.amount_cents)}`
  try { await ElMessageBox.confirm(action === 'confirm' ? `${detail}。请核对实际收到款项后确认。` : `${detail}。${paymentActions[action]}后将释放可登记额度。`, paymentActions[action], { confirmButtonText: '确认操作', cancelButtonText: '取消', type: 'warning' }) }
  catch { return }
  changing.value = true; actionError.value = ''
  try { await settlementApi.change(props.activity.id, row.id, action); ElMessage.success('付款状态已更新'); emit('changed') }
  catch (cause) { if (!isCancelled(cause)) { actionError.value = errorMessage(cause); emit('changed') } }
  finally { changing.value = false }
}
watch(() => [props.activity.id, props.activity.status, props.refreshToken, status.value], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="panel settlement-content">
    <div class="panel-heading"><div><h2>余额明细</h2><p class="muted">净额来自共同费用；待确认付款仅占用可登记额度。</p></div></div>
    <el-alert v-if="error || actionError" :title="actionError || error" type="error" :closable="false" role="alert" />
    <div class="balance-grid">
      <article v-for="row in balances" :key="row.member_id" class="balance-card" :class="row.balance_cents > 0 ? 'receivable' : row.balance_cents < 0 ? 'payable' : 'settled'" :data-testid="`balance-${row.member_id}`">
        <h3><span class="avatar small" :class="avatarTone(row.member_id)" aria-hidden="true">{{ initial(name(row.member_id)) }}</span>{{ name(row.member_id) }} <small v-if="row.member_id === currentMember">我</small></h3>
        <strong class="balance-amount"><span class="balance-tag">{{ row.balance_cents > 0 ? '应收' : row.balance_cents < 0 ? '应付' : '已平账' }}</span> ¥ {{ formatCents(Math.abs(row.balance_cents)) }}</strong>
        <dl class="balance-totals"><div><dt>累计垫付</dt><dd>¥ {{ formatCents(row.paid_cents) }}</dd></div><div><dt>累计承担</dt><dd>¥ {{ formatCents(row.owed_cents) }}</dd></div></dl>
        <table class="balance-table"><thead><tr><th scope="col">结算付款</th><th scope="col">付出</th><th scope="col">收到</th></tr></thead>
          <tbody>
            <tr data-row="confirmed"><th scope="row">已确认</th><td>¥ {{ formatCents(row.confirmed_out_cents) }}</td><td>¥ {{ formatCents(row.confirmed_in_cents) }}</td></tr>
            <tr data-row="pending"><th scope="row">待确认</th><td>¥ {{ formatCents(row.pending_out_cents) }}</td><td>¥ {{ formatCents(row.pending_in_cents) }}</td></tr>
            <tr data-row="available"><th scope="row">可登记</th><td>¥ {{ formatCents(row.available_out_cents) }}</td><td>¥ {{ formatCents(row.available_in_cents) }}</td></tr>
          </tbody>
        </table>
      </article>
    </div>
    <div class="panel-heading payment-heading"><h2>付款记录</h2><label class="payment-filter">状态 <select v-model="status" aria-label="付款状态筛选"><option value="">全部</option><option v-for="(label, key) in paymentLabels" :key="key" :value="key">{{ label }}</option></select></label></div>
    <p v-if="activity.status === 'ACTIVE'" class="muted">封账后，成员可以按右侧的转账建议登记付款。</p>
    <p v-else-if="!busy && !payments.length" class="muted">暂无符合条件的付款。</p>
    <article v-for="row in payments" :key="row.id" class="payment-card" :data-testid="`payment-${row.id}`">
      <div class="payment-route"><span class="avatar mini" :class="avatarTone(row.payer_member_id)" aria-hidden="true">{{ initial(name(row.payer_member_id)) }}</span><div><h3>{{ name(row.payer_member_id) }} → {{ name(row.payee_member_id) }}</h3><p class="muted">{{ new Date(row.created_at).toLocaleString('zh-CN') }} · <span class="payment-status" :class="row.status.toLowerCase()">{{ paymentLabels[row.status] }}</span></p></div></div>
      <strong class="money">¥ {{ formatCents(row.amount_cents) }}</strong>
      <div v-if="activity.status === 'SETTLING' && allowedPaymentActions(row, currentMember).length" class="entry-actions"><el-button v-for="action in allowedPaymentActions(row, currentMember)" :key="action" size="small" :type="action === 'confirm' ? 'primary' : 'default'" :disabled="changing" @click="change(row, action)">{{ paymentActions[action] }}</el-button></div>
    </article>
    <el-button v-if="more" :loading="busy" @click="load(true)">加载更多付款</el-button>
  </section>
</template>
