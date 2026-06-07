import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { useScheduler } from '@/composables/useScheduler'
import { apiClient } from '@/services/api/client'
import type { Task } from '@/types/scheduler'

vi.mock('@/services/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

const createTask = (overrides: Partial<Task> = {}): Task => ({
  id: 'task-1',
  name: '数据更新',
  command: 'data_update',
  cron: '0 8 * * 1-5',
  params: '',
  description: '',
  enabled: true,
  lastRun: null,
  nextRun: null,
  lastStatus: null,
  level: 'idle',
  isRunning: false,
  ...overrides,
})

describe('useScheduler', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiClient.get).mockResolvedValue({ tasks: [], runs: [] })
  })

  it('deduplicates rapid trigger clicks for the same task while the first request is pending', async () => {
    let resolvePost!: () => void
    vi.mocked(apiClient.post).mockReturnValue(new Promise<void>((resolve) => {
      resolvePost = resolve
    }))

    const scheduler = useScheduler()
    const task = createTask()

    const firstTrigger = scheduler.triggerTask(task)
    await nextTick()

    const secondTrigger = scheduler.triggerTask(task)

    expect(apiClient.post).toHaveBeenCalledTimes(1)
    expect(apiClient.post).toHaveBeenCalledWith('/api/scheduler/tasks/task-1/trigger')
    expect(scheduler.isTaskTriggering(task)).toBe(true)

    resolvePost()
    await firstTrigger
    await secondTrigger

    expect(scheduler.isTaskTriggering(task)).toBe(false)
  })
})
