/**
 * Checkpoint 管理器测试
 */

import { describe, it, expect } from 'vitest'
import { CheckpointManager } from '../../src/application/internal/checkpoint-manager.js'
import type { RequirementRecord } from '../../src/client/types.js'
import type { Checkpoint } from '../../src/domain/checkpoint.js'

// 创建测试需求
function createRequirement(id: string, advance?: any): RequirementRecord {
  return {
    id,
    title: `Requirement ${id}`,
    description: 'Test requirement',
    status: 'implementing',
    blocked: false,
    advance,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    createdBy: { kind: 'agent', sessionId: 'test' },
    updatedBy: { kind: 'agent', sessionId: 'test' }
  } as RequirementRecord
}

describe('CheckpointManager', () => {
  const manager = new CheckpointManager()

  describe('writeCheckpoint', () => {
    it('写入新 checkpoint', () => {
      const req = createRequirement('REQ-1')
      const checkpoint: Checkpoint = {
        runId: 'run-123',
        currentSubtaskId: 't-abc',
        stepIndex: 5,
        heartbeatAt: Date.now()
      }
      
      const updated = manager.writeCheckpoint(req, checkpoint)
      
      expect(updated.advance?.runId).toBe('run-123')
      expect(updated.advance?.currentSubtaskId).toBe('t-abc')
      expect(updated.advance?.stepIndex).toBe(5)
      expect(updated.advance?.heartbeatAt).toBe(checkpoint.heartbeatAt)
    })

    it('覆盖已有 checkpoint', () => {
      const req = createRequirement('REQ-1', {
        lockAt: 12345,
        runId: 'run-old',
        currentSubtaskId: 't-old',
        stepIndex: 1
      })
      
      const checkpoint: Checkpoint = {
        runId: 'run-new',
        currentSubtaskId: 't-new',
        stepIndex: 10,
        heartbeatAt: Date.now()
      }
      
      const updated = manager.writeCheckpoint(req, checkpoint)
      
      expect(updated.advance?.runId).toBe('run-new')
      expect(updated.advance?.currentSubtaskId).toBe('t-new')
      expect(updated.advance?.stepIndex).toBe(10)
      expect(updated.advance?.lockAt).toBe(12345) // 保留其他字段
    })

    it('不修改原对象', () => {
      const req = createRequirement('REQ-1')
      const checkpoint: Checkpoint = {
        runId: 'run-123'
      }
      
      const updated = manager.writeCheckpoint(req, checkpoint)
      
      expect(updated).not.toBe(req)
      expect(req.advance).toBeUndefined()
      expect(updated.advance?.runId).toBe('run-123')
    })
  })

  describe('readCheckpoint', () => {
    it('读取存在的 checkpoint', () => {
      const req = createRequirement('REQ-1', {
        runId: 'run-123',
        currentSubtaskId: 't-abc',
        stepIndex: 5,
        heartbeatAt: 12345
      })
      
      const checkpoint = manager.readCheckpoint(req)
      
      expect(checkpoint).not.toBeNull()
      expect(checkpoint?.runId).toBe('run-123')
      expect(checkpoint?.currentSubtaskId).toBe('t-abc')
      expect(checkpoint?.stepIndex).toBe(5)
      expect(checkpoint?.heartbeatAt).toBe(12345)
    })

    it('无 advance：返回 null', () => {
      const req = createRequirement('REQ-1')
      
      const checkpoint = manager.readCheckpoint(req)
      
      expect(checkpoint).toBeNull()
    })

    it('无 runId：返回 null', () => {
      const req = createRequirement('REQ-1', {
        lockAt: 12345
      })
      
      const checkpoint = manager.readCheckpoint(req)
      
      expect(checkpoint).toBeNull()
    })
  })

  describe('clearCheckpoint', () => {
    it('清理 checkpoint 字段', () => {
      const req = createRequirement('REQ-1', {
        lockAt: 12345,
        noopStreak: 0,
        runId: 'run-123',
        currentSubtaskId: 't-abc',
        stepIndex: 5,
        heartbeatAt: 67890
      })
      
      const updated = manager.clearCheckpoint(req)
      
      expect(updated.advance?.runId).toBeUndefined()
      expect(updated.advance?.currentSubtaskId).toBeUndefined()
      expect(updated.advance?.stepIndex).toBeUndefined()
      expect(updated.advance?.heartbeatAt).toBeUndefined()
      // 保留其他字段
      expect(updated.advance?.lockAt).toBe(12345)
      expect(updated.advance?.noopStreak).toBe(0)
    })

    it('无 advance：返回原对象', () => {
      const req = createRequirement('REQ-1')
      
      const updated = manager.clearCheckpoint(req)
      
      expect(updated).toBe(req)
    })

    it('清理后读取返回 null', () => {
      const req = createRequirement('REQ-1', {
        runId: 'run-123',
        stepIndex: 5
      })
      
      const cleared = manager.clearCheckpoint(req)
      const checkpoint = manager.readCheckpoint(cleared)
      
      expect(checkpoint).toBeNull()
    })
  })

  describe('updateHeartbeat', () => {
    it('更新心跳时间', () => {
      const now = Date.now()
      const req = createRequirement('REQ-1', {
        runId: 'run-123',
        heartbeatAt: now - 10000
      })
      
      const updated = manager.updateHeartbeat(req)
      
      expect(updated.advance?.heartbeatAt).toBeGreaterThan(now - 10000)
      expect(updated.advance?.heartbeatAt).toBeGreaterThanOrEqual(now)
    })

    it('无 checkpoint：不更新', () => {
      const req = createRequirement('REQ-1')
      
      const updated = manager.updateHeartbeat(req)
      
      expect(updated).toBe(req)
    })

    it('无 runId：不更新', () => {
      const req = createRequirement('REQ-1', {
        lockAt: 12345
      })
      
      const updated = manager.updateHeartbeat(req)
      
      expect(updated).toBe(req)
    })
  })

  describe('hasCheckpoint', () => {
    it('有 checkpoint：true', () => {
      const req = createRequirement('REQ-1', {
        runId: 'run-123'
      })
      
      expect(manager.hasCheckpoint(req)).toBe(true)
    })

    it('无 advance：false', () => {
      const req = createRequirement('REQ-1')
      
      expect(manager.hasCheckpoint(req)).toBe(false)
    })

    it('无 runId：false', () => {
      const req = createRequirement('REQ-1', {
        lockAt: 12345
      })
      
      expect(manager.hasCheckpoint(req)).toBe(false)
    })
  })

  describe('getHeartbeatAge', () => {
    it('计算心跳年龄', () => {
      const now = Date.now()
      const req = createRequirement('REQ-1', {
        heartbeatAt: now - 5000
      })
      
      const age = manager.getHeartbeatAge(req)
      
      expect(age).not.toBeNull()
      expect(age!).toBeGreaterThanOrEqual(5000)
      expect(age!).toBeLessThan(6000)
    })

    it('无 advance：返回 null', () => {
      const req = createRequirement('REQ-1')
      
      const age = manager.getHeartbeatAge(req)
      
      expect(age).toBeNull()
    })

    it('无 heartbeatAt：返回 null', () => {
      const req = createRequirement('REQ-1', {
        runId: 'run-123'
      })
      
      const age = manager.getHeartbeatAge(req)
      
      expect(age).toBeNull()
    })
  })

  describe('并发场景', () => {
    it('并发写入：最后一次生效', () => {
      const req = createRequirement('REQ-1')
      
      const checkpoint1: Checkpoint = { runId: 'run-1', stepIndex: 1 }
      const checkpoint2: Checkpoint = { runId: 'run-2', stepIndex: 2 }
      
      const updated1 = manager.writeCheckpoint(req, checkpoint1)
      const updated2 = manager.writeCheckpoint(req, checkpoint2)
      
      expect(manager.readCheckpoint(updated1)?.runId).toBe('run-1')
      expect(manager.readCheckpoint(updated2)?.runId).toBe('run-2')
    })

    it('写入-读取-清理 完整流程', () => {
      const req = createRequirement('REQ-1')
      const checkpoint: Checkpoint = {
        runId: 'run-123',
        currentSubtaskId: 't-abc',
        stepIndex: 5,
        heartbeatAt: Date.now()
      }
      
      // 写入
      const written = manager.writeCheckpoint(req, checkpoint)
      expect(manager.hasCheckpoint(written)).toBe(true)
      
      // 读取
      const read = manager.readCheckpoint(written)
      expect(read?.runId).toBe('run-123')
      
      // 清理
      const cleared = manager.clearCheckpoint(written)
      expect(manager.hasCheckpoint(cleared)).toBe(false)
      expect(manager.readCheckpoint(cleared)).toBeNull()
    })
  })
})
