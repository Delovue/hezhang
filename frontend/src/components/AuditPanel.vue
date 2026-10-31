<script setup lang="ts">
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { activityApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
import type { AuditEntry, Member } from '../api/types'
import { parseActivityId } from '../utils/activity'
import { actionLabels, auditChanges, objectLabels } from '../utils/audit'

const props = defineProps<{ activityId: number; members: Member[]; refreshToken: number }>()
const filters = reactive({ action: '', object_type: '', object_id: '', actor_user_id: '' })
const rows = ref<AuditEntry[]>([]), busy = ref(false), error = ref(''), more = ref(false)
let controller: AbortController | null = null
let applied: Record<string, string | number | undefined> = {}
async function load(append = false) {
  error.value = ''
  if (!append) {
    if (filters.object_id && (!filters.object_type || parseActivityId(filters.object_id) === null)) { error.value = '查询对象编号时，请选择对象类型并填写有效的正整数编号'; return }
    applied = { ...filters }
  }
  controller?.abort(); const current = new AbortController(); controller = current; busy.value = true
  try {
    const next = await activityApi.history(props.activityId, { ...applied, limit: 20, before_id: append ? rows.value.at(-1)?.id : undefined }, current.signal)
    if (current.signal.aborted) return
    rows.value = append ? [...rows.value, ...next] : next; more.value = next.length === 20
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { if (controller === current) busy.value = false }
}
watch(() => [props.activityId, props.refreshToken], () => void load(), { immediate: true })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <section class="panel ledger-panel">
    <div class="panel-heading"><div><h2>操作历史</h2><p class="muted">按时间倒序记录操作者及变化内容，删除费用后记录仍保留。</p></div></div>
    <form class="filter-grid" @submit.prevent="load()">
      <label>操作类型<select v-model="filters.action" aria-label="操作类型"><option value="">全部操作</option><option v-for="(label, key) in actionLabels" :key="key" :value="key">{{ label }}</option></select></label>
      <label>对象类型<select v-model="filters.object_type" aria-label="对象类型"><option value="">全部对象</option><option v-for="(label, key) in objectLabels" :key="key" :value="key">{{ label }}</option></select></label>
      <label>对象编号<input v-model="filters.object_id" inputmode="numeric" placeholder="例如费用编号" /></label>
      <label>操作者<select v-model="filters.actor_user_id" aria-label="操作者"><option value="">全部成员</option><option v-for="member in members" :key="member.id" :value="member.user_id">{{ member.display_name }}</option></select></label>
      <el-button native-type="submit" :loading="busy">筛选历史</el-button>
    </form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" />
    <p v-if="!busy && !error && !rows.length" class="muted">暂无符合条件的历史。</p>
    <article v-for="row in rows" :key="row.id" class="audit-entry" :data-audit-id="row.id">
      <div class="audit-heading"><strong>{{ members.find(m => m.user_id === row.actor_user_id)?.display_name || `用户 ${row.actor_user_id}` }} · {{ actionLabels[row.action] || row.action }}</strong><time :datetime="row.created_at">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</time></div>
      <p class="muted">{{ objectLabels[row.object_type] || row.object_type }} #{{ row.object_id }}</p>
      <details><summary>查看变更详情</summary><div class="audit-table-wrap"><table class="audit-table"><thead><tr><th>字段</th><th>变更前</th><th>变更后</th></tr></thead><tbody><tr v-for="change in auditChanges(row, members)" :key="change.key" :data-field="change.key"><th>{{ change.label }}</th><td>{{ change.before }}</td><td>{{ change.after }}</td></tr></tbody></table></div></details>
    </article>
    <el-button v-if="more" :loading="busy" @click="load(true)">加载更早历史</el-button>
  </section>
</template>
