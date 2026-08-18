<template>
  <span :title="description">{{ text }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  cron: string
}

const props = defineProps<Props>()

// 简化的 Cron 表达式解析
const description = computed(() => {
  const parts = props.cron.split(' ')
  if (parts.length !== 5) return props.cron

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts

  const desc: string[] = []

  // 分钟
  if (minute === '*') {
    desc.push('每分钟')
  } else if (minute.includes('/')) {
    const interval = minute.split('/')[1]
    desc.push(`每 ${interval} 分钟`)
  } else {
    desc.push(`第 ${minute} 分钟`)
  }

  // 小时
  if (hour === '*') {
    desc.push('每小时')
  } else if (hour.includes('/')) {
    const interval = hour.split('/')[1]
    desc.push(`每 ${interval} 小时`)
  } else {
    desc.push(`${hour} 点`)
  }

  // 日期
  if (dayOfMonth !== '*') {
    desc.push(`每月 ${dayOfMonth} 号`)
  }

  // 月份
  if (month !== '*') {
    desc.push(`${month} 月`)
  }

  // 星期
  if (dayOfWeek !== '*') {
    const weekdays = ['日', '一', '二', '三', '四', '五', '六']
    const day = parseInt(dayOfWeek)
    if (!isNaN(day)) {
      desc.push(`星期${weekdays[day]}`)
    }
  }

  return desc.join(', ')
})

const text = computed(() => {
  // 常见 Cron 表达式的快捷显示
  const commonPatterns: Record<string, string> = {
    '0 0 * * *': '每天 0:00',
    '0 */1 * * *': '每小时',
    '*/5 * * * *': '每 5 分钟',
    '0 0 * * 0': '每周日 0:00',
    '0 0 1 * *': '每月 1 号 0:00',
  }

  return commonPatterns[props.cron] || props.cron
})
</script>
