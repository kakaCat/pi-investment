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
  const isMounted = ref(true)

  // 包装回调，检查组件存活状态
  const safeCallback = async () => {
    if (!isMounted.value) return
    try {
      await callback()
      // 异步操作完成后再次检查，防止在组件卸载后更新响应式状态
      if (!isMounted.value) return
    } catch (error) {
      if (isMounted.value) {
        console.error('Polling error:', error)
      }
    }
  }

  // 开始轮询
  const start = () => {
    if (isPolling.value) return

    isPolling.value = true

    const poll = async () => {
      if (!isPolling.value) return

      await safeCallback()

      if (isPolling.value && isMounted.value) {
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
    if (isMounted.value) {
      start()
    }
  }

  onMounted(() => {
    if (options?.enabled !== false) {
      if (options?.immediate) {
        safeCallback()
      }
      start()
    }
  })

  onUnmounted(() => {
    isMounted.value = false
    stop()
  })

  return {
    isPolling,
    start,
    stop,
    restart
  }
}
