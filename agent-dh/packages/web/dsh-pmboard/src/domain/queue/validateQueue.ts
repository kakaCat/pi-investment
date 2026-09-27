/**
 * 队列数据校验 V-1~V-6（REQ-260927202051-f6df · S-3 / I-4 / FR-5）。
 *
 * 规则编号是**单一事实源**（design/data-model.md「数据约束」），本文件是唯一实现处：
 *
 * | 规则 | 含义 |
 * |---|---|
 * | V-1 | 必填字段完整性（顶层 8 字段 + 每个任务的必填字段/类型） |
 * | V-2 | 标识唯一性（`tasks[].id` 两两唯一） |
 * | V-3 | 引用完整性（dependsOn / edges / layers / ready 的 id 都存在；requirementId 与顶层一致） |
 * | V-4 | 层级一致性（layer ≥ 0；层随依赖递增；layer=0 无依赖；layer 号从 0 连续） |
 * | V-5 | ready 双向一致性（假就绪禁止 + 漏就绪禁止） |
 * | V-6 | 无环性（拓扑排序可完整完成） |
 *
 * ⚠️ 三条硬约束：
 *
 * 1. **不抛错**：任何坏输入都只返回 `{passed:false, issues}`，绝不 throw（TC-2.10）。
 *    调用方按场景决定处置——写前拒绝落盘（抛 QUEUE_VALIDATION_FAILED）、读后降级返回
 *    undefined、更新前保持旧内容。若这里 throw，三种处置就退化成一种（整个调用栈炸掉）。
 * 2. **环检测 import 自 `topology.ts`**，不复制算法。两份环检测必然漂移，而 V-5 的正反例
 *    又依赖同一份推导——复制出来的第二份会让"检查通过但解析崩"变成可能。
 * 3. **纯函数**：不 import 任何 node 内置模块、不碰时钟与随机数。
 *
 * 校验是**累积式**的：一次调用报出全部问题，而不是遇到第一条就返回。理由：迁移与手工修数据时，
 * 一次看全比"修一个再跑一次"快得多；也便于测试里对"6/6 规则各有反例"做汇总断言。
 */

import type { TaskRecord } from '../../shared/protocol.js'
import type { QueueEdge, QueueFile, QueueLayer, QueueTask, ValidationIssue, ValidationResult, ValidationRule } from './QueueTypes.js'
import { computeLayers, computeReady } from './topology.js'

/**
 * 任务的必填字段（对齐 `TaskRecord` 的**非可选**成员）。
 *
 * 只列非可选成员：可选字段（`implementation` / `lastRun` / `revisions` …）缺失是合法的。
 * 这些字段一个都不能在队列里丢——`lastRun` 缺失会让子卡完工凭证门永远判不通过，
 * `lastReport` 缺失会让 done 凭证门永远拦人（**静默失效**，不是报错）。
 */
const REQUIRED_TASK_FIELDS: readonly (keyof TaskRecord)[] = [
  'id',
  'requirementId',
  'title',
  'description',
  'phase',
  'side',
  'dependsOn',
  'scope',
  'acceptance',
  'context',
  'status',
  'blocked',
  'executions',
  'comments',
  'version',
  'createdAt',
  'updatedAt',
  'createdBy',
  'updatedBy',
]

/** 队列顶层必填字段（`updated_at` 可选，见 QueueTypes.QueueFile）。 */
const REQUIRED_TOP_LEVEL_FIELDS = ['version', 'requirement_id', 'schemaVersion', 'generated_at', 'tasks', 'edges', 'layers', 'ready'] as const

/**
 * V-1~V-6 全量校验。**不抛错**：失败只填 `issues`（`passed = issues.length === 0`）。
 *
 * 入参类型是 `QueueFile`，但实现按"可能来自任意 JSON"的防御口径处理（内部先收窄为
 * `Record<string, unknown>`）——`load()` 拿到的是 `JSON.parse` 的产物，不是构造好的对象。
 */
export function validateQueueFile(file: QueueFile): ValidationResult {
  const issues: ValidationIssue[] = []
  const add = (rule: ValidationRule, message: string, path?: string): void => {
    issues.push(path === undefined ? { rule, message } : { rule, message, path })
  }

  const raw = file as unknown
  if (raw === null || typeof raw !== 'object' || Array.isArray(raw)) {
    add('V-1', '队列文件必须是 JSON 对象', 'root')
    return { passed: false, issues }
  }
  const f = raw as Record<string, unknown>

  // ── V-1：顶层必填与类型 ────────────────────────────────────────────────
  for (const key of REQUIRED_TOP_LEVEL_FIELDS) {
    if (f[key] === undefined || f[key] === null) add('V-1', `缺少必填字段 ${key}`, key)
  }
  if (typeof f.version !== 'number' || !Number.isInteger(f.version) || f.version < 1) {
    add('V-1', 'version 必须是 ≥1 的整数', 'version')
  }
  if (typeof f.requirement_id !== 'string' || f.requirement_id.length === 0) {
    add('V-1', 'requirement_id 必须是非空字符串', 'requirement_id')
  } else if (!f.requirement_id.startsWith('REQ-')) {
    add('V-1', 'requirement_id 必须以 REQ- 开头', 'requirement_id')
  }
  if (typeof f.schemaVersion !== 'number' || !Number.isInteger(f.schemaVersion)) {
    add('V-1', 'schemaVersion 必须是整数', 'schemaVersion')
  }
  if (typeof f.generated_at !== 'string' || f.generated_at.length === 0) {
    add('V-1', 'generated_at 必须是非空字符串（ISO 8601）', 'generated_at')
  }
  if (f.updated_at !== undefined && typeof f.updated_at !== 'string') {
    add('V-1', 'updated_at 若存在必须是字符串', 'updated_at')
  }
  for (const key of ['tasks', 'edges', 'layers', 'ready'] as const) {
    if (f[key] !== undefined && f[key] !== null && !Array.isArray(f[key])) add('V-1', `${key} 必须是数组`, key)
  }

  const tasks = Array.isArray(f.tasks) ? (f.tasks as unknown[]) : undefined
  if (tasks === undefined) {
    // tasks 不是数组时，下游每条规则都无输入可言——只报 V-1，不做级联噪声。
    return { passed: issues.length === 0, issues }
  }

  // ── V-1（任务级）+ V-2 ────────────────────────────────────────────────
  const ids = new Set<string>()
  tasks.forEach((entry, i) => {
    const path = `tasks[${i}]`
    if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) {
      add('V-1', '任务必须是对象', path)
      return
    }
    const t = entry as Record<string, unknown>
    for (const field of REQUIRED_TASK_FIELDS) {
      if (t[field as string] === undefined || t[field as string] === null) add('V-1', `任务缺少必填字段 ${String(field)}`, `${path}.${String(field)}`)
    }
    if (typeof t.id !== 'string' || t.id.length === 0) add('V-1', '任务 id 必须是非空字符串', `${path}.id`)
    if (t.dependsOn !== undefined && !Array.isArray(t.dependsOn)) add('V-1', '任务 dependsOn 必须是数组', `${path}.dependsOn`)
    if (t.layer === undefined || typeof t.layer !== 'number' || !Number.isInteger(t.layer)) {
      add('V-1', '任务 layer 必须是整数（队列专有派生字段）', `${path}.layer`)
    }
    if (typeof t.id === 'string' && t.id.length > 0) {
      if (ids.has(t.id)) {
        add('V-2', `任务 id 重复：${t.id}`, `${path}.id`)
      } else {
        ids.add(t.id)
      }
    }
  })

  const taskList = tasks as readonly QueueTask[]
  const byId = new Map<string, QueueTask>()
  for (const t of taskList) {
    if (t !== null && typeof t === 'object' && typeof t.id === 'string' && !byId.has(t.id)) byId.set(t.id, t)
  }
  const layerOf = new Map<string, number>()
  for (const t of taskList) {
    if (t !== null && typeof t === 'object' && typeof t.id === 'string' && typeof t.layer === 'number' && !layerOf.has(t.id)) {
      layerOf.set(t.id, t.layer)
    }
  }

  // ── V-3：引用完整性 ───────────────────────────────────────────────────
  const requirementId = typeof f.requirement_id === 'string' ? f.requirement_id : undefined
  taskList.forEach((t, i) => {
    if (t === null || typeof t !== 'object') return
    const deps = Array.isArray(t.dependsOn) ? t.dependsOn : []
    deps.forEach((dep, j) => {
      if (typeof dep !== 'string' || !ids.has(dep)) add('V-3', `dependsOn 引用了不存在的任务 ${String(dep)}`, `tasks[${i}].dependsOn[${j}]`)
    })
    if (requirementId !== undefined && t.requirementId !== requirementId) {
      add(
        'V-3',
        `任务 requirementId(${String(t.requirementId)}) 与队列 requirement_id(${requirementId}) 不一致（跨需求串档）`,
        `tasks[${i}].requirementId`,
      )
    }
  })

  const edges = Array.isArray(f.edges) ? (f.edges as unknown[]) : []
  edges.forEach((entry, i) => {
    if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) {
      add('V-1', '边必须是对象', `edges[${i}]`)
      return
    }
    const e = entry as Partial<QueueEdge>
    if (typeof e.from !== 'string' || e.from.length === 0) add('V-1', 'edges[].from 必须是非空字符串', `edges[${i}].from`)
    else if (!ids.has(e.from)) add('V-3', `edges[].from 引用了不存在的任务 ${e.from}`, `edges[${i}].from`)
    if (typeof e.to !== 'string' || e.to.length === 0) add('V-1', 'edges[].to 必须是非空字符串', `edges[${i}].to`)
    else if (!ids.has(e.to)) add('V-3', `edges[].to 引用了不存在的任务 ${e.to}`, `edges[${i}].to`)
  })

  const layers = Array.isArray(f.layers) ? (f.layers as unknown[]) : []
  layers.forEach((entry, i) => {
    if (entry === null || typeof entry !== 'object' || Array.isArray(entry)) {
      add('V-1', '层必须是对象', `layers[${i}]`)
      return
    }
    const l = entry as Partial<QueueLayer>
    if (typeof l.layer !== 'number' || !Number.isInteger(l.layer)) add('V-1', 'layers[].layer 必须是整数', `layers[${i}].layer`)
    else if (l.layer < 0) add('V-4', 'layers[].layer 不能为负', `layers[${i}].layer`)
    if (!Array.isArray(l.tasks)) {
      add('V-1', 'layers[].tasks 必须是数组', `layers[${i}].tasks`)
      return
    }
    l.tasks.forEach((id, j) => {
      if (typeof id !== 'string' || !ids.has(id)) add('V-3', `layers[].tasks 引用了不存在的任务 ${String(id)}`, `layers[${i}].tasks[${j}]`)
    })
  })

  const ready = Array.isArray(f.ready) ? (f.ready as unknown[]) : []
  ready.forEach((id, i) => {
    if (typeof id !== 'string' || !ids.has(id)) add('V-3', `ready 引用了不存在的任务 ${String(id)}`, `ready[${i}]`)
  })

  // ── V-4：层级一致性 ───────────────────────────────────────────────────
  taskList.forEach((t, i) => {
    if (t === null || typeof t !== 'object') return
    const deps = Array.isArray(t.dependsOn) ? t.dependsOn : []
    if (typeof t.layer === 'number' && t.layer < 0) add('V-4', '任务 layer 不能为负', `tasks[${i}].layer`)
    if (t.layer === 0) {
      deps.forEach((dep, j) => {
        if (typeof dep === 'string' && ids.has(dep)) {
          add('V-4', `layer=0 的任务不得有依赖（却依赖 ${dep}）`, `tasks[${i}].dependsOn[${j}]`)
        }
      })
    }
    if (typeof t.layer !== 'number') return
    deps.forEach((dep) => {
      if (typeof dep !== 'string') return
      const depLayer = layerOf.get(dep)
      if (depLayer === undefined) return // 悬空依赖：V-3 已报，不重复计
      if (!(t.layer > depLayer)) {
        add('V-4', `层号未随依赖递增：任务层 ${t.layer} 不大于前置 ${dep} 的层 ${depLayer}`, `tasks[${i}].layer`)
      }
    })
  })
  if (layers.length > 0) {
    const indices = layers
      .map((entry) => (entry !== null && typeof entry === 'object' ? (entry as Partial<QueueLayer>).layer : undefined))
      .filter((n): n is number => typeof n === 'number')
    const expected = indices.map((_, i) => i)
    const actual = [...indices].sort((a, b) => a - b)
    if (actual.join(',') !== expected.join(',')) {
      add('V-4', `layer 号必须从 0 连续（实际 [${actual.join(', ')}]）`, 'layers')
    }
  }

  // ── V-5：ready 双向一致性 ─────────────────────────────────────────────
  const readyIds = ready.filter((id): id is string => typeof id === 'string')
  const readySet = new Set(readyIds)
  readyIds.forEach((id, i) => {
    const t = byId.get(id)
    if (t === undefined) return // V-3 已报
    const deps = Array.isArray(t.dependsOn) ? t.dependsOn : []
    const unmet = deps.filter((dep) => typeof dep === 'string' && byId.get(dep)?.status !== 'done')
    if (unmet.length > 0) {
      add('V-5', `假就绪：ready 中任务 ${id} 的依赖未全部 done [${unmet.map(String).join(', ')}]`, `ready[${i}]`)
    } else if (t.status !== 'todo') {
      add('V-5', `假就绪：ready 中任务 ${id} 自身状态为 ${String(t.status)}（可执行集只应含 todo）`, `ready[${i}]`)
    }
  })
  for (const id of computeReady(taskList)) {
    if (!readySet.has(id)) add('V-5', `漏就绪：任务 ${id} 依赖已全 done 且自身 todo，却不在 ready 中`, 'ready')
  }

  // ── V-6：无环性（算法 import 自 topology，不复制） ──────────────────────
  try {
    computeLayers(taskList)
  } catch (error) {
    add('V-6', `依赖成环：${(error as Error).message}`, 'tasks')
  }

  return { passed: issues.length === 0, issues }
}

/** 便捷断言：某结果是否命中指定规则（调用方/测试用，避免到处写 issues.some）。 */
export function hasIssue(result: ValidationResult, rule: ValidationRule): boolean {
  return result.issues.some((issue) => issue.rule === rule)
}
