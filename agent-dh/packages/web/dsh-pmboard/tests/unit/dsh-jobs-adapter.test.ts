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

  // REQ-260927144541-0481 根因修复：装配层要求的 JobsPort 形状（start/get/available）。
  // 此前本类只有 startJob/getJob —— 组合根拿不到这个形状，deps.jobs 恒 undefined，
  // 实施链因此退化为同步循环（调用被阻塞数分钟，且回执谎报『投递失败』）。
  it('JobsPort.start：透传 kind/label/owner，run 包装成 DSH 生产者钩子', async () => {
    // 关键回归：DSH 的 JobStart.run 必须**同步返回 JobHooks**（注册表调 hooks.cancel.bind(hooks)）。
    // 旧实现把 async 执行函数直接当 run 传 → run() 返回 Promise → hooks.cancel 为 undefined →
    // TypeError（Cannot read properties of undefined (reading 'bind')）→ 线上投递恒失败。
    // 旧用例只断言"参数被透传"（mock 从不调用 run()），因此漏掉了这条真实契约。
    let captured: any
    const ctx = { jobs: { start: vi.fn((spec: any) => { captured = spec; return 'job-9' }), get: vi.fn() } }
    const adapter = new DshJobsAdapter(ctx)
    const owner = { id: 'agent-1' }
    let observedSignal: AbortSignal | undefined
    const run = async (signal: AbortSignal) => { observedSignal = signal }
    const jobId = await adapter.start({ kind: 'reqboard', label: 'REQ-x', owner, run })
    expect(jobId).toBe('job-9')
    expect(captured.kind).toBe('reqboard')
    expect(captured.label).toBe('REQ-x')
    expect(captured.owner).toBe(owner)

    // 契约：run() 同步返回 { cancel, done }，且 done 可结算（不得 reject）。
    const hooks = captured.run()
    expect(typeof hooks.cancel).toBe('function')
    expect(hooks.done).toBeInstanceOf(Promise)
    await expect(hooks.done).resolves.toEqual({ status: 'completed' })
    expect(observedSignal?.aborted).toBe(false)
  })

  it('JobsPort.start：执行函数抛错 → done 结算为 failed（不 reject）', async () => {
    let captured: any
    const ctx = { jobs: { start: vi.fn((spec: any) => { captured = spec; return 'job-1' }), get: vi.fn() } }
    const adapter = new DshJobsAdapter(ctx)
    await adapter.start({ kind: 'reqboard', label: 'REQ-y', run: async () => { throw new Error('boom') } })
    const hooks = captured.run()
    await expect(hooks.done).resolves.toEqual({ status: 'failed', detail: 'boom' })
  })

  it('JobsPort.start：cancel 同步触发 AbortSignal（幂等）', async () => {
    let captured: any
    const ctx = { jobs: { start: vi.fn((spec: any) => { captured = spec; return 'job-2' }), get: vi.fn() } }
    const adapter = new DshJobsAdapter(ctx)
    let signal: AbortSignal | undefined
    const run = (s: AbortSignal) => new Promise<void>((resolve) => { signal = s; s.addEventListener('abort', () => resolve()) })
    await adapter.start({ kind: 'reqboard', label: 'REQ-z', run })
    const hooks = captured.run()
    hooks.cancel()
    hooks.cancel() // 幂等：重复取消不得抛错
    await hooks.done
    expect(signal?.aborted).toBe(true)
  })

  it('JobsPort.get：复用状态映射（job 不存在 → null）', async () => {
    const ctx = { jobs: { start: vi.fn(), get: vi.fn().mockResolvedValue(undefined) } }
    const adapter = new DshJobsAdapter(ctx)
    expect(await adapter.get('job-x')).toBeNull()
  })

  it('JobsPort.available：能构造即可用（advanceRequirement 据此选投递/同步路径）', () => {
    const ctx = { jobs: { start: vi.fn(), get: vi.fn() } }
    expect(new DshJobsAdapter(ctx).available()).toBe(true)
  })
})
