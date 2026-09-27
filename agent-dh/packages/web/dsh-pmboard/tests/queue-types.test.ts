/**
 * 队列类型契约测试（REQ-260927202051-f6df · t1 / FR-1 / FR-5）。
 *
 * 本文件的核心是**类型级断言**——因为 t1 要保证的性质（"QueueTask 恰好等于
 * TaskRecord + layer，字段一个不多一个不少"）是**类型层**的事实，运行时断言
 * 只能验证我自己造的样本，验证不了类型定义本身。
 *
 * 断言写法说明：`type Assert<C extends true> = C` + 把条件类型赋给常量，
 * 条件不成立时**编译失败**（`tsc --noEmit` 报错），成立时编译通过。
 * 因此本文件的"测试通过"= `npx tsc --noEmit` 通过 + vitest 运行时断言通过。
 */

import { describe, expect, it } from 'vitest'
import { QUEUE_VERSION } from '../src/domain/queue/QueueTypes.js'
import type {
  QueueEdge,
  QueueFile,
  QueueLayer,
  QueueTask,
  ValidationIssue,
  ValidationResult,
} from '../src/domain/queue/QueueTypes.js'
import type { TaskRecord } from '../src/shared/protocol.js'

/** 编译期断言：条件为 false 时本行报错（`Type 'false' does not satisfy the constraint 'true'`）。 */
type Assert<T extends true> = T

// 说明：下列类型别名全部 `export`，是为了通过本仓 tsconfig 的 `noUnusedLocals`——
// 非导出的"只做断言、不参与计算"的类型别名会被判为未使用（TS6196）。导出即视为已用，
// 而断言效果（条件不成立则编译失败）不受影响。

// ── 类型级断言 1：QueueTask 与 TaskRecord & { layer } 互相可赋值（即等价） ──
export type _T1Forward = Assert<QueueTask extends TaskRecord & { layer: number } ? true : false>
export type _T1Backward = Assert<TaskRecord & { layer: number } extends QueueTask ? true : false>

// ── 类型级断言 2：键集差集恰为 { layer }（双向包含 = 精确相等） ──
// 队列相对 TaskRecord 多出来的键，必须 ⊆ {'layer'}
export type ExtraKeys = Exclude<keyof QueueTask, keyof TaskRecord>
export type _T2ExtraSubset = Assert<ExtraKeys extends 'layer' ? true : false>
// 且 {'layer'} ⊆ 多出来的键 —— 两者合起来才证明"恰为 {layer}"
export type _T2LayerPresent = Assert<'layer' extends ExtraKeys ? true : false>

// ── 类型级断言 3：TaskRecord 的键一个都没漏（MissingKeys 必须为 never） ──
export type MissingKeys = Exclude<keyof TaskRecord, keyof QueueTask>
export type _T3NoMissing = Assert<MissingKeys extends never ? true : false>

// ── 类型级断言 4：layer 是 number ──
export type _T4LayerType = Assert<QueueTask['layer'] extends number ? true : false>

// ── 类型级断言 5：校验规则编号恰为 V-1~V-6 ──
export type Rules = ValidationIssue['rule']
export type _T5RuleCount = Assert<
  Exclude<Rules, 'V-1' | 'V-2' | 'V-3' | 'V-4' | 'V-5' | 'V-6'> extends never ? true : false
>

/**
 * 构造一份**字段齐全**的 TaskRecord 样本。
 *
 * 这里刻意写出**必填字段的每一个**（而非用 `as` 强转）：一旦 TaskRecord 新增必填字段，
 * 本样本会编译失败，提醒维护者去检查队列是否需要同步——这正是我们要的看护效果。
 */
function sampleTask(): TaskRecord {
  const actor = { kind: 'agent' as const, sessionId: 'session-test' }
  return {
    id: 't-1a2b3c',
    requirementId: 'REQ-260927202051-f6df',
    title: '样本任务',
    description: '用于契约测试',
    phase: 'implement',
    side: 'backend',
    dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: '样本验收',
    context: '样本背景',
    status: 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: 1759000000000,
    updatedAt: 1759000000000,
    createdBy: actor,
    updatedBy: actor,
  }
}

describe('QueueTypes 类型契约（t1）', () => {
  it('QUEUE_VERSION 为 1（队列格式版本）', () => {
    expect(QUEUE_VERSION).toBe(1)
  })

  it('QueueTask 在运行时保留 TaskRecord 的全部字段，且多出 layer', () => {
    const base = sampleTask()
    const queued: QueueTask = { ...base, layer: 0 }

    // 差集（运行时侧对样本的核对）：应恰为 ['layer']
    const extra = Object.keys(queued).filter((k) => !(k in base))
    expect(extra).toEqual(['layer'])

    // 反向：TaskRecord 的每个键都在队列任务里（无遗漏）
    const missing = Object.keys(base).filter((k) => !(k in queued))
    expect(missing).toEqual([])

    // layer 是 number
    expect(typeof queued.layer).toBe('number')
  })

  it('QueueFile 顶层字段齐全且语义自洽', () => {
    const task: QueueTask = { ...sampleTask(), layer: 0 }
    const edge: QueueEdge = { from: 't-1a2b3c', to: 't-1a2b3d' }
    const layer: QueueLayer = { layer: 0, tasks: ['t-1a2b3c'] }
    const file: QueueFile = {
      version: QUEUE_VERSION,
      requirement_id: 'REQ-260927202051-f6df',
      schemaVersion: 9,
      generated_at: '2026-09-27T23:00:00.000Z',
      tasks: [task],
      edges: [edge],
      layers: [layer],
      ready: ['t-1a2b3c'],
    }

    // 必填字段恰为这 8 个（updated_at 是可选，见下一条断言）
    expect(Object.keys(file).sort()).toEqual(
      [
        'edges',
        'generated_at',
        'layers',
        'ready',
        'requirement_id',
        'schemaVersion',
        'tasks',
        'version',
      ].sort()
    )
    // updated_at 可选：上面未给也能构造
    expect(file.updated_at).toBeUndefined()
    // 给上则保留（证明它是可选，而不是被忽略的字段）
    const withUpdatedAt: QueueFile = { ...file, updated_at: '2026-09-28T00:00:00.000Z' }
    expect(withUpdatedAt.updated_at).toBe('2026-09-28T00:00:00.000Z')
    expect(file.schemaVersion).toBe(9)
  })

  it('ValidationResult 允许"失败但不抛错"的表达（issues 非空、passed=false）', () => {
    const result: ValidationResult = {
      passed: false,
      issues: [{ rule: 'V-3', message: 'dependsOn 引用了不存在的任务', path: 'tasks[1].dependsOn[0]' }],
    }
    expect(result.passed).toBe(false)
    expect(result.issues).toHaveLength(1)
    expect(result.issues[0]!.rule).toBe('V-3')
    expect(result.issues[0]!.path).toBe('tasks[1].dependsOn[0]')
  })
})
