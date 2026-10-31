<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { settlementApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
import type { Activity, Balance, Member, Payment, PaymentAction, PaymentStatus, Transfer } from '../api/types'
import { formatCents } from '../utils/money'
import { allowedPaymentActions, paymentActions, paymentLabels } from '../utils/payment'
import PaymentDialog from './PaymentDialog.vue'

const props = defineProps<{ activity: Activity; members: Member[]; userId: number; refreshToken: number }>()
const emit = defineEmits<{ changed: [] }>()
const balances = ref<Balance[]>([]), suggestions = ref<Transfer[]>([]), payments = ref<Payment[]>([])
const busy = ref(false), changing = ref(false), error = ref(''), actionError = ref(''), more = ref(false)
const status = ref<PaymentStatus | ''>(''), dialog = ref(false), suggestion = ref<Transfer>()
const currentMember = computed(() => props.members.find(row => row.user_id === props.userId)?.id)
const owner = computed(() => props.activity.owner_id === props.userId)
const own = computed(() => balances.value.find(row => row.member_id === currentMember.value))
let controller: AbortController | null = null
function name(id: number) { return props.members.find(row => row.id === id)?.display_name || `成员 ${id}` }
async function load(append = false) {
  controller?.abort(); const current = new AbortController(); controller = current
  busy.value = true; error.value = ''
  try {
    const [balanceRows, transfers, paymentRows] = await Promise.all([
      settlementApi.balances(props.activity.id, current.signal), settlementApi.suggestions(props.activity.id, current.signal),
      settlementApi.payments(props.activity.id, { status: status.value, limit: 20, offset: append ? payments.value.length : 0 }, current.signal),
    ])
    if (current.signal.aborted) return
    balances.value = balanceRows; suggestions.value = transfers
    payments.value = append ? [...payments.value, ...paymentRows] : paymentRows; more.value = paymentRows.length === 20
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { if (controller === current) busy.value = false }
}
function register(transfer?: Transfer) { suggestion.value = transfer; dialog.value = true }
async function lifecycle(action: 'start' | 'archive') {
  if (changing.value) return
  const text = action === 'start' ? '封账后费用、成员和预算不能再修改。确认账目无误后开始结算？' : '确认归档这个已结清活动？归档后仍可查询和导出。'
  try { await ElMessageBox.confirm(text, action === 'start' ? '发起结算' : '归档活动', { confirmButtonText: '确认继续', cancelButtonText: '取消', type: 'warning' }) }
  catch { return }
  changing.value = true; actionError.value = ''
  try { await settlementApi[action](props.activity.id); ElMessage.success(action === 'start' ? '已封账，结算状态已更新' : '活动已归档'); emit('changed') }
  catch (cause) { if (!isCancelled(cause)) { actionError.value = errorMessage(cause); emit('changed') } }
  finally { changing.value = false }
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
function saved() { ElMessage.success('付款已登记，等待收款人确认'); emit('changed') }
watch(() => [props.activity.id, props.activity.status, props.refreshToken, status.value], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="settlement-content">
    <div class="lifecycle-bar"><div><h2>结算与付款</h2><p class="muted">净额来自共同费用；待确认付款仅占用可登记额度。</p></div><el-button v-if="owner && activity.status === 'ACTIVE'" type="primary" :loading="changing" @click="lifecycle('start')">封账并开始结算</el-button><el-button v-if="owner && activity.status === 'SETTLED'" type="primary" :loading="changing" @click="lifecycle('archive')">归档活动</el-button></div>
    <el-alert v-if="error || actionError" :title="actionError || error" type="error" :closable="false" role="alert" />
    <p v-if="activity.status === 'ACTIVE'" class="notice-box">当前为记账阶段。请先核对费用，再由创建者封账；封账后可登记付款。</p>
    <p v-if="['SETTLED', 'ARCHIVED'].includes(activity.status)" class="notice-box">所有余额已结清，无待确认付款。费用、余额及付款记录保留供查阅。</p>
    <div class="balance-grid">
      <article v-for="row in balances" :key="row.member_id" class="balance-card" :data-testid="`balance-${row.member_id}`">
        <h3>{{ name(row.member_id) }} <small v-if="row.member_id === currentMember">（我）</small></h3>
        <strong class="money" :class="{ payable: row.balance_cents < 0 }">{{ row.balance_cents > 0 ? '应收' : row.balance_cents < 0 ? '应付' : '已平账' }} ¥ {{ formatCents(Math.abs(row.balance_cents)) }}</strong>
        <dl><div><dt>累计垫付 / 承担</dt><dd>¥ {{ formatCents(row.paid_cents) }} / {{ formatCents(row.owed_cents) }}</dd></div><div><dt>已确认付出 / 收到</dt><dd>¥ {{ formatCents(row.confirmed_out_cents) }} / {{ formatCents(row.confirmed_in_cents) }}</dd></div><div><dt>待确认付出 / 收到</dt><dd>¥ {{ formatCents(row.pending_out_cents) }} / {{ formatCents(row.pending_in_cents) }}</dd></div><div><dt>可登记付出 / 收到</dt><dd>¥ {{ formatCents(row.available_out_cents) }} / {{ formatCents(row.available_in_cents) }}</dd></div></dl>
      </article>
    </div>
    <article class="panel ledger-panel"><div class="panel-heading"><div><h2>转账建议</h2><p class="muted">已扣除待确认占用，可按建议部分付款。</p></div><el-button v-if="activity.status === 'SETTLING' && own && own.available_out_cents > 0" type="primary" @click="register()">登记已付款</el-button></div>
      <div v-for="(row, index) in suggestions" :key="index" class="transfer-row"><span>{{ name(row.payer_member_id) }} <span class="transfer-arrow">→</span> {{ name(row.payee_member_id) }}</span><strong>¥ {{ formatCents(row.amount_cents) }}</strong><el-button v-if="activity.status === 'SETTLING' && row.payer_member_id === currentMember" @click="register(row)">按此建议登记</el-button></div>
      <p v-if="!busy && !suggestions.length" class="muted">暂无可登记的转账建议；如有待确认付款，请由收款人处理。</p>
    </article>
    <article class="panel ledger-panel"><div class="panel-heading"><h2>付款记录</h2><label class="payment-filter">状态 <select v-model="status" aria-label="付款状态筛选"><option value="">全部</option><option v-for="(label, key) in paymentLabels" :key="key" :value="key">{{ label }}</option></select></label></div>
      <p v-if="!busy && !payments.length" class="muted">暂无符合条件的付款。</p>
      <article v-for="row in payments" :key="row.id" class="payment-card" :data-testid="`payment-${row.id}`"><div class="entry-heading"><div><h3>{{ name(row.payer_member_id) }} → {{ name(row.payee_member_id) }}</h3><p class="muted">{{ new Date(row.created_at).toLocaleString('zh-CN') }} · <span :class="{ 'pending-label': row.status === 'PENDING' }">{{ paymentLabels[row.status] }}</span></p></div><strong class="money">¥ {{ formatCents(row.amount_cents) }}</strong></div><div v-if="activity.status === 'SETTLING'" class="entry-actions"><el-button v-for="action in allowedPaymentActions(row, currentMember)" :key="action" :type="action === 'confirm' ? 'primary' : 'default'" :disabled="changing" @click="change(row, action)">{{ paymentActions[action] }}</el-button></div></article>
      <el-button v-if="more" :loading="busy" @click="load(true)">加载更多付款</el-button>
    </article>
    <PaymentDialog v-model="dialog" :activity="activity" :balances="balances" :members="members" :member-id="currentMember" :suggestion="suggestion" @saved="saved" @refresh="emit('changed')" />
  </section>
</template>
