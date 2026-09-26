/**
 * 后台执行器测试
 */

import { describe, it, expect, vi } from 'vitest'
import { BackgroundRunner } from '../../src/application/internal/background-runner.js'
import type { ExecutionContext } from '../../src/application/internal/background-runner.js'
import type { RequirementRecord, TaskRecord } from '../../src/client/types.js'

// 创建测试需求
function createRequirement(id: string, advance?: any): RequirementRecord {
  return {
    id,
    title: 'Test Requirement',
    description: 'Test',
    status: 'implementing',
    blocked: false,
    advance,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  } as RequirementRecord
}

// 创建测试任务
function createTask(id: string, status: 'todo' | 'done', dependsOn: string[] = []): TaskRecord {
  return {
    id,
    requirementId: 'REQ-test',
    title: `Task ${id}`,
    description: 'Test task',
    phase: 'implement',
    side: 'backend',
    dependsOn,
    scope: { apis: [], tables: [], files: [] },
    acceptance: 'Test',
    context: '',
    filesPlanned: [],
    status,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  } as TaskRecord
}

describe('BackgroundRunner', () => {
  const runner = new BackgroundRunner()

  describe('runChain', () => {
    it('全部完成：返回 completed', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [
        createTask('t1', 'done'),
        createTask('t2', 'done')
      ]
      
      const controller = new AbortController()
      const ctx: ExecutionContext = {
        requirementId: 'REQ-1',
        runId: 'run-123',
        signal: controller.signal,
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        executeSubtask: vi.fn().mockResolvedValue(undefined),
        updateRequirement: vi.fn().mockResolvedValue(undefined)
      }
      
      const result = await runner.runChain(ctx)
      
      expect(result.status).toBe('completed')
      expect(result.totalSteps).toBe(0)
    })

    it('执行单个任务', async () => {
      const requirement = createRequirement('REQ-1')
      let tasks = [createTask('t1', 'todo')]
      
      const executeSubtask = vi.fn().mockImplementation(async () => {
        // 模拟任务完成
        tasks = [createTask('t1', 'done')]
      })
      
      const controller = new AbortController()
      const ctx: ExecutionContext = {
        requirementId: 'REQ-1',
        runId: 'run-123',
        signal: controller.signal,
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockImplementation(async () => tasks),
        executeSubtask,
        updateRequirement: vi.fn().mockResolvedValue(undefined)
      }
      
      const result = await runner.runChain(ctx)
      
      expect(result.status).toBe('completed')
      expect(result.totalSteps).toBe(1)
      expect(executeSubtask).toHaveBeenCalledWith('t1')
    })

    it('依赖关系：先执行依赖任务', async () => {
      const requirement = createRequirement('REQ-1')
      const executionOrder: string[] = []
      
      let tasks = [
        createTask('t1', 'todo'),
        createTask('t2', 'todo', ['t1']) // t2 依赖 t1
      ]
      
      const executeSubtask = vi.fn().mockImplementation(async (taskId: string) => {
        executionOrder.push(taskId)
        // 模拟任务完成
        tasks = tasks.map(t => t.id === taskId ? createTask(taskId, 'done', t.dependsOn) : t)
      })
      
      const controller = new AbortController()
      const ctx: ExecutionContext = {
        requirementId: 'REQ-1',
        runId: 'run-123',
        signal: controller.signal,
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockImplementation(async () => tasks),
        executeSubtask,
        updateRequirement: vi.fn().mockResolvedValue(undefined)
      }
      
      const result = await runner.runChain(ctx)
      
      expect(result.status).toBe('completed')
      expect(executionOrder).toEqual(['t1', 't2'])
    })

    it('取消信号：返回 cancelled', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [createTask('t1', 'todo')]
      
      const controller = new AbortController()
      const ctx: ExecutionContext = {
        requirementId: 'REQ-1',
        runId: 'run-123',
        signal: controller.signal,
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        executeSubtask: vi.fn().mockImplementation(async () => {
          // 执行中取消
          controller.abort()
        }),
        updateRequirement: vi.fn().mockResolvedValue(undefined)
      }
      
      const result = await runner.runChain(ctx)
      
      expect(result.status).toBe('cancelled')
    })

    it('写 checkpoint', async () => {
      const requirement = createRequirement('REQ-1')
      let tasks = [createTask('t1', 'todo')]
      
      const updateRequirement = vi.fn().mockResolvedValue(undefined)
      
      const executeSubtask = vi.fn().mockImplementation(async () => {
        tasks = [createTask('t1', 'done')]
      })
      
      const controller = new AbortController()
      const ctx: ExecutionContext = {
        requirementId: 'REQ-1',
        runId: 'run-123',
        signal: controller.signal,
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockImplementation(async () => tasks),
        executeSubtask,
        updateRequirement
      }
      
      const result = await runner.runChain(ctx)
      
      expect(result.status).toBe('completed')
      expect(result.lastCheckpoint).toBeDefined()
      expect(result.lastCheckpoint?.runId).toBe('run-123')
      expect(result.lastCheckpoint?.stepIndex).toBe(1)
      expect(updateRequirement).toHaveBeenCalled()
    })

    it('暂停：无 ready 任务但有未完成任务', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [
        createTask('t1', 'todo', ['t-nonexist']) // 依赖不存在，无法执行
      ]
      
      const controller = new AbortController()
      const ctx: ExecutionContext = {
        requirementId: 'REQ-1',
        runId: 'run-123',
        signal: controller.signal,
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        executeSubtask: vi.fn().mockResolvedValue(undefined),
        updateRequirement: vi.fn().mockResolvedValue(undefined)
      }
      
      const result = await runner.runChain(ctx)
      
      expect(result.status).toBe('paused')
      expect(result.totalSteps).toBe(0)
    })

    it('错误处理：返回 failed', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [createTask('t1', 'todo')]
      
      const controller = new AbortController()
      const ctx: ExecutionContext = {
        requirementId: 'REQ-1',
        runId: 'run-123',
        signal: controller.signal,
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        executeSubtask: vi.fn().mockRejectedValue(new Error('Execution failed')),
        updateRequirement: vi.fn().mockResolvedValue(undefined)
      }
      
      const result = await runner.runChain(ctx)
      
      expect(result.status).toBe('failed')
      expect(result.error).toContain('Execution failed')
    })
  })
})
