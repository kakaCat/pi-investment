/**
 * 关键路径与上下游遍历（REQ-260928001915-f978 · t-1f219b · FR-6 / FR-4 / FR-5）
 * 研发子卡：t-868884
 *
 * 本文件是 DAG 图算法的唯一实现处，四个函数全部为纯函数
 * （不依赖 DOM、不 import node 内置模块、不改入参、无时钟/随机数）：
 *
 * - findCriticalPath()  DAG 最长路径（Kahn 拓扑排序 + 动态规划 + prev 回溯）→ Set<taskId>
 * - computeNeighbors()  某节点的全部可达前驱（上游）与后继（下游）
 * - detectCycle()       循环依赖检测（Kahn 剥皮法）
 * - branchCounts()      主线折叠时每个关键节点的支线边数（「+N 支线」徽标）
 *
 * 关于「拓扑序从哪来」（本卡相对初版的关键修正）：
 *   初版按 task.layer 升序排完就直接 DP。layer 是队列落盘时的**派生字段**，
 *   一旦缺失（降级数据）或写错，DP 会读到「尚未计算的前驱 dist」，静默算出偏短的
 *   路径——而关键路径算错不会有任何报错。本版改为**在函数内用 Kahn 算法从 dependsOn
 *   现算拓扑序**：① 与需求口径「从入度为 0 的节点开始」（requirement.md §FR-6 第 77 行）
 *   逐字一致；② 不再依赖 layer 是否可信；③ 同一遍遍历顺带拿到环上节点做降级。
 *   layer 不参与正确性判断。
 *
 * 输入契约（design/data-model.md L159 / architecture.md L138-141）：
 *   - **dependsOn 是数据源头**；edges 是其展开结果、本只用于画线。
 *   - 仅当某任务的 dependsOn 缺失/为空时，本文件才用传入的 edges 为该节点兜底补前驱，
 *     以兼容 findCriticalPath(tasks, edges) 这种「结构全在 edges 里」的调用形态。
 *   - 悬空依赖（指向不存在的任务）按**忽略**处理，不当作环——否则一条脏引用会把整张
 *     图报成 CIRCULAR；检出职责在 validateQueue / V-3。
 */

import type { CardData } from './card-types';

/** 依赖边（与 card-types.ts 的 QueueData.edges 同形）。用 DependencyEdge 而非 Edge：
 * integration.ts 对 critical-path / edge-renderer 都做 export *，重名会被 TS2308 拦下。 */
export interface DependencyEdge {
  /** 前置任务 id */
  from: string;
  /** 后继任务 id */
  to: string;
}

/** 依赖图内部表示 */
interface DepGraph {
  /** 图内任务 id（输入顺序，去重后的首个为准） */
  ids: string[];
  /** id -> 任务对象 */
  byId: Map<string, CardData>;
  /** id -> 去重后的直接前驱（只含图内节点） */
  preds: Map<string, string[]>;
  /** id -> 去重后的直接后继（只含图内节点） */
  succs: Map<string, string[]>;
  /** id -> 入度（只计图内前驱；自依赖计 1，用于判环） */
  indeg: Map<string, number>;
}

/** 运行时形状守卫：畸形队列（JSON.parse 产物）里可能混着 null/数字/字符串 */
function isTaskLike(value: unknown): value is CardData {
  return value !== null && typeof value === 'object';
}

/**
 * 构建依赖图。以**去重后的首个同 id 任务**为准（与 domain/queue/topology.ts 的口径一致：
 * 重复 id 不在这里报错，由 V-2 负责；这里只保证可算且不把两个任务算成一个）。
 */
function buildGraph(tasks: readonly CardData[], edges?: readonly DependencyEdge[]): DepGraph {
  const ids: string[] = [];
  const byId = new Map<string, CardData>();
  for (const task of tasks) {
    if (!isTaskLike(task) || typeof task.id !== 'string' || task.id.length === 0) continue;
    if (byId.has(task.id)) continue;
    byId.set(task.id, task);
    ids.push(task.id);
  }

  const preds = new Map<string, string[]>();
  const succs = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  for (const id of ids) {
    preds.set(id, []);
    succs.set(id, []);
    indeg.set(id, 0);
  }

  const addEdge = (from: string, to: string): void => {
    if (!byId.has(from) || !byId.has(to)) return; // 悬空依赖：忽略
    const incoming = preds.get(to)!;
    if (incoming.indexOf(from) >= 0) return; // 重复 dependsOn：去重
    incoming.push(from);
    succs.get(from)!.push(to);
    indeg.set(to, indeg.get(to)! + 1);
  };

  for (const id of ids) {
    const task = byId.get(id)!;
    const deps = Array.isArray(task.dependsOn) ? task.dependsOn : [];
    if (deps.length > 0) {
      for (const dep of deps) {
        if (typeof dep === 'string' && dep.length > 0) addEdge(dep, id);
      }
      continue;
    }
    // dependsOn 缺失/为空：才用 edges 兜底（只取指向本节点的入边）
    if (Array.isArray(edges)) {
      for (const e of edges) {
        if (!e || typeof e.from !== 'string' || typeof e.to !== 'string') continue;
        if (e.to === id) addEdge(e.from, e.to);
      }
    }
  }

  return { ids, byId, preds, succs, indeg };
}

/**
 * Kahn 拓扑排序：从入度为 0 的节点开始逐层剥皮。
 *
 * @returns order = 拓扑序（前驱必在后继之前）；cycle = 剥不掉的节点（入度仍 > 0），
 *          即环上节点，按输入顺序返回。
 * 注：用下标游标而非 Array.shift()，整体 O(V+E)。
 */
function topoOrder(graph: DepGraph): { order: string[]; cycle: string[] } {
  const indeg = new Map(graph.indeg);
  const queue: string[] = graph.ids.filter((id) => indeg.get(id) === 0);
  const order: string[] = [];
  for (let head = 0; head < queue.length; head += 1) {
    const id = queue[head]!;
    order.push(id);
    for (const next of graph.succs.get(id)!) {
      const left = indeg.get(next)! - 1;
      indeg.set(next, left);
      if (left === 0) queue.push(next);
    }
  }
  const cycle = graph.ids.filter((id) => indeg.get(id)! > 0);
  return { order, cycle };
}

/**
 * 检测循环依赖（Kahn 剥皮）。
 * @returns 有环时返回环上节点 id 列表（含自依赖），无环返回 null
 */
export function detectCycle(tasks: readonly CardData[]): string[] | null {
  const { cycle } = topoOrder(buildGraph(tasks));
  return cycle.length > 0 ? cycle : null;
}

/**
 * 关键路径 = DAG 最长路径。
 *
 * 算法（requirement.md §FR-6 / architecture.md §关键路径算法）：
 * 1. Kahn 拓扑排序（从入度为 0 的节点开始）——保证处理某节点时其全部前驱已算完
 * 2. 动态规划：dist[id] = 1 + max(dist[前驱])（无前驱为 1），并记录 prev[id]
 * 3. 取 dist 最大的节点为终点（等长取拓扑序更先者 → 结果确定）
 * 4. 沿 prev 回溯 → 关键路径节点集合
 *
 * @param tasks 任务列表（须含 id/dependsOn；dependsOn 缺失时才用 edges 兜底）
 * @param edges 依赖边（可选，仅用于给 dependsOn 缺失的节点补前驱）
 * @returns 关键路径节点 id 集合；空图或有环时返回**空集**（不抛异常，
 *          由调用方负责提示——design/interfaces.md L116-118）
 */
export function findCriticalPath(tasks: readonly CardData[], edges?: readonly DependencyEdge[]): Set<string> {
  const result = new Set<string>();
  const graph = buildGraph(tasks, edges);
  if (graph.ids.length === 0) return result;

  const { order, cycle } = topoOrder(graph);
  if (cycle.length > 0) return result; // 有环：无可定义的最长路径

  const dist = new Map<string, number>();
  const prev = new Map<string, string | null>();
  for (const id of order) {
    dist.set(id, 1);
    prev.set(id, null);
    for (const p of graph.preds.get(id)!) {
      const candidate = dist.get(p)! + 1;
      if (candidate > dist.get(id)!) {
        dist.set(id, candidate);
        prev.set(id, p);
      }
    }
  }

  let end: string | null = null;
  let best = 0;
  for (const id of order) {
    const d = dist.get(id)!;
    if (d > best) {
      best = d;
      end = id;
    }
  }

  let cur: string | null = end;
  while (cur !== null) {
    result.add(cur);
    cur = prev.get(cur) ?? null;
  }
  return result;
}

/**
 * 设计文档（interfaces.md L102）中的函数名 computeCriticalPath 的别名。
 * 保留两个名字：findCriticalPath 是任务卡/自测口径，computeCriticalPath 是设计口径。
 */
export const computeCriticalPath = findCriticalPath;

/**
 * 上下游遍历。
 * @returns up = 全部可达前驱（上游）；down = 全部可达后继（下游）；均不含自身。
 *          未知 targetId 返回两个空集。
 */
export function computeNeighbors(
  tasks: readonly CardData[],
  targetId: string,
): { up: Set<string>; down: Set<string> } {
  const graph = buildGraph(tasks);
  const up = new Set<string>();
  const down = new Set<string>();
  if (!graph.byId.has(targetId)) return { up, down };

  const walk = (seeds: string[], adjacency: Map<string, string[]>, out: Set<string>): void => {
    const stack = seeds.slice();
    while (stack.length > 0) {
      const id = stack.pop()!;
      for (const next of adjacency.get(id) ?? []) {
        if (next === targetId || out.has(next)) continue;
        out.add(next);
        stack.push(next);
      }
    }
  };

  walk([targetId], graph.preds, up);
  walk([targetId], graph.succs, down);
  return { up, down };
}

/**
 * 主线折叠时，每个关键路径节点被折叠掉的支线边数（用于卡角「+N 支线」徽标）。
 * 主线内部的边（两端都在 critSet）不计支线。
 */
export function branchCounts(
  edges: readonly DependencyEdge[],
  critSet: ReadonlySet<string>,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const e of edges) {
    if (!e || typeof e.from !== 'string' || typeof e.to !== 'string') continue;
    const fromCrit = critSet.has(e.from);
    const toCrit = critSet.has(e.to);
    if (fromCrit && toCrit) continue;
    if (fromCrit) out[e.from] = (out[e.from] ?? 0) + 1;
    if (toCrit && !fromCrit) out[e.to] = (out[e.to] ?? 0) + 1;
  }
  return out;
}
