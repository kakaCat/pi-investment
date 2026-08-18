<template>
  <span :title="fullTime">{{ relativeTime }}</span>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

interface Props {
  time: string | Date
  autoUpdate?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  autoUpdate: true,
})

const now = ref(Date.now())
let timer: number | null = null

const relativeTime = computed(() => {
  const timestamp = typeof props.time === 'string' ? new Date(props.time).getTime() : props.time.getTime()
  const diff = now.value - timestamp
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  const months = Math.floor(days / 30)
  const years = Math.floor(days / 365)

  if (seconds < 60) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 30) return `${days} 天前`
  if (months < 12) return `${months} 个月前`
  return `${years} 年前`
})

const fullTime = computed(() => {
  const date = typeof props.time === 'string' ? new Date(props.time) : props.time
  return date.toLocaleString('zh-CN')
})

onMounted(() => {
  if (props.autoUpdate) {
    timer = window.setInterval(() => {
      now.value = Date.now()
    }, 60000) // 每分钟更新一次
  }
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>
