import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 轮询组合式函数
 */
export function usePolling(
  callback: () => void | Promise<void>,
  interval: number = 5000,
  options?: {
    immediate?: boolean
    enabled?: boolean
  }
) {
  const isPolling = ref(false)
  const timerId = ref<number>()

  // 开始轮询
  const start = () => {
    if (isPolling.value) return

    isPolling.value = true

    const poll = async () => {
      if (!isPolling.value) return

      try {
        await callback()
      } catch (error) {
        console.error('Polling error:', error)
      }

      if (isPolling.value) {
        timerId.value = window.setTimeout(poll, interval)
      }
    }

    poll()
  }

  // 停止轮询
  const stop = () => {
    isPolling.value = false
    if (timerId.value) {
      clearTimeout(timerId.value)
      timerId.value = undefined
    }
  }

  // 重启轮询
  const restart = () => {
    stop()
    start()
  }

  onMounted(() => {
    if (options?.enabled !== false) {
      if (options?.immediate) {
        callback()
      }
      start()
    }
  })

  onUnmounted(() => {
    stop()
  })

  return {
    isPolling,
    start,
    stop,
    restart
  }
}
