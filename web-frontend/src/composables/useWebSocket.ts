import { ref, onMounted, onUnmounted } from 'vue'
import { io, Socket } from 'socket.io-client'
import { WS_URL } from '@/utils/constants'

/**
 * WebSocket 组合式函数
 */
interface UseWebSocketOptions {
  autoConnect?: boolean
}

export function useWebSocket(url: string = WS_URL, options: UseWebSocketOptions = {}) {
  const { autoConnect = true } = options
  const socket = ref<Socket>()
  const connected = ref(false)
  const error = ref<string | null>(null)
  const isMounted = ref(true)

  // 追踪所有注册的事件监听器，用于清理
  const listeners: Array<{ event: string; callback: (...args: any[]) => void }> = []

  // 连接
  const connect = () => {
    if (!url) {
      return
    }

    socket.value = io(url, {
      transports: ['websocket'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    })

    socket.value.on('connect', () => {
      if (!isMounted.value) return
      connected.value = true
      error.value = null
      console.log('WebSocket connected')
    })

    socket.value.on('disconnect', () => {
      if (!isMounted.value) return
      connected.value = false
      console.log('WebSocket disconnected')
    })

    socket.value.on('error', (err: any) => {
      if (!isMounted.value) return
      error.value = err.message
      console.error('WebSocket error:', err)
    })
  }

  // 断开连接
  const disconnect = () => {
    isMounted.value = false
    // 先移除所有自定义监听器，防止回调在组件卸载后触发
    listeners.forEach(({ event, callback }) => {
      socket.value?.off(event, callback)
    })
    listeners.length = 0
    if (socket.value) {
      socket.value.disconnect()
      socket.value = undefined
    }
  }

  // 发送消息
  const emit = (event: string, data?: any) => {
    if (!isMounted.value) return
    if (socket.value && connected.value) {
      socket.value.emit(event, data)
    }
  }

  // 监听消息（包装回调以检查组件存活状态）
  const on = (event: string, callback: (...args: any[]) => void) => {
    const wrappedCallback = (...args: any[]) => {
      if (!isMounted.value) return
      callback(...args)
    }
    listeners.push({ event, callback: wrappedCallback })
    if (socket.value) {
      socket.value.on(event, wrappedCallback)
    }
  }

  // 取消监听
  const off = (event: string, callback?: (...args: any[]) => void) => {
    if (socket.value) {
      socket.value.off(event, callback)
    }
  }

  onMounted(() => {
    if (autoConnect) {
      connect()
    }
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    socket,
    connected,
    error,
    isMounted,
    connect,
    disconnect,
    emit,
    on,
    off
  }
}

/**
 * 市场行情 WebSocket
 */
export function useMarketWebSocket(options: UseWebSocketOptions = {}) {
  const ws = useWebSocket(WS_URL, options)
  const quotes = ref<Map<string, any>>(new Map())

  // 订阅股票
  const subscribe = (symbol: string) => {
    ws.emit('subscribe', { symbol })
  }

  // 取消订阅
  const unsubscribe = (symbol: string) => {
    ws.emit('unsubscribe', { symbol })
  }

  // 监听行情更新
  ws.on('quote', (data: any) => {
    quotes.value.set(data.symbol, data)
  })

  return {
    ...ws,
    quotes,
    subscribe,
    unsubscribe
  }
}

/**
 * 信号 WebSocket
 */
export function useSignalWebSocket() {
  const ws = useWebSocket()
  const signals = ref<any[]>([])

  // 监听新信号
  ws.on('signal', (data: any) => {
    signals.value.unshift(data)
  })

  return {
    ...ws,
    signals
  }
}

/**
 * Agent WebSocket
 */
export function useAgentWebSocket() {
  const ws = useWebSocket()
  const logs = ref<any[]>([])

  // 监听Agent日志
  ws.on('agent:log', (data: any) => {
    logs.value.unshift(data)
  })

  return {
    ...ws,
    logs
  }
}
