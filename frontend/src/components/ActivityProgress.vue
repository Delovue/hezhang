<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { settlementApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
import type { Activity, ActivityStatus } from '../api/types'
import { statusDescriptions, statusLabels } from '../utils/activity'

const props = defineProps<{ activity: Activity; owner: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const steps: ActivityStatus[] = ['ACTIVE', 'SETTLING', 'SETTLED', 'ARCHIVED']
const current = computed(() => steps.indexOf(props.activity.status))
const changing = ref(false), error = ref('')
async function lifecycle(action: 'start' | 'archive') {
  if (changing.value) return
  const text = action === 'start' ? '封账后费用、成员和预算不能再修改。确认账目无误后开始结算？' : '确认归档这个已结清活动？归档后仍可查询和导出。'
  try { await ElMessageBox.confirm(text, action === 'start' ? '发起结算' : '归档活动', { confirmButtonText: '确认继续', cancelButtonText: '取消', type: 'warning' }) }
  catch { return }
  changing.value = true; error.value = ''
  try { await settlementApi[action](props.activity.id); ElMessage.success(action === 'start' ? '已封账，结算状态已更新' : '活动已归档'); emit('changed') }
  catch (cause) { if (!isCancelled(cause)) { error.value = errorMessage(cause); emit('changed') } }
  finally { changing.value = false }
}
</script>

<template>
  <div class="activity-progress">
    <ol class="progress-steps" aria-label="活动进度">
      <li v-for="(step, index) in steps" :key="step" :class="{ done: index < current, current: index === current }" :aria-current="index === current ? 'step' : undefined">{{ statusLabels[step] }}</li>
    </ol>
    <p class="progress-hint">{{ statusDescriptions[activity.status] }}</p>
    <el-button v-if="owner && activity.status === 'ACTIVE'" type="primary" :loading="changing" @click="lifecycle('start')">封账并开始结算</el-button>
    <el-button v-if="owner && activity.status === 'SETTLED'" type="primary" :loading="changing" @click="lifecycle('archive')">归档活动</el-button>
  </div>
  <el-alert v-if="error" :title="error" type="error" :closable="false" role="alert" class="section-alert" />
</template>
