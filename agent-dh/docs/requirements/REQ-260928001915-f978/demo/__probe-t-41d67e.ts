/**
 * 接口联调探针（REQ-260928001915-f978 · t-1f219b · FR-6 · 联调子卡 t-41d67e）
 *
 * 目的：对 `critical-path.ts` 的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，
 *       并验证它在下游集成链路（integration.ts / renderDagHtml）里被正确消费。
 * 运行：cd docs/requirements/REQ-260928001915-f978/demo && npx tsx __probe-t-41d67e.ts
 *
 * 本探针是结论族联调的取证脚本（只读被测模块，不修改任何交付物）。
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  findCriticalPath,
  computeCriticalPath,
  detectCycle,
  branchCounts,
  type DependencyEdge,
} from './critical-path';
import { validateQueueFile, renderDagHtml, resolveTasks, type DagData, type DagState } from './integration';
import { Phase, Side, Role, Status, type CardData } from './card-types';

const HERE = dirname(fileURLToPath(import.meta.url));
const QUEUE_PATH = resolve(HERE, '..', 'queue.json');

let pass = 0;
let fail = 0;
function row(name: string, expected: string, actual: string, ok: boolean): void {
  if (ok) pass += 1; else fail += 1;
  console.log((ok ? '  PASS' : '  FAIL') + ' | ' + name + '\n          期望= ' + expected + '\n          实际= ' + actual);
}
const sorted = (s: Set<string>): string[] => Array.from(s).sort();
const sameSet = (a: Set<string>, b: string[]): boolean => a.size === b.length && b.every((x) => a.has(x));

/** 被测接口最简任务构造器 */
function card(id: string, dependsOn?: string[]): CardData {
  const c: CardData = { id, title: '任务 ' + id, phase: Phase.IMPLEMENT, side: Side.BACKEND, role: Role.SOLO, status: Status.TODO };
  if (dependsOn) c.dependsOn = dependsOn.slice();
  return c;
}

/**
 * 独立参考实现（交叉验证用）：朴素 DFS 记忆化算最长路径。
 * 与生产的 Kahn 拓扑 + DP 是完全不同的写法，用来排除「同一个错两处复现」。
 */
function refCriticalPath(tasks: CardData[]): Set<string> {
  const memo = new Map<string, number>();
  const next = new Map<string, string | null>();
  const succsOf = (id: string): string[] => {
    const out: string[] = [];
    for (const t of tasks) if (Array.isArray(t.dependsOn) && t.dependsOn.indexOf(id) >= 0) out.push(t.id);
    return out;
  };
  const dfs = (id: string): number => {
    if (memo.has(id)) return memo.get(id)!;
    let best = 1;
    let bestNext: string | null = null;
    for (const s of succsOf(id)) {
      const v = 1 + dfs(s);
      if (v > best) { best = v; bestNext = s; }
    }
    memo.set(id, best);
    next.set(id, bestNext);
    return best;
  };
  const starts = tasks.filter((t) => !Array.isArray(t.dependsOn) || t.dependsOn.length === 0);
  let startId: string | null = null;
  let bestLen = 0;
  for (const t of starts) {
    const v = dfs(t.id);
    if (v > bestLen) { bestLen = v; startId = t.id; }
  }
  const out = new Set<string>();
  for (let cur: string | null = startId; cur !== null; cur = next.get(cur) ?? null) out.add(cur);
  return out;
}

console.log('=== 接口联调：critical-path 接口（findCriticalPath / computeCriticalPath） ===');
console.log('接口签名（交付）: (tasks: CardData[], edges?: DependencyEdge[]) => Set<string>');
console.log('设计口径（interfaces.md L102-118）: computeCriticalPath(tasks: StageTaskRef[]) => Set<string>');
console.log('');

/* ---- 接口形状：存在性 / 别名 / 返回类型 ---- */
console.log('[S0] 接口形状与别名');
row('findCriticalPath 是函数', 'typeof === function', typeof findCriticalPath, typeof findCriticalPath === 'function');
row('computeCriticalPath 是同一函数引用', '=== findCriticalPath', computeCriticalPath === findCriticalPath ? '同一引用' : '不同', computeCriticalPath === findCriticalPath);
const emptyRet = findCriticalPath([]);
row('返回类型为 Set<string>', 'Set 实例且 size=0', String(emptyRet instanceof Set) + ' size=' + emptyRet.size, emptyRet instanceof Set && emptyRet.size === 0);

/* ---- R1：验收 DAG（两条等长最长路径，链路长度 4 节点 = 3 边） ---- */
console.log('\n[R1] 验收 DAG（6 节点、两条等长路径 1→2→3→6 / 1→4→5→6）');
const accDep: Record<string, string[]> = { '1': [], '2': ['1'], '3': ['2'], '4': ['1'], '5': ['4'], '6': ['3', '5'] };
const accTasks = Object.keys(accDep).map((id) => card(id, accDep[id]));
const accEdges: DependencyEdge[] = [
  { from: '1', to: '2' }, { from: '2', to: '3' }, { from: '3', to: '6' },
  { from: '1', to: '4' }, { from: '4', to: '5' }, { from: '5', to: '6' },
];
const r1 = findCriticalPath(accTasks, accEdges);
row('R1 findCriticalPath(tasks, edges)', 'size=4 且 ∈ {1,2,3,6} | {1,4,5,6}',
  'size=' + r1.size + ' {' + sorted(r1).join(',') + '}',
  r1.size === 4 && (sameSet(r1, ['1', '2', '3', '6']) || sameSet(r1, ['1', '4', '5', '6'])));
const r1b = findCriticalPath(accTasks); // 只传 tasks，dependsOn 为源
row('R1b 只传 tasks（dependsOn 为源）', '与 R1 同一集合', '{' + sorted(r1b).join(',') + '}', sameSet(r1b, sorted(r1)));

/* ---- R2：链 a→b→c + 孤立 x ---- */
console.log('\n[R2] 链 + 孤立点');
const r2 = findCriticalPath([card('a', []), card('b', ['a']), card('c', ['b']), card('x', [])]);
row('R2 链 a→b→c 加孤立 x', '{a,b,c}', '{' + sorted(r2).join(',') + '}', sameSet(r2, ['a', 'b', 'c']));

/* ---- R3：空图 ---- */
console.log('\n[R3] 空图');
const r3 = findCriticalPath([]);
row('R3 tasks=[]', 'size=0（不抛异常）', 'size=' + r3.size, r3.size === 0);

/* ---- R4：环降级 ---- */
console.log('\n[R4] 环 x→y→z→x（降级）');
const cyc = [card('x', ['z']), card('y', ['x']), card('z', ['y'])];
const r4 = findCriticalPath(cyc);
const cy = detectCycle(cyc);
row('R4 有环', '关键路径=空集 且 detectCycle=3 节点', 'size=' + r4.size + ' cycle=' + (cy ? cy.length : 0), r4.size === 0 && (cy ?? []).length === 3);

/* ---- R5：真实 queue.json，与独立参考实现交叉验证 ---- */
console.log('\n[R5] 真实 queue.json（端到端）');
const queue = JSON.parse(readFileSync(QUEUE_PATH, 'utf8')) as {
  requirement_id?: string; tasks: CardData[]; edges: DependencyEdge[]; ready: string[];
};
const real = findCriticalPath(queue.tasks);
const expected = refCriticalPath(queue.tasks);
row('R5a findCriticalPath(queue.tasks) == 独立 DFS 参考实现',
  '{' + sorted(expected).join(',') + '}', '{' + sorted(real).join(',') + '}',
  real.size === expected.size && sorted(real).join(',') === sorted(expected).join(','));

/* ---- R6：下游集成消费（integration.ts） ---- */
console.log('\n[R6] 下游集成链路 integration.ts');
const val = validateQueueFile(queue);
row('R6a validateQueueFile(真实 queue).passed', 'true', String(val.passed), val.passed === true);
const dagData: DagData = { tasks: queue.tasks, edges: queue.edges, ready: queue.ready };
const focusState: DagState = { dir: 'vertical', crit: true, focus: true, pinned: null };
const focusHtml = renderDagHtml(dagData, focusState);
const focusNodes = (focusHtml.match(/class="node/g) ?? []).length;
const focusCrit = (focusHtml.match(/class="node crit"/g) ?? []).length;
row('R6b focus=只看主线：渲染节点数 == 关键路径节点数', String(real.size), String(focusNodes), focusNodes === real.size);
row('R6c focus 模式全部节点带 crit 类', String(real.size), String(focusCrit), focusCrit === real.size);
const fullState: DagState = { dir: 'vertical', crit: true, focus: false, pinned: null };
const fullHtml = renderDagHtml(dagData, fullState);
const fullNodes = (fullHtml.match(/class="node/g) ?? []).length;
const fullCritNodes = (fullHtml.match(/class="node crit"/g) ?? []).length;
row('R6d focus=展开全图：渲染全部任务节点', String(queue.tasks.length), String(fullNodes), fullNodes === queue.tasks.length);
row('R6e 展开模式下带 crit 类节点数 == 关键路径节点数', String(real.size), String(fullCritNodes), fullCritNodes === real.size);

/* ---- R7：branchCounts（主线折叠「+N 支线」数据） ---- */
console.log('\n[R7] branchCounts 接口');
const bc = branchCounts(accEdges, new Set(['1', '2', '3', '6']));
row('R7 branchCounts(主线 1-2-3-6) 只计主线外的边', '{"1":1,"6":1}', JSON.stringify(bc),
  bc['1'] === 1 && bc['6'] === 1 && Object.keys(bc).length === 2 && bc['2'] === undefined && bc['3'] === undefined);

/* ---- R8：契约与边界（纯函数 / 兜底 / 降级） ---- */
console.log('\n[R8] 契约与边界');
const frozen = [card('a', []), card('b', ['a']), card('c', ['b'])];
const snapshot = JSON.stringify(frozen);
findCriticalPath(frozen, accEdges);
row('R8a 不修改入参（纯函数）', snapshot, JSON.stringify(frozen), JSON.stringify(frozen) === snapshot);
const callA = sorted(findCriticalPath(accTasks, accEdges)).join(',');
const callB = sorted(findCriticalPath(accTasks, accEdges)).join(',');
row('R8b 幂等/确定性（两次调用一致）', callA, callB, callA === callB);
const bare = [card('p'), card('q')]; // 无 dependsOn
const bareSet = findCriticalPath(bare, [{ from: 'p', to: 'q' }]);
row('R8c dependsOn 缺失时用 edges 兜底', '{p,q}', '{' + sorted(bareSet).join(',') + '}', sameSet(bareSet, ['p', 'q']));
const dangling = [card('a', []), card('b', ['a', 'ghost'])];
row('R8d 悬空依赖被忽略（不报环）', '{a,b} 且 detectCycle=null', '{' + sorted(findCriticalPath(dangling)).join(',') + '} cycle=' + String(detectCycle(dangling)),
  sameSet(findCriticalPath(dangling), ['a', 'b']) && detectCycle(dangling) === null);
const dupDep = [card('a', []), card('b', ['a', 'a'])];
row('R8e 重复 dependsOn 去重', '{a,b}', '{' + sorted(findCriticalPath(dupDep)).join(',') + '}', sameSet(findCriticalPath(dupDep), ['a', 'b']));
const malformed = [card('a', []), null, 42, 'x'] as unknown as CardData[];
let noThrow = true;
let malformedSet = new Set<string>();
try { malformedSet = findCriticalPath(malformed); } catch { noThrow = false; }
row('R8f 畸形条目被跳过且不抛', '{a}', '{' + sorted(malformedSet).join(',') + '} noThrow=' + noThrow, noThrow && sameSet(malformedSet, ['a']));

/* ---- R9：resolveTasks 后结果不变（下游会先补 role/kids 再算） ---- */
console.log('\n[R9] 下游前置变换 resolveTasks 不改变关键路径');
const resolved = resolveTasks(queue.tasks);
const realAfterResolve = findCriticalPath(resolved);
row('R9 resolveTasks(queue) 后 critSet 不变', '{' + sorted(real).join(',') + '}', '{' + sorted(realAfterResolve).join(',') + '}',
  sorted(real).join(',') === sorted(realAfterResolve).join(','));

/* ---- 台账：错误处理契约（设计 vs 实现） ---- */
console.log('\n[S1] 设计契约「循环依赖 → 返回空 Set + 控制台错误」：返回空 Set ✓；控制台错误由');
console.log('     detectCycle 暴露 + renderDagHtml 渲染 "DAG 存在循环依赖"（findCriticalPath 自身为纯函数，不 console）');
const cycHtml = renderDagHtml({ tasks: cyc, edges: [], ready: [] }, fullState);
row('S1 有环时 renderDagHtml 渲染错误提示', "包含 'DAG 存在循环依赖'", cycHtml.slice(0, 60),
  cycHtml.indexOf('DAG 存在循环依赖') >= 0);

console.log('\n---------------------------------------------');
console.log('联调结果: ' + (fail === 0 ? '全部一致 PASS ' + pass + '/' + (pass + fail) : 'FAIL ' + fail + '/' + (pass + fail)));
process.exit(fail === 0 ? 0 : 1);
