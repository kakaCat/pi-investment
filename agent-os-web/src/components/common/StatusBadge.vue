<template>
  <el-tag :type="type" :size="size">
    {{ text }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  status: string
  size?: 'large' | 'default' | 'small'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'default',
})

const statusConfig: Record<string, { text: string; type: any }> = {
  // 通用状态
  success: { text: '成功', type: 'success' },
  failed: { text: '失败', type: 'danger' },
  error: { text: '错误', type: 'danger' },
  warning: { text: '警告', type: 'warning' },
  info: { text: '信息', type: 'info' },
  
  // 任务状态
  running: { text: '运行中', type: 'primary' },
  pending: { text: '待处理', type: 'info' },
  completed: { text: '已完成', type: 'success' },
  cancelled: { text: '已取消', type: 'info' },
  timeout: { text: '超时', type: 'warning' },
  skipped: { text: '已跳过', type: 'info' },
  
  // 启用状态
  enabled: { text: '启用', type: 'success' },
  disabled: { text: '禁用', type: 'info' },
  active: { text: '活跃', type: 'success' },
  inactive: { text: '停用', type: 'info' },
  
  // 执行状态
  executed: { text: '已执行', type: 'success' },
  executing: { text: '执行中', type: 'primary' },
  
  // 健康状态
  healthy: { text: '正常', type: 'success' },
  unhealthy: { text: '异常', type: 'danger' },
}

const text = computed(() => {
  return statusConfig[props.status]?.text || props.status
})

const type = computed(() => {
  return statusConfig[props.status]?.type || 'info'
})
</script>
