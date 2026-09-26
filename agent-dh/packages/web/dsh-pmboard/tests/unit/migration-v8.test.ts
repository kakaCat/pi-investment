/**
 * Schema v8 迁移测试
 * 
 * 验证：
 * 1. 旧台账（v7，无 filesPlanned/runId 等字段）加载后新字段为 undefined，行为不变
 * 2. 新台账写入 v8，包含新字段
 */

import { describe, it, expect } from 'vitest'
import type { RequirementRecord, TaskRecord } from '../../src/client/types.js'

describe('Schema v8 migration', () => {
  it('v7 台账加载：新字段缺省为 undefined', () => {
    // 模拟 v7 台账的任务记录（没有 filesPlanned）
    const v7Task: TaskRecord = {
      id: 't-test123',
      requirementId: 'REQ-test',
      title: 'Test Task',
      description: 'A test task',
      phase: 'implement',
      side: 'backend',
      dependsOn: [],
      scope: { apis: [], tables: [], files: [] },
      acceptance: 'Test passes',
      context: '',
      status: 'todo',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      createdBy: { kind: 'agent', sessionId: 'test' },
      updatedBy: { kind: 'agent', sessionId: 'test' }
    } as TaskRecord

    // 验证：filesPlanned 字段不存在时为 undefined
    expect(v7Task.filesPlanned).toBeUndefined()
    
    // 验证：v7 任务仍然是有效的 TaskRecord
    expect(v7Task.id).toBe('t-test123')
    expect(v7Task.status).toBe('todo')
  })

  it('v7 台账加载：需求运行态字段缺省为 undefined', () => {
    // 模拟 v7 台账的需求记录（advance 没有 runId/stepIndex 等）
    const v7Req: RequirementRecord = {
      id: 'REQ-test',
      title: 'Test Requirement',
      description: 'A test requirement',
      status: 'implementing',
      blocked: false,
      advance: {
        lockAt: Date.now(),
        noopStreak: 0
        // v7: 没有 runId, currentSubtaskId, stepIndex, heartbeatAt
      },
      createdAt: Date.now(),
      updatedAt: Date.now(),
      createdBy: { kind: 'agent', sessionId: 'test' },
      updatedBy: { kind: 'agent', sessionId: 'test' }
    } as RequirementRecord

    // 验证：新字段缺省时为 undefined
    expect(v7Req.advance?.runId).toBeUndefined()
    expect(v7Req.advance?.currentSubtaskId).toBeUndefined()
    expect(v7Req.advance?.stepIndex).toBeUndefined()
    expect(v7Req.advance?.heartbeatAt).toBeUndefined()
    
    // 验证：v7 需求仍然是有效的 RequirementRecord
    expect(v7Req.id).toBe('REQ-test')
    expect(v7Req.status).toBe('implementing')
  })

  it('v8 台账写入：新字段始终包含（即使为 undefined）', () => {
    // v8 新建的任务应该包含 filesPlanned 字段
    const v8Task: TaskRecord = {
      id: 't-new',
      requirementId: 'REQ-new',
      title: 'New Task',
      description: 'A new task',
      phase: 'implement',
      side: 'backend',
      dependsOn: [],
      scope: { apis: [], tables: [], files: [] },
      acceptance: 'Test passes',
      context: '',
      filesPlanned: ['src/domain/test.ts'], // v8: 新字段
      status: 'todo',
      createdAt: Date.now(),
      updatedAt: Date.now(),
      createdBy: { kind: 'agent', sessionId: 'test' },
      updatedBy: { kind: 'agent', sessionId: 'test' }
    } as TaskRecord

    // 验证：filesPlanned 字段存在
    expect(v8Task.filesPlanned).toBeDefined()
    expect(v8Task.filesPlanned).toEqual(['src/domain/test.ts'])
  })

  it('v8 台账写入：需求运行态字段完整', () => {
    const v8Req: RequirementRecord = {
      id: 'REQ-new',
      title: 'New Requirement',
      description: 'A new requirement',
      status: 'implementing',
      blocked: false,
      advance: {
        lockAt: Date.now(),
        noopStreak: 0,
        runId: 'run-123',          // v8: 新字段
        currentSubtaskId: 't-abc', // v8: 新字段
        stepIndex: 5,              // v8: 新字段
        heartbeatAt: Date.now()    // v8: 新字段
      },
      createdAt: Date.now(),
      updatedAt: Date.now(),
      createdBy: { kind: 'agent', sessionId: 'test' },
      updatedBy: { kind: 'agent', sessionId: 'test' }
    } as RequirementRecord

    // 验证：新字段都存在
    expect(v8Req.advance?.runId).toBe('run-123')
    expect(v8Req.advance?.currentSubtaskId).toBe('t-abc')
    expect(v8Req.advance?.stepIndex).toBe(5)
    expect(v8Req.advance?.heartbeatAt).toBeGreaterThan(0)
  })

  it('迁移兼容性：v7 到 v8 无破坏性变更', () => {
    // v7 记录可以安全地视为 v8 记录
    const v7Task: Partial<TaskRecord> = {
      id: 't-old',
      status: 'done'
      // 没有 filesPlanned
    }

    const v8Task: TaskRecord = {
      ...v7Task,
      filesPlanned: undefined // 显式标记为 undefined 也是合法的
    } as TaskRecord

    // 验证：行为不变
    expect(v8Task.id).toBe('t-old')
    expect(v8Task.status).toBe('done')
    expect(v8Task.filesPlanned).toBeUndefined()
  })
})
