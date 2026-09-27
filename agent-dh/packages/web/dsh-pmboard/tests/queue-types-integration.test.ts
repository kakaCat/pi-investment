/**
 * 队列类型联调测试（REQ-260927202051-f6df · t-b34b32 / integrate / FR-1）。
 *
 * t1 只证明了「类型定义本身自洽」；本文件证明的是**接口联调**——
 * 队列任务能不能真正接到既有的读方接口上，而不是纸面同构。
 *
 * 联调对象（既有真实接口，非本卡自造的 mock）：
 * - `readyTasks(tasks: readonly TaskRecord[], requirementId)`  ← src/shared/protocol.ts:1393
 * - `assertDagAcyclic(tasks, requirementId)`                   ← src/shared/protocol.ts:1360
 *
 * 验收口径「给出请求样例与期望响应，实际返回与预期一致」在本文件中的落法：
 * - 请求样例 = buildQueueFile() 产出的 QueueFile（3 任务链 a→b→c）
 * - 期望响应 = 读方返回 ready=['t-aa0001']、DAG 校验不抛错、JSON 往返无损
 * - 实际返回 = vitest 断言结果（见 evidence）
 */

import { describe, expect, it } from 'vitest'
import { QUEUE_VERSION } from '../src/domain/queue/QueueTypes.js'
import type { QueueFile, QueueTask } from '../src/domain/queue/QueueTypes.js'
import { assertDagAcyclic, readyTasks } from '../src/shared/protocol.js'
import type { TaskRecord, TaskStatus } from '../src/shared/protocol.js'

const REQ = 'REQ-260927202051-f6df'

/** 构造一条字段齐全的 TaskRecord；可选字段刻意全部带值，用于验证跨界不丢字段。 */
function task(id: string, status: TaskStatus, dependsOn: string[]): TaskRecord {
  const actor = { kind: 'agent' as const, sessionId: 'session-integration' }
  return {
    id,
    requirementId: REQ,
    title: `联调样本 ${id}`,
    description: '队列类型联调样本',
    phase: 'implement',
    side: 'backend',
    dependsOn,
    scope: { apis: [], tables: [], files: [] },
    acceptance: '可执行验收',
    implementation: '改哪个文件、怎么验证',
    context: '需求背景',
    dependsSummary: '上游产出摘要',
    requirementRefs: ['FR-1'],
    skipIntegration: false,
    attempt: 2,
    status,
    blocked: false,
    blockedReason: undefined,
    claimedBy: 'w-integration',
    claimedAt: 1759000000000,
    executions: [],
    statusHistory: [],
    comments: [],
    version: 3,
    createdAt: 1759000000000,
    updatedAt: 1759000001000,
    createdBy: actor,
    updatedBy: actor,
  }
}

/**
 * 请求样例：a(done) → b(todo) → c(todo) 的三级链。
 * layer 按 x 无依赖=0 / 依赖方 layer+1 派生；ready 期望只有 b（a 已 done，c 依赖 b 未完成）。
 */
function buildQueueFile(): QueueFile {
  const tasks: QueueTask[] = [
    { ...task('t-aa0001', 'done', []), layer: 0 },
    { ...task('t-aa0002', 'todo', ['t-aa0001']), layer: 1 },
    { ...task('t-aa0003', 'todo', ['t-aa0002']), layer: 2 },
  ]
  return {
    version: QUEUE_VERSION,
    requirement_id: REQ,
    schemaVersion: 9,
    generated_at: '2026-09-27T23:30:00.000Z',
    tasks,
    edges: [
      { from: 't-aa0001', to: 't-aa0002' },
      { from: 't-aa0002', to: 't-aa0003' },
    ],
    layers: [
      { layer: 0, tasks: ['t-aa0001'] },
      { layer: 1, tasks: ['t-aa0002'] },
      { layer: 2, tasks: ['t-aa0003'] },
    ],
    ready: ['t-aa0002'],
  }
}

describe('QueueTypes 接口联调（t-b34b32）', () => {
  it('QueueTask[] 可直接喂给既有读方 readyTasks（只换数据源，不改读方签名）', () => {
    const file = buildQueueFile()

    // 编译期联调：QueueTask[] 必须可赋给 readonly TaskRecord[]（读方签名不变）
    const asRecords: readonly TaskRecord[] = file.tasks

    // 实际返回 vs 期望
    expect(readyTasks(asRecords, REQ).map((t) => t.id)).toEqual(['t-aa0002'])
  })

  it('QueueTask[] 可直接喂给既有 DAG 校验 assertDagAcyclic', () => {
    const file = buildQueueFile()
    expect(() => assertDagAcyclic(file.tasks, REQ)).not.toThrow()
  })

  it('QueueFile 过 JSON 序列化边界无损（含全部可选字段与派生视图）', () => {
    const file = buildQueueFile()
    const wire = JSON.stringify(file, null, 2)
    const parsed = JSON.parse(wire) as QueueFile

    expect(parsed).toEqual(file)
    // 逐项确认关键字段没在边界上被丢弃
    expect(parsed.tasks).toHaveLength(3)
    expect(parsed.tasks[1]!.implementation).toBe('改哪个文件、怎么验证')
    expect(parsed.tasks[1]!.dependsSummary).toBe('上游产出摘要')
    expect(parsed.tasks[1]!.requirementRefs).toEqual(['FR-1'])
    expect(parsed.tasks[1]!.attempt).toBe(2)
    expect(parsed.tasks[2]!.layer).toBe(2)
    expect(parsed.edges).toEqual([
      { from: 't-aa0001', to: 't-aa0002' },
      { from: 't-aa0002', to: 't-aa0003' },
    ])
    expect(parsed.ready).toEqual(['t-aa0002'])
  })

  it('从 JSON 反序列化回的对象仍是合法读方输入（往返后读方结果一致）', () => {
    const file = buildQueueFile()
    const revived = JSON.parse(JSON.stringify(file)) as QueueFile

    expect(readyTasks(revived.tasks, REQ).map((t) => t.id)).toEqual(['t-aa0002'])
    expect(() => assertDagAcyclic(revived.tasks, REQ)).not.toThrow()
  })
})
