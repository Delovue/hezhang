<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { activityApi } from '../api'
import { ApiError, errorMessage, isCancelled } from '../api/client'
import type { Activity } from '../api/types'
import { centsToInput, parseYuan } from '../utils/money'

const props = defineProps<{ modelValue: boolean; activity?: Activity }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  saved: [activity: Activity]
  refresh: []
}>()
const form = reactive({ name: '', budget: '' })
const busy = ref(false)
const error = ref('')
const uncertain = ref(false)
watch(() => props.modelValue, (open) => {
  if (open) {
    form.name = props.activity?.name || ''
    form.budget = centsToInput(props.activity?.budget_cents ?? null)
    error.value = ''
    uncertain.value = false
  }
})

async function submit() {
  if (busy.value || uncertain.value) return
  error.value = ''
  const name = form.name.trim()
  if (!name || name.length > 100) { error.value = '活动名称请输入 1–100 个字符'; return }
  let budget: number | null
  try { budget = parseYuan(form.budget, true) }
  catch (cause) { error.value = errorMessage(cause); return }
  busy.value = true
  try {
    const body = { name, budget_cents: budget }
    const activity = props.activity ? await activityApi.update(props.activity.id, body) : await activityApi.create(body)
    emit('update:modelValue', false)
    emit('saved', activity)
  } catch (cause) {
    if (!isCancelled(cause)) error.value = errorMessage(cause)
    // Creation has no request_id contract. Do not invite another POST after an ambiguous failure.
    if (!props.activity && cause instanceof ApiError && (cause.status === 0 || cause.status >= 500)) uncertain.value = true
    if (cause instanceof ApiError && cause.code === 'ACTIVITY_LOCKED') emit('refresh')
  } finally { busy.value = false }
}
</script>

<template>
  <el-dialog :model-value="modelValue" :title="activity ? '编辑活动' : '创建新活动'" width="480px"
    :close-on-click-modal="false" :close-on-press-escape="!busy" :show-close="!busy"
    @update:model-value="!busy && emit('update:modelValue', $event)">
    <p class="dialog-intro">{{ activity ? '调整活动名称和总预算。' : '给这次相聚起个名字，邀请伙伴一起记账。' }}</p>
    <form class="stack-form" @submit.prevent="submit">
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
      <div class="form-field"><label for="activity-name">活动名称 <span>*</span></label>
        <el-input id="activity-name" v-model="form.name" placeholder="例如：周末杭州之旅" maxlength="100" show-word-limit :disabled="busy || uncertain" autofocus />
      </div>
      <div class="form-field"><label for="activity-budget">总预算 <small>选填</small></label>
        <el-input id="activity-budget" v-model="form.budget" placeholder="留空表示不设置预算" inputmode="decimal" :disabled="busy || uncertain"><template #suffix>元</template></el-input>
        <p class="field-help">最多两位小数；填写 0 表示预算为 0 元。</p>
      </div>
      <div class="dialog-actions">
        <el-button :disabled="busy" @click="emit('update:modelValue', false)">{{ uncertain ? '关闭并核对活动列表' : '取消' }}</el-button>
        <el-button type="primary" native-type="submit" :loading="busy" :disabled="uncertain || (activity !== undefined && activity.status !== 'ACTIVE')">{{ activity ? '保存修改' : '创建活动' }}</el-button>
      </div>
      <p v-if="uncertain" class="field-help">创建结果尚不确定。关闭后刷新活动列表，确认是否已创建，再决定是否重新提交。</p>
    </form>
  </el-dialog>
</template>
