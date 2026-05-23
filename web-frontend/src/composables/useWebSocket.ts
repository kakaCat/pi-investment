import { ref, onMounted, onUnmounted } from 'vue'
import { io, Socket } from 'socket.io-client'
import { WS_URL } from '@/utils/constants'

/**
 * WebSocket 组合式函数
 */
export function useWebSocket(url: string = WS_URL) {
  const socket = ref<Socket>()
  const connected = ref(false)
  const error = ref<string | null>(null)

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
      connected.value = true
      error.value = null
      console.log('WebSocket connected')
    })

    socket.value.on('disconnect', () => {
      connected.value = false
      console.log('WebSocket disconnected')
    })

    socket.value.on('error', (err: any) => {
      error.value = err.message
      console.error('WebSocket error:', err)
    })
  }

  // 断开连接
  const disconnect = () => {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = undefined
    }
  }

  // 发送消息
  const emit = (event: string, data?: any) => {
    if (socket.value && connected.value) {
      socket.value.emit(event, data)
    }
  }

  // 监听消息
  const on = (event: string, callback: (...args: any[]) => void) => {
    if (socket.value) {
      socket.value.on(event, callback)
    }
  }

  // 取消监听
  const off = (event: string, callback?: (...args: any[]) => void) => {
    if (socket.value) {
      socket.value.off(event, callback)
    }
  }

  onMounted(() => {
    connect()
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    socket,
    connected,
    error,
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
export function useMarketWebSocket() {
  const ws = useWebSocket()
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
