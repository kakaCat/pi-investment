/**
 * 仓储层扩展测试
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { InMemoryRequirementRepository } from '../../src/repositories/RequirementRepository.js'
import { InMemoryTaskRepository } from '../../src/repositories/TaskRepository.js'
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
function createTask(id: string, reqId: string, status: 'todo' | 'in_progress' | 'done', startedAt?: number): TaskRecord {
  const task: any = {
    id,
    requirementId: reqId,
    title: `Task ${id}`,
    description: 'Test task',
    phase: 'implement',
    side: 'backend',
    dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: 'Test',
    context: '',
    status,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  }
  
  if (status === 'in_progress' && startedAt) {
    task.executions = [{
      trigger: 'auto',
      startedAt,
      outcome: 'running'
    }]
  }
  
  return task as TaskRecord
}

describe('RequirementRepository', () => {
  let repo: InMemoryRequirementRepository
  
  beforeEach(() => {
    repo = new InMemoryRequirementRepository()
  })
  
  describe('updateRunState', () => {
    it('更新运行状态', async () => {
      const req = createRequirement('REQ-1')
      repo.seed(req)
      
      await repo.updateRunState('REQ-1', {
        runId: 'run-123',
        stepIndex: 5,
        currentSubtaskId: 't-abc',
        heartbeatAt: Date.now()
      })
      
      const updated = await repo.getRequirement('REQ-1')
      expect(updated?.advance?.runId).toBe('run-123')
      expect(updated?.advance?.stepIndex).toBe(5)
      expect(updated?.advance?.currentSubtaskId).toBe('t-abc')
    })
    
    it('需求不存在：抛出错误', async () => {
      await expect(repo.updateRunState('REQ-nonexist', {
        runId: 'run-123'
      })).rejects.toThrow('not found')
    })
  })
  
  describe('readCheckpoint', () => {
    it('读取存在的 checkpoint', async () => {
      const req = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 5,
        currentSubtaskId: 't-abc',
        heartbeatAt: 12345
      })
      repo.seed(req)
      
      const checkpoint = await repo.readCheckpoint('REQ-1')
      
      expect(checkpoint).not.toBeNull()
      expect(checkpoint?.runId).toBe('run-123')
      expect(checkpoint?.stepIndex).toBe(5)
      expect(checkpoint?.currentSubtaskId).toBe('t-abc')
      expect(checkpoint?.heartbeatAt).toBe(12345)
    })
    
    it('无 checkpoint：返回 null', async () => {
      const req = createRequirement('REQ-1')
      repo.seed(req)
      
      const checkpoint = await repo.readCheckpoint('REQ-1')
      
      expect(checkpoint).toBeNull()
    })
    
    it('需求不存在：返回 null', async () => {
      const checkpoint = await repo.readCheckpoint('REQ-nonexist')
      
      expect(checkpoint).toBeNull()
    })
  })
  
  describe('clearCheckpoint', () => {
    it('清理 checkpoint 字段', async () => {
      const req = createRequirement('REQ-1', {
        lockAt: 12345,
        runId: 'run-123',
        stepIndex: 5,
        currentSubtaskId: 't-abc',
        heartbeatAt: 67890
      })
      repo.seed(req)
      
      await repo.clearCheckpoint('REQ-1')
      
      const updated = await repo.getRequirement('REQ-1')
      expect(updated?.advance?.runId).toBeUndefined()
      expect(updated?.advance?.stepIndex).toBeUndefined()
      expect(updated?.advance?.currentSubtaskId).toBeUndefined()
      expect(updated?.advance?.heartbeatAt).toBeUndefined()
      expect(updated?.advance?.lockAt).toBe(12345) // 保留其他字段
    })
    
    it('需求不存在：不抛出错误', async () => {
      await expect(repo.clearCheckpoint('REQ-nonexist')).resolves.not.toThrow()
    })
  })
})

describe('TaskRepository', () => {
  let repo: InMemoryTaskRepository
  
  beforeEach(() => {
    repo = new InMemoryTaskRepository()
  })
  
  describe('getTasksByRequirement', () => {
    it('返回需求下的所有任务', async () => {
      repo.seed(createTask('t1', 'REQ-1', 'todo'))
      repo.seed(createTask('t2', 'REQ-1', 'done'))
      repo.seed(createTask('t3', 'REQ-2', 'todo'))
      
      const tasks = await repo.getTasksByRequirement('REQ-1')
      
      expect(tasks).toHaveLength(2)
      expect(tasks.map(t => t.id)).toContain('t1')
      expect(tasks.map(t => t.id)).toContain('t2')
      expect(tasks.map(t => t.id)).not.toContain('t3')
    })
    
    it('无任务：返回空数组', async () => {
      const tasks = await repo.getTasksByRequirement('REQ-nonexist')
      
      expect(tasks).toHaveLength(0)
    })
  })
  
  describe('getOrphans', () => {
    it('返回超时的 in_progress 任务', async () => {
      const now = Date.now()
      repo.seed(createTask('t1', 'REQ-1', 'in_progress', now - 5 * 60 * 1000)) // 5分钟前
      repo.seed(createTask('t2', 'REQ-1', 'in_progress', now - 1000)) // 1秒前
      repo.seed(createTask('t3', 'REQ-1', 'todo'))
      
      const orphans = await repo.getOrphans('REQ-1')
      
      expect(orphans).toHaveLength(1)
      expect(orphans[0].id).toBe('t1')
    })
    
    it('无执行记录的 in_progress：是孤儿', async () => {
      const task = createTask('t1', 'REQ-1', 'in_progress')
      delete (task as any).executions
      repo.seed(task)
      
      const orphans = await repo.getOrphans('REQ-1')
      
      expect(orphans).toHaveLength(1)
      expect(orphans[0].id).toBe('t1')
    })
    
    it('todo 状态：不是孤儿', async () => {
      repo.seed(createTask('t1', 'REQ-1', 'todo'))
      
      const orphans = await repo.getOrphans('REQ-1')
      
      expect(orphans).toHaveLength(0)
    })
  })
  
  describe('updateHeartbeat', () => {
    it('更新心跳时间', async () => {
      const now = Date.now()
      const task = createTask('t1', 'REQ-1', 'in_progress', now - 10000)
      repo.seed(task)
      
      const newTimestamp = now + 5000
      await repo.updateHeartbeat('t1', newTimestamp)
      
      const updated = await repo.getTask('t1')
      const executions = (updated as any)?.executions || []
      expect(executions[0]?.startedAt).toBe(newTimestamp)
    })
    
    it('任务不存在：抛出错误', async () => {
      await expect(repo.updateHeartbeat('t-nonexist', Date.now()))
        .rejects.toThrow('not found')
    })
  })
})
