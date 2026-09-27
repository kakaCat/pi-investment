/**
 * 队列 DAG 派生视图（REQ-260927202051-f6df · S-2 / I-3 / FR-1）。
 *
 * 本文件是队列三个**派生字段**（edges / layers / ready）的唯一计算处：
 * - `computeEdges`  → 由 `tasks[].dependsOn` 展开边集
 * - `computeLayers` → Kahn 入度分层（有环抛错），结果即 `QueueTask.layer` 的来源
 * - `computeReady`  → 依赖全 done 且自身 todo 的任务 id
 *
 * ⚠️ 三条硬约束（违反会静默产生"假就绪/漏就绪"或"写路径两套算法漂移"）：
 *
 * 1. **纯函数**：不 import 任何 node 内置模块（验收口径 = 对本文件 grep 文件系统模块名的
 *    命中数为 0）、不碰时钟与随机数、不改入参（与 `domain/task/*` 同构）。
 *    写路径（QueueRepository / QueueTaskStore）可以放心在任意环境重算，不产生副作用。
 * 2. **`computeReady` 是唯一实现**——写路径（`QueueTaskStore.mutate`）必须 import 本函数重算，
 *    不得另写一份"就地判断"。两套实现必然漂移：改一处忘一处时，队列文件里的 `ready`
 *    会与真实可执行集不一致，而 V-5 自己的正反例又都用同一份实现去校验，于是**检查不出来**。
 * 3. **有环必须抛错**（message 含 `CIRCULAR`，code 为 `CIRCULAR_DEPENDENCY`）：
 *    环上任务永远进不了 ready，静默返回一份"没有 ready 的队列"会把问题伪装成"还没排到"。
 *    分层与 ready 是**生成期**的断言，宁可让拆分失败，也不落盘一份死锁队列。
 *
 * 关于**悬空依赖**（`dependsOn` 指向不存在的任务）的处置：分层时按"忽略该依赖"处理，
 * 而不是当成环——否则一条脏引用会把整份队列报成 CIRCULAR，掩盖真正的环。悬空引用由
 * `validateQueue.ts` 的 V-3 负责检出（职责分离：topology 保证"可算"，validate 保证"合法"）。
 */

import type { QueueEdge, QueueLayer, QueueTask } from './QueueTypes.js'

/** 环依赖错误码（design/interfaces.md「错误码」）。 */
export const CIRCULAR_DEPENDENCY = 'CIRCULAR_DEPENDENCY'

/**
 * 由 `tasks[].dependsOn` 展开依赖边（`from` 是 `to` 的前置）。
 *
 * 忠实展开：**不做存在性过滤**——`dependsOn` 里写了什么就产出什么边。
 * 这样 V-3 对 `edges[].from/to` 的存在性检查才有意义（若在这里悄悄过滤掉悬空边，
 * 落盘文件里"边少了"就永远不会被发现）。重复的 dependsOn 项按下标去重，保证顺序确定。
 */
export function computeEdges(tasks: readonly QueueTask[]): QueueEdge[] {
  const edges: QueueEdge[] = []
  const seen = new Set<string>()
  for (const task of tasks) {
    if (!isTaskLike(task)) continue
    for (const from of Array.isArray(task.dependsOn) ? task.dependsOn : []) {
      const key = `${from}\u0000${task.id}`
      if (seen.has(key)) continue
      seen.add(key)
      edges.push({ from, to: task.id })
    }
  }
  return edges
}

/**
 * Kahn 入度分层：第 n 层任务的所有依赖都落在 < n 层。
 *
 * 语义等价于 `layer(t) = 1 + max(layer(dep))`（无依赖为 0），因为一个任务只有在
 * **全部前置都出队之后**才会被释放——释放它的那一轮就是它的层。同层任务互不依赖，可并行。
 *
 * 空输入返回 `[]`（不是错误：可写的空队列，见 TC-1.4 / TC-11.3）。
 * 有环（含自依赖）抛 `Error`，`message` 含 `CIRCULAR`、`code` 为 `CIRCULAR_DEPENDENCY`。
 */
export function computeLayers(tasks: readonly QueueTask[]): QueueLayer[] {
  // 入口防御（**实测踩到过**）：本函数的输入可能是 `JSON.parse` 的产物，条目里混着
  // null/数字/字符串（畸形队列文件）。此时 `task.id` 会抛 `Cannot read properties of null`
  // ——校验路径不允许任何 throw（V-1 要负责报"任务必须是对象"），所以先只收任务对象。
  const nodes = (tasks as readonly unknown[]).filter(isTaskLike) as readonly QueueTask[]
  const total = nodes.length
  if (total === 0) return []

  // 以**下标**为主键而非 id：V-2 未通过（id 重复）时也要能算出结果并让校验去报错，
  // 用 Map<id, ...> 会把重复 id 静默合并、把"两个任务"算成"一个"。
  const indexOf = new Map<string, number>()
  nodes.forEach((task, i) => {
    if (!indexOf.has(task.id)) indexOf.set(task.id, i)
  })

  const inDegree = new Array<number>(total).fill(0)
  const dependents: number[][] = Array.from({ length: total }, () => [])
  nodes.forEach((task, i) => {
    for (const dep of Array.isArray(task.dependsOn) ? task.dependsOn : []) {
      const j = indexOf.get(dep)
      if (j === undefined) continue // 悬空依赖：忽略（见文件头说明）
      inDegree[i] += 1
      dependents[j]!.push(i)
    }
  })

  const layers: QueueLayer[] = []
  let wave: number[] = []
  for (let i = 0; i < total; i += 1) if (inDegree[i] === 0) wave.push(i)

  let processed = 0
  while (wave.length > 0) {
    const current = wave
    wave = []
    layers.push({ layer: layers.length, tasks: current.map((i) => nodes[i]!.id) })
    for (const i of current) {
      processed += 1
      for (const k of dependents[i]!) {
        inDegree[k]! -= 1
        if (inDegree[k] === 0) wave.push(k)
      }
    }
  }

  if (processed < total) {
    const stuck = nodes.filter((_, i) => inDegree[i]! > 0).map((t) => t.id)
    const error = new Error(
      `CIRCULAR dependency detected in queue: 以下任务因依赖成环无法分层 [${stuck.join(', ')}]`,
    ) as Error & { code?: string }
    error.code = CIRCULAR_DEPENDENCY
    throw error
  }

  return layers
}

/**
 * 由状态与依赖推导 ready（**唯一实现**，写路径不得另写一份）。
 *
 * 规则（design/data-model.md V-5）：
 * - 假就绪禁止：进入 ready 的任务，其 `dependsOn` 必须**全部 `done`**
 * - 漏就绪禁止：依赖全 done 且自身 `todo` 的任务**必须**出现在 ready 中
 *
 * 因此本函数就是"漏就绪"定义本身，而"假就绪"由 validateQueue 用 `ready ⊆ 本函数结果` 反向校验。
 *
 * 悬空依赖按"未满足"处理（`byId.get(d)?.status === 'done'` 为 false）——保守不放行，
 * 与 V-3 的检出职责互补：校验报错，推导不冒险解锁。
 * 返回顺序 = `tasks` 输入顺序（稳定，便于比对与测试）。
 */
export function computeReady(tasks: readonly QueueTask[]): string[] {
  const byId = new Map<string, QueueTask>()
  for (const task of tasks) {
    if (!isTaskLike(task)) continue
    if (!byId.has(task.id)) byId.set(task.id, task)
  }

  const ready: string[] = []
  for (const task of tasks) {
    if (!isTaskLike(task)) continue
    if (task.status !== 'todo') continue
    const deps = Array.isArray(task.dependsOn) ? task.dependsOn : []
    const unlocked = deps.every((dep) => byId.get(dep)?.status === 'done')
    if (unlocked) ready.push(task.id)
  }
  return ready
}

/**
 * 运行时形状守卫：只认"看起来像任务对象"的条目（非 null 的对象）。
 *
 * 存在的理由不是洁癖，而是**实测**：`computeLayers` 曾对 `tasks: [null, 42, 'x']`
 * 这样的畸形输入抛 `Cannot read properties of null (reading 'id')`，
 * 而校验路径（V-1 负责报"任务必须是对象"）**不允许任何 throw**。
 * 守卫放在推导函数里而非只放在校验里，是因为推导函数是公开 API，
 * 任何调用方（含未来的迁移脚本）都可能喂进 JSON 原始数据。
 */
function isTaskLike(value: unknown): boolean {
  return value !== null && typeof value === 'object'
}
