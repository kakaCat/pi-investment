/**
 * critical-path.ts 单测（REQ-260928001915-f978 · t-1f219b · FR-6 · t-868884 研发）
 *
 * 运行（无需浏览器 / 无第三方依赖）：
 *   cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/critical-path.test.ts
 *
 * 覆盖：
 *   ① 验收 DAG（6 节点、两条等长路径 1→2→3→6 / 1→4→5→6，各 3 条边）
 *   ② 拓扑序来源：layer 缺失 / layer 全 0 / layer 倒序 都不影响正确性
 *   ③ edges 兜底：tasks 无 dependsOn 时用第二参 edges 建图
 *   ④ 边界：空图 / 单点 / 孤立分支 / 悬空依赖 / 重复 dependsOn / 重复 id / 畸形条目
 *   ⑤ 降级：环（含自依赖）→ detectCycle 报到 且 findCriticalPath 返回空集
 *   ⑥ 纯函数：不改入参；确定性（两次结果一致）
 *   ⑦ computeNeighbors 上下游 / branchCounts 支线计数 / computeCriticalPath 别名
 *   ⑧ 真实队列 queue.json：关键路径是单链（与 selftest.mjs [3] 同判据）
 *
 * 退出码 0 = 全绿；1 = 有断言失败。
 */
import { readFileSync } from 'node:fs';
import {
  findCriticalPath,
  computeCriticalPath,
  computeNeighbors,
  detectCycle,
  branchCounts,
  type DependencyEdge as Edge,
} from './critical-path';
import { Phase, Side, Role, Status, type CardData } from './card-types';

let pass = 0;
let fail = 0;
const failures: string[] = [];

function check(name: string, cond: boolean, detail?: string): void {
  if (cond) {
    pass += 1;
    console.log('  ok   ' + name);
  } else {
    fail += 1;
    failures.push(name + (detail ? ' — ' + detail : ''));
    console.log('  FAIL ' + name + (detail ? ' — ' + detail : ''));
  }
}

function card(id: string, layer?: number, dependsOn?: string[]): CardData {
  const c: CardData = {
    id,
    title: '任务 ' + id,
    phase: Phase.IMPLEMENT,
    side: Side.BACKEND,
    role: Role.SOLO,
    status: Status.TODO,
  };
  if (layer !== undefined) c.layer = layer;
  if (dependsOn !== undefined) c.dependsOn = dependsOn.slice();
  return c;
}

function sorted(set: Set<string>): string[] {
  return Array.from(set).sort();
}

function sameSet(a: Set<string>, b: Set<string>): boolean {
  return a.size === b.size && Array.from(a).every((x) => b.has(x));
}

/* ---------------- 验收 DAG（父卡 t-1f219b 验收口径） ---------------- */

// 1→2→3→6（3 条边）与 1→4→5→6（3 条边），两条等长最长路径
const ACC_IDS = ['1', '2', '3', '4', '5', '6'];
const ACC_DEP: Record<string, string[]> = {
  '1': [],
  '2': ['1'],
  '3': ['2'],
  '4': ['1'],
  '5': ['4'],
  '6': ['3', '5'],
};
const ACC_LAYER: Record<string, number> = { '1': 0, '2': 1, '3': 2, '4': 1, '5': 2, '6': 3 };
const ACC_EDGES: Edge[] = [
  { from: '1', to: '2' },
  { from: '2', to: '3' },
  { from: '3', to: '6' },
  { from: '1', to: '4' },
  { from: '4', to: '5' },
  { from: '5', to: '6' },
];
const PATH_A = new Set(['1', '2', '3', '6']);
const PATH_B = new Set(['1', '4', '5', '6']);

function accTasks(withLayer = true, withDep = true): CardData[] {
  return ACC_IDS.map((id) => card(id, withLayer ? ACC_LAYER[id] : undefined, withDep ? ACC_DEP[id] : undefined));
}

function inPath(set: Set<string>): Set<string> {
  return sameSet(set, PATH_A) ? PATH_A : PATH_B;
}

function pathEdgeCount(set: Set<string>): number {
  return ACC_EDGES.filter((e) => set.has(e.from) && set.has(e.to)).length;
}

/* ---------------- ① 验收 DAG ---------------- */

console.log('\n[1] 验收 DAG：6 节点 / 两条等长最长路径（各 3 条边）');
const accSet = findCriticalPath(accTasks(), ACC_EDGES);
check('findCriticalPath(tasks, edges) 返回 4 节点路径', accSet.size === 4, 'size=' + accSet.size + ' set=' + sorted(accSet).join(','));
check('结果是两条等长路径之一（1→2→3→6 或 1→4→5→6）', sameSet(accSet, PATH_A) || sameSet(accSet, PATH_B), sorted(accSet).join(','));
check('路径长度 = 3 条边（4 节点）', pathEdgeCount(accSet) === 3, 'edges=' + pathEdgeCount(accSet));
check('包含起点 1 与终点 6', accSet.has('1') && accSet.has('6'));
check('只传 tasks（dependsOn 为源）得到同一条路径', sameSet(findCriticalPath(accTasks()), inPath(accSet)));

/* ---------------- ② 拓扑序来源：不依赖 layer ---------------- */

console.log('\n[2] 拓扑序来自 dependsOn 现算（layer 缺失/写错不影响）');
const base = sorted(findCriticalPath(accTasks(), ACC_EDGES));
check('缺 layer：结果与有 layer 一致', sorted(findCriticalPath(accTasks(false, true), ACC_EDGES)).join(',') === base.join(','));
const allZero = ACC_IDS.map((id) => card(id, 0, ACC_DEP[id]));
check('layer 全 0：结果一致', sorted(findCriticalPath(allZero, ACC_EDGES)).join(',') === base.join(','));
const reversed = ACC_IDS.map((id) => card(id, 3 - ACC_LAYER[id], ACC_DEP[id]));
check('layer 倒序（错误 layer）：结果一致', sorted(findCriticalPath(reversed, ACC_EDGES)).join(',') === base.join(','));

/* ---------------- ③ edges 兜底 ---------------- */

console.log('\n[3] edges 兜底：tasks 无 dependsOn 时用第二参建图');
const bare = ACC_IDS.map((id) => card(id, ACC_LAYER[id]));
const bareSet = findCriticalPath(bare, ACC_EDGES);
check('裸 tasks + edges：得到同一条路径', sorted(bareSet).join(',') === base.join(','), sorted(bareSet).join(','));
check('裸 tasks 不传 edges：无依赖 → 单点路径', findCriticalPath(bare).size === 1);
check('edges 里的悬空边被忽略（to 不存在）', findCriticalPath(bare, ACC_EDGES.concat([{ from: '1', to: 'ghost' }])).has('ghost') === false);

/* ---------------- ④ 边界 ---------------- */

console.log('\n[4] 边界：空图 / 单点 / 孤立 / 悬空 / 重复 / 畸形');
check('空数组 → 空集', findCriticalPath([]).size === 0);
check('空数组 detectCycle → null', detectCycle([]) === null);
check('单点 → {solo}', sameSet(findCriticalPath([card('solo', 0, [])]), new Set(['solo'])));
const island = [card('a', 0, []), card('b', 1, ['a']), card('c', 2, ['b']), card('x', 0, [])];
check('孤立点不干扰最长路径 → {a,b,c}', sameSet(findCriticalPath(island), new Set(['a', 'b', 'c'])), sorted(findCriticalPath(island)).join(','));
const dangling = [card('a', 0, []), card('b', 1, ['a', 'ghost'])];
check('悬空依赖被忽略（不报环）→ {a,b}', sameSet(findCriticalPath(dangling), new Set(['a', 'b'])) && detectCycle(dangling) === null);
const dupDep = [card('a', 0, []), card('b', 1, ['a', 'a'])];
check('重复 dependsOn 去重 → {a,b}', sameSet(findCriticalPath(dupDep), new Set(['a', 'b'])));
const dupId = [card('a', 0, []), card('a', 1, ['ghost'])];
check('重复 id 不抛异常且可算', (() => { try { return findCriticalPath(dupId).size >= 1; } catch { return false; } })());
const malformed = [null, 42, 'x', card('a', 0, [])] as unknown as CardData[];
check('畸形条目（null/数字/字符串）被跳过且不抛', (() => { try { return sameSet(findCriticalPath(malformed), new Set(['a'])); } catch { return false; } })());

/* ---------------- ⑤ 降级：环 ---------------- */

console.log('\n[5] 降级：循环依赖 → 空集（不抛异常）');
const cycle3 = [card('x', 0, ['z']), card('y', 1, ['x']), card('z', 2, ['y'])];
check('detectCycle 抓到 3 节点环', (detectCycle(cycle3) || []).length === 3, String(detectCycle(cycle3)));
check('有环时 findCriticalPath 返回空集', findCriticalPath(cycle3).size === 0);
const selfDep = [card('a', 0, ['a'])];
check('自依赖也算环（detectCycle=[a]）', JSON.stringify(detectCycle(selfDep)) === JSON.stringify(['a']));
check('自依赖时 findCriticalPath 返回空集', findCriticalPath(selfDep).size === 0);

/* ---------------- ⑥ 纯函数与确定性 ---------------- */

console.log('\n[6] 纯函数：不改入参 / 结果确定');
const frozen = accTasks();
const before = JSON.stringify(frozen.map((t) => t.dependsOn));
findCriticalPath(frozen, ACC_EDGES);
check('调用后入参 dependsOn 逐字未变', JSON.stringify(frozen.map((t) => t.dependsOn)) === before);
check('两次调用结果一致', sorted(findCriticalPath(accTasks(), ACC_EDGES)).join(',') === sorted(findCriticalPath(accTasks(), ACC_EDGES)).join(','));

/* ---------------- ⑦ 上下游 / 支线 / 别名 ---------------- */

console.log('\n[7] computeNeighbors / branchCounts / computeCriticalPath 别名');
const nbTasks = [card('a', 0, []), card('b', 1, ['a']), card('c', 2, ['b']), card('d', 2, ['b'])];
const nb = computeNeighbors(nbTasks, 'b');
check('B 的上游 = {a}', nb.up.size === 1 && nb.up.has('a'));
check('B 的下游 = {c,d}', nb.down.size === 2 && nb.down.has('c') && nb.down.has('d'));
check('B 不在自己的上下游里', !nb.up.has('b') && !nb.down.has('b'));
check('未知 targetId → 两个空集', (() => { const e = computeNeighbors(nbTasks, 'zzz'); return e.up.size === 0 && e.down.size === 0; })());
check('computeCriticalPath 是 findCriticalPath 的别名', computeCriticalPath === findCriticalPath);
check('acceptance DAG 上：别名结果一致', sameSet(computeCriticalPath(accTasks(), ACC_EDGES), accSet));
const bc = branchCounts(ACC_EDGES, PATH_A);
check('branchCounts(主线=1→2→3→6) = {1:1, 6:1}', bc['1'] === 1 && bc['6'] === 1 && Object.keys(bc).length === 2, JSON.stringify(bc));
check('主线内部边不计支线', branchCounts(ACC_EDGES, PATH_B)['1'] === 1 && branchCounts(ACC_EDGES, PATH_B)['6'] === 1);

/* ---------------- ⑧ 真实队列 ---------------- */

console.log('\n[8] 真实队列 queue.json：关键路径是单链');
const QUEUE_CANDIDATES = ['queue.json', 'docs/requirements/REQ-260928001915-f978/queue.json'];
let queueRaw: { tasks: CardData[] } | null = null;
for (const p of QUEUE_CANDIDATES) {
  try { queueRaw = JSON.parse(readFileSync(p, 'utf8')); break; } catch { /* 试下一个 */ }
}
check('真实队列可读取', queueRaw !== null, 'cwd=' + process.cwd());
if (queueRaw) {
  const tasks = queueRaw.tasks;
  const set = findCriticalPath(tasks);
  const byId = new Map<string, CardData>(tasks.map((t) => [t.id, t]));
  const has = (id: string): boolean => set.has(id);
  const starts = Array.from(set).filter((id) => !((byId.get(id) || {}).dependsOn || []).some(has));
  const orphan = Array.from(set).filter((id) => id !== starts[0] && !((byId.get(id) || {}).dependsOn || []).some(has));
  const layers = Array.from(set).map((id) => (byId.get(id) || {}).layer);
  check('真实队列：关键路径是单链（起点唯一 / 每节点有集合内前驱 / layer 互不相同）',
    set.size >= 1 && starts.length === 1 && orphan.length === 0 && new Set(layers).size === layers.length,
    'size=' + set.size + ' starts=' + starts.length + ' orphan=' + orphan.length);
  check('真实队列：关键路径节点都真实存在', Array.from(set).every((id) => byId.has(id)));
}

/* ---------------- 汇总 ---------------- */

console.log('\n' + '='.repeat(56));
if (fail === 0) {
  console.log('全部通过：' + pass + ' / ' + (pass + fail));
  process.exit(0);
}
console.log('失败 ' + fail + ' 项 / 共 ' + (pass + fail) + ' 项：');
for (const f of failures) console.log('  - ' + f);
process.exit(1);
