/**
 * DSH Jobs 适配器测试
 */

import { describe, it, expect, vi } from 'vitest'
import { DshJobsAdapter, DshJobsUnavailable } from '../../src/adapters/DshJobsAdapter.js'

describe('DshJobsAdapter', () => {
  it('构造时检测 ctx.jobs 不可用', () => {
    const ctx = {}
    
    expect(() => new DshJobsAdapter(ctx)).toThrow(DshJobsUnavailable)
    expect(() => new DshJobsAdapter(ctx)).toThrow('ctx.jobs.start is not available')
  })

  it('构造时检测 ctx.jobs.start 不可用', () => {
    const ctx = { jobs: {} }
    
    expect(() => new DshJobsAdapter(ctx)).toThrow(DshJobsUnavailable)
  })

  it('构造时检测 ctx.jobs.get 不可用', () => {
    const ctx = { jobs: { start: vi.fn() } }
    
    expect(() => new DshJobsAdapter(ctx)).toThrow(DshJobsUnavailable)
  })

  it('构造成功：ctx.jobs 完整可用', () => {
    const ctx = {
      jobs: {
        start: vi.fn(),
        get: vi.fn()
      }
    }
    
    expect(() => new DshJobsAdapter(ctx)).not.toThrow()
  })

  it('startJob 返回 jobId', async () => {
    const mockJobId = 'job-123'
    const ctx = {
      jobs: {
        start: vi.fn().mockResolvedValue(mockJobId),
        get: vi.fn()
      }
    }
    
    const adapter = new DshJobsAdapter(ctx)
    const jobId = await adapter.startJob({
      kind: 'reqboard',
      run: async () => {}
    })
    
    expect(jobId).toBe(mockJobId)
    expect(ctx.jobs.start).toHaveBeenCalledOnce()
    expect(ctx.jobs.start).toHaveBeenCalledWith({
      kind: 'reqboard',
      run: expect.any(Function),
      label: undefined
    })
  })

  it('startJob 传递 label', async () => {
    const ctx = {
      jobs: {
        start: vi.fn().mockResolvedValue('job-456'),
        get: vi.fn()
      }
    }
    
    const adapter = new DshJobsAdapter(ctx)
    await adapter.startJob({
      kind: 'test',
      run: async () => {},
      label: 'Test Job'
    })
    
    expect(ctx.jobs.start).toHaveBeenCalledWith({
      kind: 'test',
      run: expect.any(Function),
      label: 'Test Job'
    })
  })

  it('getJob 返回快照', async () => {
    const mockJob = {
      id: 'job-789',
      status: 'running',
      startedAt: Date.now()
    }
    
    const ctx = {
      jobs: {
        start: vi.fn(),
        get: vi.fn().mockResolvedValue(mockJob)
      }
    }
    
    const adapter = new DshJobsAdapter(ctx)
    const snapshot = await adapter.getJob('job-789')
    
    expect(snapshot).toEqual({
      id: 'job-789',
      status: 'running',
      startedAt: mockJob.startedAt,
      finishedAt: undefined,
      error: undefined
    })
    expect(ctx.jobs.get).toHaveBeenCalledWith('job-789')
  })

  it('getJob 返回 null：job 不存在', async () => {
    const ctx = {
      jobs: {
        start: vi.fn(),
        get: vi.fn().mockResolvedValue(null)
      }
    }
    
    const adapter = new DshJobsAdapter(ctx)
    const snapshot = await adapter.getJob('not-exist')
    
    expect(snapshot).toBeNull()
  })

  it('getJob 映射状态：completed', async () => {
    const ctx = {
      jobs: {
        start: vi.fn(),
        get: vi.fn().mockResolvedValue({
          id: 'job-done',
          status: 'completed',
          startedAt: 1000,
          finishedAt: 2000
        })
      }
    }
    
    const adapter = new DshJobsAdapter(ctx)
    const snapshot = await adapter.getJob('job-done')
    
    expect(snapshot?.status).toBe('completed')
    expect(snapshot?.finishedAt).toBe(2000)
  })

  it('getJob 映射状态：failed', async () => {
    const ctx = {
      jobs: {
        start: vi.fn(),
        get: vi.fn().mockResolvedValue({
          id: 'job-fail',
          status: 'failed',
          error: 'Test error'
        })
      }
    }
    
    const adapter = new DshJobsAdapter(ctx)
    const snapshot = await adapter.getJob('job-fail')
    
    expect(snapshot?.status).toBe('failed')
    expect(snapshot?.error).toBe('Test error')
  })

  it('isAvailable 静态方法：检测可用性', () => {
    const availableCtx = {
      jobs: {
        start: vi.fn(),
        get: vi.fn()
      }
    }
    
    const unavailableCtx1 = {}
    const unavailableCtx2 = { jobs: {} }
    const unavailableCtx3 = { jobs: { start: vi.fn() } }
    
    expect(DshJobsAdapter.isAvailable(availableCtx)).toBe(true)
    expect(DshJobsAdapter.isAvailable(unavailableCtx1)).toBe(false)
    expect(DshJobsAdapter.isAvailable(unavailableCtx2)).toBe(false)
    expect(DshJobsAdapter.isAvailable(unavailableCtx3)).toBe(false)
  })
})
