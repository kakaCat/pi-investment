import { vi } from 'vitest'

// Mock Element Plus
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  },
  ElNotification: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  }
}))

// Mock dayjs
vi.mock('dayjs', () => {
  const dayjs = vi.fn((date?: string | Date) => {
    const d = date ? new Date(date) : new Date('2024-01-01T12:00:00Z')
    return {
      format: (fmt: string) => {
        if (fmt === 'YYYY-MM-DD') return '2024-01-01'
        if (fmt === 'YYYY-MM-DD HH:mm:ss') return '2024-01-01 12:00:00'
        if (fmt === 'HH:mm:ss') return '12:00:00'
        return d.toISOString()
      },
      diff: (target: any, unit: string) => {
        if (unit === 'second') return 0
        return 0
      }
    }
  })

  dayjs.extend = vi.fn()

  return { default: dayjs }
})

// Global test utilities
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn()
}))

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn()
  }))
})
