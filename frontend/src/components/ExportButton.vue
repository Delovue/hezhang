<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { activityApi } from '../api'
import { errorMessage, isCancelled } from '../api/client'
const props = defineProps<{ activityId: number; name: string }>()
const busy = ref(false)
async function download() {
  if (busy.value) return
  busy.value = true
  try {
    const blob = await activityApi.exportCsv(props.activityId)
    if (!blob.type.startsWith('text/csv')) throw new Error('导出响应格式错误，请稍后重试')
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `${props.name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_')}-费用明细.csv`
    document.body.append(anchor); anchor.click(); anchor.remove()
    setTimeout(() => URL.revokeObjectURL(url), 30_000)
  } catch (cause) { if (!isCancelled(cause)) ElMessage.error(errorMessage(cause)) }
  finally { busy.value = false }
}
</script>
<template><el-button :loading="busy" @click="download">导出费用 CSV</el-button></template>
