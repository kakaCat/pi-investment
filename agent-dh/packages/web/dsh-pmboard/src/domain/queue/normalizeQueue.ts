/**
 * 队列文件依赖归一化 —— **写路径与迁移脚本共用的唯一实现**。
 *
 * 做什么（两步，顺序不能反）：
 * 1. **传递归约**：`tasks[].dependsOn` 从「全部前置（传递闭包）」归一为「直接前置」
 *    （实现见 `./transitiveReduction.ts`，纯函数、零 import）。
 * 2. **派生视图整份重算**：`layer` / `edges` / `layers` / `ready` 全部按归约后的依赖重算
 *    ——它们都是派生字段，写回时必须整份重算（见 QueueTypes 文件头）。
 *
 * 为什么必须与写路径同一份实现：`QueueTaskStore.recompute` 与迁移脚本若各写一遍"怎么折"，
 * 必然漂移——迁移后的文件与写路径产出的文件形状不同，而两者的消费者（看板 / ready 判定）
 * 又用同一套读取口径，于是**漂移静默**（本仓已踩过：ready 两套实现）。
 *
 * 语义等价性：传递归约保持可达性 ⇒ `computeLayers`（最长路径）与 `computeReady`（依赖全 done）
 * 的结果与归约前逐字相同；因此归一化**不改执行序、不改可开工集**，只是去掉冗余存储。
 *
 * ⚠️ `computeLayers` 对成环**抛错**（`CIRCULAR_DEPENDENCY`）——这是生成期断言，本函数沿用该行为，
 * 不让一份死锁队列被静默写回（见 `topology.ts` 硬约束 3）。
 *
 * @module dsh-pmboard/domain/queue/normalizeQueue
 */

import type { QueueFile, QueueTask } from './QueueTypes.js'
import { computeEdges, computeLayers, computeReady } from './topology.js'
import { transitiveReduce, type DependencyGraph } from './transitiveReduction.js'

/** 数组逐项相等（顺序敏感——依赖顺序也是数据）。 */
function sameList(a: readonly string[] | undefined, b: readonly string[]): boolean {
  if (!Array.isArray(a) || a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false
  return true
}

/**
 * 把一份队列文件归一化：`dependsOn` 只留直接前置 + 派生视图整份重算。
 *
 * @param file 队列文件（**不改入参**；返回新对象）
 */
export function normalizeQueueFile(file: QueueFile): QueueFile {
  const graph: Map<string, readonly string[]> = new Map()
  for (const task of file.tasks) {
    if (task === null || typeof task !== 'object') continue
    if (graph.has(task.id)) continue // V-2 重复 id：与 computeLayers 同口径，首个为准
    graph.set(task.id, Array.isArray(task.dependsOn) ? task.dependsOn : [])
  }
  const reduced = transitiveReduce(graph as DependencyGraph)

  const withDeps: QueueTask[] = file.tasks.map((task) => {
    const next = reduced.get(task.id)
    if (next === undefined || sameList(task.dependsOn, next)) return task
    return { ...task, dependsOn: next }
  })

  const layers = computeLayers(withDeps)
  const layerOf = new Map<string, number>()
  for (const layer of layers) {
    for (const id of layer.tasks) if (!layerOf.has(id)) layerOf.set(id, layer.layer)
  }
  const tasks = withDeps.map((t) => ({ ...t, layer: layerOf.get(t.id) ?? t.layer }))
  return { ...file, tasks, edges: computeEdges(tasks), layers, ready: computeReady(tasks) }
}

/**
 * 归约会删掉多少条依赖（**只读统计**，供迁移脚本与工具回执报数）。
 * 不参与判定，也不改数据。
 */
export function countRedundantDependencies(file: Pick<QueueFile, 'tasks'>): number {
  const graph = new Map<string, readonly string[]>()
  for (const task of file.tasks) {
    if (task === null || typeof task !== 'object') continue
    if (graph.has(task.id)) continue
    graph.set(task.id, Array.isArray(task.dependsOn) ? task.dependsOn : [])
  }
  const reduced = transitiveReduce(graph as DependencyGraph)
  let removed = 0
  for (const [id, deps] of graph) {
    const kept = reduced.get(id) ?? []
    removed += deps.length - kept.length
  }
  return removed
}
