/**
 * 依赖传递归约（transitive reduction）——**「dependsOn 只写直接前置」这条口径的唯一实现**。
 *
 * 背景（2026-09-29 用户裁定「B 数据侧」，REQ-260929010300-dbf9）：拆分落库时每张卡写的是
 * **全部前置**（传递闭包，例如计划里 t6 依赖 t2,t3,t4,t5），于是数据里普遍存在
 * 「A→B、B→C、A→C」三角形——2026-09-29 线上实测：55 份队列、卡片层 646 条边里 **98 条**
 * 存在替代路径（33/55 份队列中招）。
 *
 * 过去画布靠 `views/dag-view.ts` 的 `reduceEdges` 在**绘制前**折叠，但**数据本身仍带闭包**：
 * 任务表、依赖列、RTM、甘特图等每个消费者都得各自再折一次（或干脆不折）。本模块把归约
 * **前移到数据写入这一处**（队列写路径 + 计划解析 + 迁移脚本共用），使 `dependsOn` 只保留直接前置。
 *
 * 语义保证：传递归约**保持可达性**——删掉 A→C 后 C 仍可由 A→…→C 到达，因此
 * `computeLayers`（最长路径）与 `computeReady`（依赖是否全 done）的结果**逐字不变**。
 *
 * 不做什么（三条边界，改动前先读）：
 * 1. **不删悬空前置**（指向不存在任务的那条）。归约的前提是"能从别的依赖走到它"；而悬空引用
 *    本身是 V-3 要报的问题，静默删掉会让问题消失（与 `topology.computeEdges` 的"忠实展开"同口径）。
 * 2. **不报错**：成环由 `computeLayers` / `validateQueue` 响亮报错；本函数对环只保证
 *    "不递归爆栈"，不在这里判环（职责分离）。
 * 3. **不改入参**：返回新 Map / 新数组。
 *
 * ⚠️ 纯函数、**零 import**（与 `topology.ts` 同构，可被 `shared/protocol.ts` 与迁移脚本共用，
 * 且不得引入 node 内置模块——验收口径见 topology.ts 文件头）。
 *
 * @module dsh-pmboard/domain/queue/transitiveReduction
 */

/** 依赖图：任务 id → 它的前置 id 列表（顺序即原顺序；允许重复与悬空）。 */
export type DependencyGraph = ReadonlyMap<string, readonly string[]>

/** 去重但**保序**（first-wins）——归约后依赖顺序仍与作者写下的一致。 */
function uniq(items: readonly string[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const item of items) {
    if (seen.has(item)) continue
    seen.add(item)
    out.push(item)
  }
  return out
}

/**
 * 从 `start` 出发的全部**严格**前置（传递闭包，不含 start 自身）。
 *
 * 环安全：visited 集合既防重复也防环回绕；即便 start 在环上，也不会把 start 放回结果。
 */
function strictAncestorsOf(start: string, graph: DependencyGraph): Set<string> {
  const seen = new Set<string>()
  const stack: string[] = [...(graph.get(start) ?? [])]
  while (stack.length > 0) {
    const cur = stack.pop() as string
    if (seen.has(cur)) continue
    seen.add(cur)
    for (const dep of graph.get(cur) ?? []) {
      if (!seen.has(dep)) stack.push(dep)
    }
  }
  seen.delete(start)
  return seen
}

/**
 * 把每个任务的依赖列表归约为「直接前置」。
 *
 * 判据：前置 `p` 冗余 ⟺ 该任务还有另一个前置 `q`，且 `p` 能从 `q` 到达
 * （`q → … → p`）。此时 `p→t` 已由 `q → … → p → t` 蕴含，删掉不改变可达性。
 *
 * @param graph 任务 id → 前置列表（含悬空/重复均可）
 * @returns 新 Map：id → 归约后的前置（保序；未变化的任务也原样出现）
 */
export function transitiveReduce(graph: DependencyGraph): Map<string, string[]> {
  // 先规整（去重保序）；悬空节点不需要在 Map 里出现，它们只会作为 dep 字符串被引用。
  const clean = new Map<string, string[]>()
  for (const [id, deps] of graph) clean.set(id, uniq(Array.isArray(deps) ? deps : []))

  const out = new Map<string, string[]>()
  for (const [id, deps] of clean) {
    if (deps.length <= 1) {
      out.set(id, deps)
      continue
    }
    // 该任务所有前置的严格祖先之并 = "已被其它前置覆盖"的集合
    const covered = new Set<string>()
    for (const q of deps) {
      for (const a of strictAncestorsOf(q, clean)) covered.add(a)
    }
    // 只删「存在且有替代路径」的；悬空前置一律保留（见文件头边界 1）
    out.set(id, deps.filter((p) => !(covered.has(p) && clean.has(p))))
  }
  return out
}
