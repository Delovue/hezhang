<script setup lang="ts">
import { ref, watch } from 'vue'
import { activityApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
import type { Activity } from '../api/types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; joined: [activity: Activity] }>()
const code = ref('')
const busy = ref(false)
const error = ref('')
watch(() => props.modelValue, (open) => { if (open) { code.value = ''; error.value = '' } })
async function submit() {
  if (busy.value) return
  const value = code.value.trim()
  if (!value || value.length > 64) { error.value = '请输入有效的邀请码（最多 64 个字符）'; return }
  error.value = ''
  busy.value = true
  try {
    const activity = await activityApi.join(value)
    emit('update:modelValue', false)
    emit('joined', activity)
  } catch (cause) { if (!isCancelled(cause)) error.value = errorMessage(cause) }
  finally { busy.value = false }
}
</script>

<template>
  <el-dialog :model-value="modelValue" title="加入伙伴的活动" width="460px" :close-on-click-modal="false"
    :show-close="!busy" :close-on-press-escape="!busy" @update:model-value="!busy && emit('update:modelValue', $event)">
    <p class="dialog-intro">向活动创建者索取邀请码，加入后即可查看共同账目。</p>
    <form class="stack-form" @submit.prevent="submit">
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon role="alert" />
      <div class="form-field"><label for="invite-code">邀请码</label>
        <el-input id="invite-code" v-model="code" placeholder="粘贴活动邀请码" maxlength="64" :disabled="busy" autofocus />
        <p class="field-help">仅进行中的活动可以加入。</p>
      </div>
      <div class="dialog-actions"><el-button :disabled="busy" @click="emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" native-type="submit" :loading="busy">加入活动</el-button>
      </div>
    </form>
  </el-dialog>
</template>
