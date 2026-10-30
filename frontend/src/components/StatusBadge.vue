<script setup lang="ts">
import type { ActivityStatus } from '../api/types'
import { statusLabels } from '../utils/activity'
defineProps<{ status: ActivityStatus }>()
</script>

<template><span class="status-badge" :class="status.toLowerCase()"><i aria-hidden="true"></i>{{ statusLabels[status] }}</span></template>
