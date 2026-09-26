/**
 * QueryRunStatus 用例测试
 */

import { describe, it, expect, vi } from 'vitest'
import { queryRunStatus } from '../../src/application/use-cases/QueryRunStatus.js'
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
    status,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  } as TaskRecord
}

describe('QueryRunStatus', () => {
  describe('queryRunStatus', () => {
    it('无运行：返回 not_found 状态', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [createTask('t1', 'todo')]
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        dshJobsAdapter: { getJob: vi.fn() } as any
      })
      
      expect(result.runId).toBeNull()
      expect(result.stepIndex).toBe(0)
      expect(result.jobStatus).toBe('not_found')
      expect(result.autoRun).toBe(false)
      expect(result.nextReady).toEqual(['t1'])
    })

    it('有 checkpoint：返回运行信息', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 5,
        currentSubtaskId: 't-abc'
      })
      const tasks = [createTask('t1', 'todo')]
      
      const mockAdapter = {
        getJob: vi.fn().mockResolvedValue({
          status: 'running'
        })
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.runId).toBe('run-123')
      expect(result.stepIndex).toBe(5)
      expect(result.currentSubtaskId).toBe('t-abc')
      expect(result.jobStatus).toBe('running')
      expect(result.autoRun).toBe(true)
    })

    it('job 状态：running', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 2
      })
      
      const mockAdapter = {
        getJob: vi.fn().mockResolvedValue({
          status: 'running'
        })
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.jobStatus).toBe('running')
      expect(result.autoRun).toBe(true)
    })

    it('job 状态：completed', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 3
      })
      
      const mockAdapter = {
        getJob: vi.fn().mockResolvedValue({
          status: 'completed'
        })
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([createTask('t1', 'done')]),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.jobStatus).toBe('completed')
      expect(result.autoRun).toBe(false)
    })

    it('job 状态：failed', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 1
      })
      
      const mockAdapter = {
        getJob: vi.fn().mockResolvedValue({
          status: 'failed'
        })
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.jobStatus).toBe('failed')
      expect(result.autoRun).toBe(false)
    })

    it('nextReady：返回可执行任务', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [
        createTask('t1', 'done'),
        createTask('t2', 'todo'), // ready
        createTask('t3', 'todo', ['t2']) // 依赖 t2，not ready
      ]
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        dshJobsAdapter: { getJob: vi.fn() } as any
      })
      
      expect(result.nextReady).toEqual(['t2'])
      expect(result.nextReady).not.toContain('t3')
    })

    it('pauseReason：有任务但都不 ready', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 1
      })
      const tasks = [
        createTask('t1', 'todo', ['t-nonexist']) // 依赖不存在
      ]
      
      const mockAdapter = {
        getJob: vi.fn().mockResolvedValue({
          status: 'completed'
        })
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.pauseReason).toBeDefined()
      expect(result.pauseReason).toContain('不 ready')
    })

    it('无 pauseReason：全部完成', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 5
      })
      const tasks = [createTask('t1', 'done')]
      
      const mockAdapter = {
        getJob: vi.fn().mockResolvedValue({
          status: 'completed'
        })
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.pauseReason).toBeUndefined()
    })

    it('job 不存在：返回 not_found', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 2
      })
      
      const mockAdapter = {
        getJob: vi.fn().mockResolvedValue(null)
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.jobStatus).toBe('not_found')
    })

    it('job 查询失败：返回 not_found', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 2
      })
      
      const mockAdapter = {
        getJob: vi.fn().mockRejectedValue(new Error('Job query failed'))
      }
      
      const result = await queryRunStatus({
        requirementId: 'REQ-1',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.jobStatus).toBe('not_found')
    })
  })
})
