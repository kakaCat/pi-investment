/**
 * 批调度器测试
 */

import { describe, it, expect } from 'vitest'
import { scheduleBatches, validateBatch } from '../../src/application/internal/batch-scheduler.js'
import type { TaskRecord } from '../../src/client/types.js'

// 创建测试任务
function createTask(id: string, filesPlanned: string[], dependsOn: string[] = []): TaskRecord {
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
    filesPlanned,
    status: 'todo',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  } as TaskRecord
}

describe('batch-scheduler', () => {
  describe('scheduleBatches', () => {
    it('无冲突：全部分到同一批', () => {
      const tasks = [
        createTask('t1', ['src/domain/a.ts']),
        createTask('t2', ['src/adapters/b.ts']),
        createTask('t3', ['src/application/c.ts'])
      ]
      
      const result = scheduleBatches(tasks)
      
      expect(result.batches).toHaveLength(1)
      expect(result.batches[0].taskIds).toHaveLength(3)
      expect(result.totalTasks).toBe(3)
      expect(result.maxBatchSize).toBe(3)
    })

    it('有冲突：分到不同批', () => {
      const tasks = [
        createTask('t1', ['src/domain/a.ts']),
        createTask('t2', ['src/domain/b.ts']), // 同目录，冲突
        createTask('t3', ['src/adapters/c.ts'])
      ]
      
      const result = scheduleBatches(tasks)
      
      // t1 和 t2 冲突，应该分到不同批
      // t3 可能与 t1 或 t2 在同一批
      expect(result.batches.length).toBeGreaterThanOrEqual(2)
      
      // 验证 t1 和 t2 不在同一批
      const t1Batch = result.batches.find(b => b.taskIds.includes('t1'))
      const t2Batch = result.batches.find(b => b.taskIds.includes('t2'))
      expect(t1Batch?.index).not.toBe(t2Batch?.index)
    })

    it('同文件冲突：必须串行', () => {
      const tasks = [
        createTask('t1', ['src/app.ts']),
        createTask('t2', ['src/app.ts']) // 同文件
      ]
      
      const result = scheduleBatches(tasks)
      
      expect(result.batches).toHaveLength(2)
      expect(result.batches[0].taskIds).toEqual(['t1'])
      expect(result.batches[1].taskIds).toEqual(['t2'])
    })

    it('目录前缀冲突', () => {
      const tasks = [
        createTask('t1', ['src/domain/']),
        createTask('t2', ['src/domain/test.ts']) // 前缀冲突
      ]
      
      const result = scheduleBatches(tasks)
      
      expect(result.batches).toHaveLength(2)
    })

    it('混合场景：部分并行、部分串行', () => {
      const tasks = [
        createTask('t1', ['src/domain/a.ts']),
        createTask('t2', ['src/adapters/b.ts']),
        createTask('t3', ['src/domain/c.ts']), // 与 t1 冲突
        createTask('t4', ['src/application/d.ts'])
      ]
      
      const result = scheduleBatches(tasks)
      
      // t1 和 t3 冲突，应该在不同批
      // t2 和 t4 不冲突，可能与 t1 或 t3 在同一批
      expect(result.batches.length).toBeGreaterThanOrEqual(2)
      expect(result.totalTasks).toBe(4)
      
      // 验证所有任务都被调度
      const allTaskIds = result.batches.flatMap(b => b.taskIds)
      expect(allTaskIds).toHaveLength(4)
      expect(allTaskIds).toContain('t1')
      expect(allTaskIds).toContain('t2')
      expect(allTaskIds).toContain('t3')
      expect(allTaskIds).toContain('t4')
    })

    it('空写集：不冲突', () => {
      const tasks = [
        createTask('t1', []),
        createTask('t2', []),
        createTask('t3', [])
      ]
      
      const result = scheduleBatches(tasks)
      
      // 空写集不冲突，全部在同一批
      expect(result.batches).toHaveLength(1)
      expect(result.batches[0].taskIds).toHaveLength(3)
    })

    it('依赖关系：被依赖任务优先', () => {
      const tasks = [
        createTask('t2', ['src/b.ts'], ['t1']), // 依赖 t1
        createTask('t1', ['src/a.ts'])
      ]
      
      const result = scheduleBatches(tasks)
      
      // t1 应该在 t2 之前
      const t1Batch = result.batches.find(b => b.taskIds.includes('t1'))
      const t2Batch = result.batches.find(b => b.taskIds.includes('t2'))
      
      expect(t1Batch!.index).toBeLessThanOrEqual(t2Batch!.index)
    })

    it('空任务列表', () => {
      const result = scheduleBatches([])
      
      expect(result.batches).toHaveLength(0)
      expect(result.totalTasks).toBe(0)
      expect(result.maxBatchSize).toBe(0)
    })

    it('单个任务', () => {
      const tasks = [createTask('t1', ['src/a.ts'])]
      
      const result = scheduleBatches(tasks)
      
      expect(result.batches).toHaveLength(1)
      expect(result.batches[0].taskIds).toEqual(['t1'])
      expect(result.maxBatchSize).toBe(1)
    })

    it('大规模任务：50个任务', () => {
      const tasks = Array.from({ length: 50 }, (_, i) => 
        createTask(`t${i}`, [`src/dir${i}/file.ts`]) // 不同目录
      )
      
      const result = scheduleBatches(tasks)
      
      // 不同目录不冲突，应该全部在同一批
      expect(result.batches).toHaveLength(1)
      expect(result.totalTasks).toBe(50)
      expect(result.maxBatchSize).toBe(50)
    })

    it('批次索引正确', () => {
      const tasks = [
        createTask('t1', ['src/domain/a.ts']),
        createTask('t2', ['src/domain/b.ts']),
        createTask('t3', ['src/domain/c.ts'])
      ]
      
      const result = scheduleBatches(tasks)
      
      // 验证批次索引从0开始连续
      result.batches.forEach((batch, i) => {
        expect(batch.index).toBe(i)
      })
    })
  })

  describe('validateBatch', () => {
    it('有效批次：无冲突', () => {
      const tasks = [
        createTask('t1', ['src/domain/a.ts']),
        createTask('t2', ['src/adapters/b.ts'])
      ]
      
      const taskMap = new Map(tasks.map(t => [t.id, t]))
      const batch = {
        index: 0,
        taskIds: ['t1', 't2'],
        mergedWriteSet: ['src/domain/a.ts', 'src/adapters/b.ts']
      }
      
      expect(validateBatch(batch, taskMap)).toBe(true)
    })

    it('无效批次：有冲突', () => {
      const tasks = [
        createTask('t1', ['src/domain/a.ts']),
        createTask('t2', ['src/domain/b.ts']) // 同目录冲突
      ]
      
      const taskMap = new Map(tasks.map(t => [t.id, t]))
      const batch = {
        index: 0,
        taskIds: ['t1', 't2'],
        mergedWriteSet: ['src/domain/a.ts', 'src/domain/b.ts']
      }
      
      expect(validateBatch(batch, taskMap)).toBe(false)
    })
  })
})
