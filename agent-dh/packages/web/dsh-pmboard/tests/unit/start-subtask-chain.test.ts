/**
 * StartSubtaskChain 用例测试
 */

import { describe, it, expect, vi } from 'vitest'
import { startSubtaskChain } from '../../src/application/use-cases/StartSubtaskChain.js'
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
function createTask(id: string): TaskRecord {
  return {
    id,
    requirementId: 'REQ-test',
    title: `Task ${id}`,
    description: 'Test task',
    phase: 'implement',
    side: 'backend',
    dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: 'Test',
    context: '',
    status: 'todo',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  } as TaskRecord
}

describe('StartSubtaskChain', () => {
  describe('startSubtaskChain', () => {
    it('首次投递：返回 dispatched 状态', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [createTask('t1')]
      
      let updatedReq: RequirementRecord | null = null
      
      const mockAdapter = {
        startJob: vi.fn().mockResolvedValue('job-123')
      }
      
      const result = await startSubtaskChain({
        parentTaskId: 't-parent',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        executeSubtask: vi.fn().mockResolvedValue(undefined),
        updateRequirement: vi.fn().mockImplementation(async (req) => {
          updatedReq = req
        }),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.status).toBe('dispatched')
      expect(result.runId).toBeDefined()
      expect(result.jobId).toBe('job-123')
      
      // 验证认领
      expect(updatedReq).not.toBeNull()
      expect(updatedReq?.advance?.lockAt).toBeDefined()
      expect(updatedReq?.advance?.runId).toBe(result.runId)
      
      // 验证注册后台任务
      expect(mockAdapter.startJob).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: 'reqboard',
          label: expect.stringContaining('t-parent')
        })
      )
    })

    it('幂等：已有 runId 时返回 already_running', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-existing',
        lockAt: Date.now()
      })
      
      const mockAdapter = {
        startJob: vi.fn()
      }
      
      const result = await startSubtaskChain({
        parentTaskId: 't-parent',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        executeSubtask: vi.fn(),
        updateRequirement: vi.fn(),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.status).toBe('already_running')
      expect(result.runId).toBe('run-existing')
      
      // 不应该注册新任务
      expect(mockAdapter.startJob).not.toHaveBeenCalled()
    })

    it('认领与注册原子完成', async () => {
      const requirement = createRequirement('REQ-1')
      const tasks = [createTask('t1')]
      
      const updateCalls: RequirementRecord[] = []
      const startJobCalls: any[] = []
      
      const mockAdapter = {
        startJob: vi.fn().mockImplementation(async (opts) => {
          startJobCalls.push(opts)
          return 'job-123'
        })
      }
      
      await startSubtaskChain({
        parentTaskId: 't-parent',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue(tasks),
        executeSubtask: vi.fn().mockResolvedValue(undefined),
        updateRequirement: vi.fn().mockImplementation(async (req) => {
          updateCalls.push(req)
        }),
        dshJobsAdapter: mockAdapter as any
      })
      
      // 验证认领在注册之前
      expect(updateCalls).toHaveLength(1)
      expect(startJobCalls).toHaveLength(1)
      
      // 认领的 runId 应该与注册时一致
      const claimedRunId = updateCalls[0].advance?.runId
      expect(claimedRunId).toBeDefined()
    })

    it('重复调用幂等：返回相同的 runId', async () => {
      const requirement = createRequirement('REQ-1', {
        runId: 'run-123',
        lockAt: Date.now()
      })
      
      const result1 = await startSubtaskChain({
        parentTaskId: 't-parent',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        executeSubtask: vi.fn(),
        updateRequirement: vi.fn(),
        dshJobsAdapter: { startJob: vi.fn() } as any
      })
      
      const result2 = await startSubtaskChain({
        parentTaskId: 't-parent',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        executeSubtask: vi.fn(),
        updateRequirement: vi.fn(),
        dshJobsAdapter: { startJob: vi.fn() } as any
      })
      
      expect(result1.runId).toBe(result2.runId)
      expect(result1.status).toBe('already_running')
      expect(result2.status).toBe('already_running')
    })

    it('返回包含 jobId', async () => {
      const requirement = createRequirement('REQ-1')
      
      const mockAdapter = {
        startJob: vi.fn().mockResolvedValue('job-abc-123')
      }
      
      const result = await startSubtaskChain({
        parentTaskId: 't-parent',
        getRequirement: vi.fn().mockResolvedValue(requirement),
        getTasks: vi.fn().mockResolvedValue([]),
        executeSubtask: vi.fn(),
        updateRequirement: vi.fn(),
        dshJobsAdapter: mockAdapter as any
      })
      
      expect(result.jobId).toBe('job-abc-123')
      expect(result.status).toBe('dispatched')
    })

    it('生成唯一的 runId', async () => {
      const requirement = createRequirement('REQ-1')
      
      const runIds: string[] = []
      
      for (let i = 0; i < 5; i++) {
        const result = await startSubtaskChain({
          parentTaskId: 't-parent',
          getRequirement: vi.fn().mockResolvedValue(requirement),
          getTasks: vi.fn().mockResolvedValue([]),
          executeSubtask: vi.fn(),
          updateRequirement: vi.fn(),
          dshJobsAdapter: { startJob: vi.fn().mockResolvedValue('job-123') } as any
        })
        
        runIds.push(result.runId)
      }
      
      // 所有 runId 应该不同
      const uniqueRunIds = new Set(runIds)
      expect(uniqueRunIds.size).toBe(5)
    })
  })
})
