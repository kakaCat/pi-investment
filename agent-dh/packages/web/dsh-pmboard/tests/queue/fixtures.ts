/**
 * 队列测试夹具（REQ-260927202051-f6df）。
 *
 * 为什么单独一个模块而不是每个测试各写一份构造：QueueTask 有 20+ 个必填字段，
 * 每个测试文件各写一份"手工填全字段"的构造函数，等于把字段清单抄 N 遍——
 * TaskRecord 加一个必填字段就要改 N 处，且漏改的那一处是**静默**的（测试仍然绿）。
 * 集中一处后，类型检查会在唯一的地方报错。
 *
 * 本文件不是测试文件（vitest include 只收 `tests/**\/*.test.ts`），是被测试 import 的模块。
 */

import type { QueueFile, QueueTask } from '../../src/domain/queue/QueueTypes.js'
import { computeEdges, computeLayers, computeReady } from '../../src/domain/queue/topology.js'
import type { TaskRecord } from '../../src/shared/protocol.js'

/** 本需求自身 id（测试里当默认 requirement_id 用）。 */
export const REQ = 'REQ-260927202051-f6df'

/** 固定时钟：夹具里不出现 `Date.now()`，让断言可复现。 */
export const NOW = 1759000000000

export interface MkTaskOptions {
  dependsOn?: string[]
  status?: TaskRecord['status']
  requirementId?: string
  layer?: number
}

/** 构造一份字段齐全的 QueueTask（layer 是占位值，`queueOf` 会按拓扑重算）。 */
export function mkTask(id: string, opts: MkTaskOptions = {}): QueueTask {
  const actor = { kind: 'agent' as const, sessionId: 'session-queue-fixture' }
  const base: TaskRecord = {
    id,
    requirementId: opts.requirementId ?? REQ,
    title: `任务 ${id}`,
    description: '队列测试样本',
    phase: 'implement',
    side: 'backend',
    scope: { apis: [], tables: [], files: [] },
    acceptance: '样本验收（含可执行锚点）',
    context: '样本背景',
    dependsOn: opts.dependsOn ?? [],
    status: opts.status ?? 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
    createdBy: actor,
    updatedBy: actor,
  }
  return { ...base, layer: opts.layer ?? 0 }
}

/**
 * 由任务草稿构造一份**合法**队列文件：edges / layers / ready 全部由 topology 重算，
 * 每个任务的 `layer` 按拓扑结果回填。
 *
 * 之所以"重算"而不是让调用方手填派生字段：手填就等于每个测试自己实现一遍拓扑，
 * 一旦实现有偏差，V-4/V-5 的校验会跟着错——非法样本要**故意**改坏某一个字段，
 * 而不是先构造一份本来就不自洽的队列。
 */
export function queueOf(
  requirementId: string,
  draft: readonly QueueTask[],
  overrides: Partial<Pick<QueueFile, 'version' | 'schemaVersion' | 'generated_at' | 'updated_at'>> = {},
): QueueFile {
  const layerOf = new Map<string, number>()
  for (const layer of computeLayers(draft)) {
    for (const id of layer.tasks) if (!layerOf.has(id)) layerOf.set(id, layer.layer)
  }
  const tasks = draft.map((t) => ({ ...t, layer: layerOf.get(t.id) ?? t.layer }))
  return {
    version: 1,
    requirement_id: requirementId,
    schemaVersion: 9,
    generated_at: '2026-09-27T22:00:00.000Z',
    tasks,
    edges: computeEdges(tasks),
    layers: computeLayers(tasks),
    ready: computeReady(tasks),
    ...overrides,
  }
}

/** 深拷贝（改坏样本前先复制，避免用例之间互相污染——vitest 里对象字面量会被复用）。 */
export function clone<T>(value: T): T {
  return structuredClone(value)
}

/**
 * 构造一份**不重算派生视图**的队列文件——专供"故意非法"的样本。
 *
 * 为什么需要它：`queueOf` 会调 `computeLayers`，而环依赖样本在分层那一步就抛错了，
 * 根本构造不出来（"构造非法数据时先被合法化逻辑拦下"）。所以成环样本必须绕过重算，
 * 手工给出 edges/layers/ready——这也更贴近真实场景：非法文件是**外部**产生的，
 * 不由本仓的推导函数生成。
 */
export function rawQueue(
  requirementId: string,
  tasks: readonly QueueTask[],
  overrides: Partial<QueueFile> = {},
): QueueFile {
  return {
    version: 1,
    requirement_id: requirementId,
    schemaVersion: 9,
    generated_at: '2026-09-27T22:00:00.000Z',
    tasks: [...tasks],
    edges: computeEdges(tasks),
    layers: [],
    ready: [],
    ...overrides,
  }
}
