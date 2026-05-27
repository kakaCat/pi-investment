import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { io } from 'socket.io-client'
import { useWebSocket } from '@/composables/useWebSocket'

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => ({
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
    disconnect: vi.fn()
  }))
}))

describe('useWebSocket', () => {
  it('does not connect on mount when autoConnect is false', () => {
    const Component = defineComponent({
      setup() {
        useWebSocket('ws://127.0.0.1:5003', { autoConnect: false })
        return () => null
      }
    })

    mount(Component)

    expect(io).not.toHaveBeenCalled()
  })
})
