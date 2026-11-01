<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { settlementApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
import type { Activity, Balance, Member, Transfer } from '../api/types'
import { formatCents, signedCents } from '../utils/money'
import { avatarTone, initial } from '../utils/members'
import PaymentDialog from './PaymentDialog.vue'

const props = defineProps<{ activity: Activity; members: Member[]; userId: number; refreshToken: number; ready: boolean }>()
const emit = defineEmits<{ changed: []; review: [] }>()
const balances = ref<Balance[]>([]), suggestions = ref<Transfer[]>([])
const busy = ref(false), error = ref(''), dialog = ref(false), suggestion = ref<Transfer>()
const canRegister = computed(() => props.ready && !busy.value && !error.value)
const currentMember = computed(() => props.members.find(row => row.user_id === props.userId)?.id)
const own = computed(() => balances.value.find(row => row.member_id === currentMember.value))
const toPay = computed(() => suggestions.value.filter(row => row.payer_member_id === currentMember.value))
const toReceive = computed(() => suggestions.value.filter(row => row.payee_member_id === currentMember.value))
const hasPending = computed(() => balances.value.some(row => row.pending_out_cents > 0 || row.pending_in_cents > 0))
const largest = computed(() => Math.max(1, ...balances.value.map(row => Math.abs(row.balance_cents))))
const tone = computed(() => !own.value || own.value.balance_cents === 0 ? 'settled' : own.value.balance_cents > 0 ? 'receivable' : 'payable')
let controller: AbortController | null = null
function name(id: number) { return props.members.find(row => row.id === id)?.display_name || `成员 ${id}` }
function width(cents: number) { return `${Math.round(Math.abs(cents) / largest.value * 100)}%` }
async function load() {
  controller?.abort(); const current = new AbortController(); controller = current
  busy.value = true; error.value = ''
  try {
    const [balanceRows, transfers] = await Promise.all([
      settlementApi.balances(props.activity.id, current.signal), settlementApi.suggestions(props.activity.id, current.signal),
    ])
    if (current.signal.aborted) return
    balances.value = balanceRows; suggestions.value = transfers
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { if (controller === current) busy.value = false }
}
function register(transfer?: Transfer) { if (canRegister.value) { suggestion.value = transfer; dialog.value = true } }
function saved() { ElMessage.success('付款已登记，等待收款人确认'); emit('changed') }
watch(() => [props.activity.id, props.activity.status, props.refreshToken], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <div class="settlement-summary">
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <section v-if="own" class="rail-card own-card" :class="tone">
      <h2>你的账</h2>
      <p v-if="own.balance_cents < 0 && toPay.length" class="own-sentence">还需<template v-for="(row, index) in toPay" :key="row.payee_member_id">{{ index ? '，' : '' }}付给{{ name(row.payee_member_id) }} <span class="money">¥ {{ formatCents(row.amount_cents) }}</span></template>。</p>
      <p v-else-if="own.balance_cents < 0" class="own-sentence">应付 <span class="money">¥ {{ formatCents(-own.balance_cents) }}</span>，已全部登记。</p>
      <p v-else-if="own.balance_cents > 0" class="own-sentence">还应收回 <span class="money">¥ {{ formatCents(own.balance_cents) }}</span><template v-if="toReceive.length">，来自{{ toReceive.map(row => name(row.payer_member_id)).join('、') }}</template>。</p>
      <p v-else class="own-sentence">你已平账，无需付款。</p>
      <el-button v-if="activity.status === 'SETTLING' && own.available_out_cents > 0" type="primary" :disabled="!canRegister" @click="register()">登记已付款</el-button>
      <p v-if="activity.status === 'ACTIVE' && own.balance_cents !== 0" class="own-note">当前为预估金额，封账后即可登记付款。</p>
      <p v-if="own.pending_out_cents > 0" class="own-note">已登记付款 ¥ {{ formatCents(own.pending_out_cents) }}，等待对方确认。</p>
      <p v-if="own.pending_in_cents > 0" class="own-note">有 ¥ {{ formatCents(own.pending_in_cents) }} 付款等待你确认收款。<button type="button" class="inline-link" @click="emit('review')">去处理</button></p>
    </section>
    <section v-if="balances.length" class="rail-card">
      <h2>余额 <small>负数为应付</small></h2>
      <div v-for="row in balances" :key="row.member_id" class="balance-bar">
        <span class="bar-name"><span class="avatar mini" :class="avatarTone(row.member_id)" aria-hidden="true">{{ initial(name(row.member_id)) }}</span><span>{{ name(row.member_id) }}</span></span>
        <span class="bar-track payable-side"><i v-if="row.balance_cents < 0" :style="{ width: width(row.balance_cents) }"></i></span>
        <span class="bar-track receivable-side"><i v-if="row.balance_cents > 0" :style="{ width: width(row.balance_cents) }"></i></span>
        <b class="money" :class="row.balance_cents > 0 ? 'receivable' : row.balance_cents < 0 ? 'payable' : ''">{{ signedCents(row.balance_cents) }}</b>
      </div>
    </section>
    <section v-if="balances.length" class="rail-card">
      <h2>转账建议 <small v-if="suggestions.length">{{ suggestions.length }} 笔建议</small></h2>
      <p v-if="hasPending && suggestions.length" class="muted">仍有付款等待确认，确认后才会抵扣余额。</p>
      <div v-for="(row, index) in suggestions" :key="index" class="suggestion-row">
        <span class="avatar mini" :class="avatarTone(row.payer_member_id)" :title="name(row.payer_member_id)" aria-hidden="true">{{ initial(name(row.payer_member_id)) }}</span>
        <span class="suggestion-text">{{ name(row.payer_member_id) }} <span class="suggestion-arrow" aria-label="付给">→</span> {{ name(row.payee_member_id) }}</span>
        <strong class="money">¥ {{ formatCents(row.amount_cents) }}</strong>
        <el-button v-if="activity.status === 'SETTLING' && row.payer_member_id === currentMember" size="small" :disabled="!canRegister" :aria-label="`按此建议登记：付给${name(row.payee_member_id)} ¥ ${formatCents(row.amount_cents)}`" @click="register(row)">登记</el-button>
      </div>
      <p v-if="!busy && !suggestions.length" class="muted">{{ hasPending ? '暂无可登记的转账，仍有付款等待确认。' : '暂无需要的转账。' }}</p>
    </section>
    <PaymentDialog v-model="dialog" :activity="activity" :balances="balances" :members="members" :member-id="currentMember" :suggestion="suggestion" @saved="saved" @refresh="emit('changed')" />
  </div>
</template>
