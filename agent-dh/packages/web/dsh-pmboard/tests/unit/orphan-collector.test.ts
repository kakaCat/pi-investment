/**
 * 孤儿回收器测试
 */

import { describe, it, expect } from 'vitest'
import { identifyOrphans, isOrphan, calculateRetryAttempt } from '../../src/application/internal/orphan-collector.js'
import type { TaskRecord } from '../../src/client/types.js'
import { LIMITS } from '../../src/domain/limits.js'

// 创建测试任务
function createTask(
  id: string,
  status: 'todo' | 'in_progress' | 'done',
  startedAt?: number,
  attempt: number = 0
): TaskRecord {
  const task: any = {
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
    status,
    attempt,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  }
  
  // 添加执行记录
  if (status === 'in_progress' && startedAt) {
    task.executions = [{
      trigger: 'auto',
      startedAt,
      outcome: 'running'
    }]
  }
  
  return task as TaskRecord
}

describe('orphan-collector', () => {
  describe('identifyOrphans', () => {
    it('正常运行的任务：不是孤儿', () => {
      const now = Date.now()
      const tasks = [
        createTask('t1', 'in_progress', now - 1000) // 1秒前启动
      ]
      
      const result = identifyOrphans(tasks, new Set())
      
      expect(result.orphanIds).toHaveLength(0)
      expect(result.thresholdMs).toBe(LIMITS.orphanTimeoutMs)
    })

    it('超时任务：是孤儿', () => {
      const now = Date.now()
      const tasks = [
        createTask('t1', 'in_progress', now - 4 * 60 * 1000) // 4分钟前启动
      ]
      
      const result = identifyOrphans(tasks, new Set())
      
      expect(result.orphanIds).toContain('t1')
      expect(result.orphanIds).toHaveLength(1)
    })

    it('刚好超时边界：3分钟', () => {
      const now = Date.now()
      const threshold = 3 * 60 * 1000
      const tasks = [
        createTask('t1', 'in_progress', now - threshold - 1000), // 超时
        createTask('t2', 'in_progress', now - threshold + 1000)  // 未超时
      ]
      
      const result = identifyOrphans(tasks, new Set(), threshold)
      
      expect(result.orphanIds).toContain('t1')
      expect(result.orphanIds).not.toContain('t2')
    })

    it('todo 状态：不检查', () => {
      const now = Date.now()
      const tasks = [
        createTask('t1', 'todo', now - 10 * 60 * 1000) // 很久以前，但是 todo
      ]
      
      const result = identifyOrphans(tasks, new Set())
      
      expect(result.orphanIds).toHaveLength(0)
    })

    it('done 状态：不检查', () => {
      const now = Date.now()
      const tasks = [
        createTask('t1', 'done', now - 10 * 60 * 1000)
      ]
      
      const result = identifyOrphans(tasks, new Set())
      
      expect(result.orphanIds).toHaveLength(0)
    })

    it('无执行记录的 in_progress：视为孤儿', () => {
      const task: any = createTask('t1', 'in_progress')
      delete task.executions // 无执行记录
      
      const result = identifyOrphans([task], new Set())
      
      expect(result.orphanIds).toContain('t1')
    })

    it('混合场景：部分孤儿', () => {
      const now = Date.now()
      const tasks = [
        createTask('t1', 'in_progress', now - 5 * 60 * 1000), // 孤儿
        createTask('t2', 'in_progress', now - 1000),           // 正常
        createTask('t3', 'todo'),                              // 不检查
        createTask('t4', 'in_progress', now - 10 * 60 * 1000) // 孤儿
      ]
      
      const result = identifyOrphans(tasks, new Set())
      
      expect(result.orphanIds).toHaveLength(2)
      expect(result.orphanIds).toContain('t1')
      expect(result.orphanIds).toContain('t4')
      expect(result.orphanIds).not.toContain('t2')
      expect(result.orphanIds).not.toContain('t3')
    })

    it('空任务列表', () => {
      const result = identifyOrphans([], new Set())
      
      expect(result.orphanIds).toHaveLength(0)
    })

    it('自定义超时阈值', () => {
      const now = Date.now()
      const customThreshold = 5 * 60 * 1000 // 5分钟
      const tasks = [
        createTask('t1', 'in_progress', now - 4 * 60 * 1000) // 4分钟前
      ]
      
      const result = identifyOrphans(tasks, new Set(), customThreshold)
      
      // 4分钟 < 5分钟，不是孤儿
      expect(result.orphanIds).toHaveLength(0)
      expect(result.thresholdMs).toBe(customThreshold)
    })
  })

  describe('isOrphan', () => {
    it('正常任务：false', () => {
      const now = Date.now()
      const task = createTask('t1', 'in_progress', now - 1000)
      
      expect(isOrphan(task, new Set())).toBe(false)
    })

    it('超时任务：true', () => {
      const now = Date.now()
      const task = createTask('t1', 'in_progress', now - 5 * 60 * 1000)
      
      expect(isOrphan(task, new Set())).toBe(true)
    })

    it('todo 状态：false', () => {
      const task = createTask('t1', 'todo')
      
      expect(isOrphan(task, new Set())).toBe(false)
    })

    it('无执行记录：true', () => {
      const task: any = createTask('t1', 'in_progress')
      delete task.executions
      
      expect(isOrphan(task, new Set())).toBe(true)
    })
  })

  describe('calculateRetryAttempt', () => {
    it('首次失败：attempt = 1', () => {
      const task = createTask('t1', 'todo', undefined, 0)
      
      expect(calculateRetryAttempt(task)).toBe(1)
    })

    it('第二次失败：attempt = 2', () => {
      const task = createTask('t1', 'todo', undefined, 1)
      
      expect(calculateRetryAttempt(task)).toBe(2)
    })

    it('多次失败：递增', () => {
      const task1 = createTask('t1', 'todo', undefined, 0)
      const task2 = createTask('t2', 'todo', undefined, 5)
      
      expect(calculateRetryAttempt(task1)).toBe(1)
      expect(calculateRetryAttempt(task2)).toBe(6)
    })
  })
})
