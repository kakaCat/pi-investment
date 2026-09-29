/**
 * integration.ts 端到端集成测试（REQ-260928001915-f978 · 父卡 t-144707 · 研发子卡 t-cf42de）
 *
 * 运行（无需浏览器 / 无第三方依赖；cwd 在本需求目录或仓库根均可）：
 *   cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/integration.test.ts
 *
 * 与 selftest.mjs 的分工：selftest 逐模块（布局/卡片/边线/交互…）断言，
 * 本文件只走**集成入口**（validateQueueFile → resolveTasks → renderDagHtml /
 * createDagViewer），用**四档真实队列文件**逐 FR 验收主渲染流程：
 *   FR-1 四轴类型：resolveTasks 从 parentId/子卡补出 role=parent/child/solo，父卡带 kids
 *   FR-2 卡片渲染：renderDagHtml 每张卡都有 ID/标题/类型徽标/状态底色，卡数 = 任务数
 *   FR-3 布局：createDagViewer.layout() 给每个可见节点坐标
 *   FR-4 边线：renderDagHtml 内含 SVG path 且条数 = 队列 edges 数
 *   FR-5 交互：createDagViewer 绑事件；切方向/只看主线后重绘不抛异常；destroy 解绑
 *   FR-6 关键路径：findCriticalPath ⊆ 任务集；只看主线节点数收缩到关键路径
 *   FR-7 子卡链：父卡渲染 card-chain，条数 = 父卡数
 * 数据集：本需求真实队列 / 小图 12 卡 / 中图 20 卡 / 压力 65 卡（小—中—压三档覆盖）。
 *
 * 退出码 0 = 全绿；1 = 有断言失败。
 */
import { readFileSync } from 'node:fs';
import { basename, dirname, join } from 'node:path';

import {
  createDagViewer,
  renderDagHtml,
  validateQueueFile,
  resolveTasks,
  findCriticalPath,
  detectCycle,
  type DagData,
  type DagState,
} from './integration';
import type { CardData } from './card-types';

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

/* ---------------- 真实队列定位（cwd 无关） ---------------- */

interface RawQueue {
  requirement_id?: string;
  tasks: CardData[];
  edges: Array<{ from: string; to: string }>;
  ready: string[];
}

function loadQueue(req: string): RawQueue | null {
  const candidates = [
    join(process.cwd(), 'queue.json'),                              // cwd = 本需求目录
    join(process.cwd(), '..', req, 'queue.json'),                   // cwd = 本需求目录，链到兄弟需求
    join(process.cwd(), 'docs', 'requirements', req, 'queue.json'), // cwd = 仓库根
  ];
  for (const p of candidates) {
    // 防串档：候选文件所在目录名必须等于请求的 req——否则「cwd/queue.json」在本需求目录下
    // 会对任何 req 都命中本需求队列，跨需求校验变成自欺。
    if (basename(dirname(p)) !== req) continue;
    try {
      return JSON.parse(readFileSync(p, 'utf8')) as RawQueue;
    } catch {
      /* 试下一个 */
    }
  }
  return null;
}

const DATASETS = [
  { key: 'd0', req: 'REQ-260928001915-f978', label: '本需求 · 真实队列' },
  { key: 'd1', req: 'REQ-260922213356-4a45', label: '小图 · 12 卡' },
  { key: 'd2', req: 'REQ-6f39b5', label: '中图 · 20 卡' },
  { key: 'd3', req: 'REQ-260924213231-b1c4', label: '压力 · 65 卡' },
];

/* ---------------- 假 canvas / 假 2D 上下文（Node 里跑通 Canvas 后端） ---------------- */

interface FakeCalls {
  fillText: number;
  fillRect: number;
  arc: number;
  bezierCurveTo: number;
  stroke: number;
}

function makeCtx(): { _calls: FakeCalls } & Record<string, unknown> {
  const calls: FakeCalls = { fillText: 0, fillRect: 0, arc: 0, bezierCurveTo: 0, stroke: 0 };
  const ctx = {
    globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1, font: '',
    textAlign: 'left', textBaseline: 'alphabetic', lineCap: 'butt',
    save() {}, restore() {}, beginPath() {}, closePath() {}, moveTo() {}, lineTo() {},
    quadraticCurveTo() {}, setTransform() {}, setLineDash() {}, clip() {}, clearRect() {},
    bezierCurveTo() { calls.bezierCurveTo += 1; },
    stroke() { calls.stroke += 1; },
    fill() {},
    fillRect() { calls.fillRect += 1; },
    fillText() { calls.fillText += 1; },
    arc() { calls.arc += 1; },
    measureText(t: string) { return { width: String(t).length * 6 }; },
    _calls: calls,
  };
  return ctx as unknown as { _calls: FakeCalls } & Record<string, unknown>;
}

interface FakeCanvas {
  width: number;
  height: number;
  style: Record<string, string>;
  parentElement: { clientWidth: number };
  getContext(): unknown;
  getBoundingClientRect(): { left: number; top: number; width: number; height: number };
  addEventListener(type: string, fn: (ev: unknown) => void): void;
  removeEventListener(type: string, fn: (ev: unknown) => void): void;
  hasListener(type: string): boolean;
}

function makeCanvas(ctx: unknown, width: number): FakeCanvas {
  const listeners: Record<string, Array<(ev: unknown) => void>> = {};
  return {
    width: 0, height: 0, style: {} as Record<string, string>,
    parentElement: { clientWidth: width },
    getContext() { return ctx; },
    getBoundingClientRect() { return { left: 0, top: 0, width: 900, height: 600 }; },
    addEventListener(type: string, fn: (ev: unknown) => void) {
      (listeners[type] = listeners[type] || []).push(fn);
    },
    removeEventListener(type: string, fn: (ev: unknown) => void) {
      listeners[type] = (listeners[type] || []).filter((f) => f !== fn);
    },
    hasListener(type: string) { return (listeners[type] || []).length > 0; },
  };
}

const countOf = (s: string, re: RegExp): number => (s.match(re) || []).length;
const BASE_STATE: DagState = { dir: 'vertical', crit: false, focus: false, pinned: null };

/* ---------------- 逐档真实队列：走完整集成主流程 ---------------- */

const loadedCounts: number[] = [];

DATASETS.forEach((ds) => {
  console.log('\n[' + ds.key + '] ' + ds.label + '（' + ds.req + '）');
  const q = loadQueue(ds.req);
  check(ds.key + ' 真实队列文件可读取', q !== null, 'cwd=' + process.cwd());
  if (!q) return;

  const tasks = q.tasks;
  const edges = q.edges || [];
  const ready = q.ready || [];
  loadedCounts.push(tasks.length);

  // 集成入口 ①：结构/一致性校验（V-1..V-6）
  const val = validateQueueFile(q);
  check(ds.key + ' 真实队列通过 V-1..V-6 校验', val.passed === true,
    JSON.stringify(val.issues.slice(0, 3)));
  check(ds.key + ' 无循环依赖', detectCycle(tasks) === null);

  // 集成入口 ②：派生角色（FR-1）
  const resolved = resolveTasks(tasks);
  const parentIds = new Set(tasks.filter((t) => t.parentId).map((t) => t.parentId));
  const parentN = resolved.filter((t) => t.role === 'parent').length;
  const childN = resolved.filter((t) => t.role === 'child').length;
  const soloN = resolved.filter((t) => t.role === 'solo').length;
  const childTasks = tasks.filter((t) => t.parentId).length;
  check(ds.key + ' FR-1 角色三分覆盖且互斥（parent/child/solo）',
    parentN === parentIds.size && childN === childTasks && parentN + childN + soloN === tasks.length,
    'parent=' + parentN + '/' + parentIds.size + ' child=' + childN + '/' + childTasks + ' solo=' + soloN);
  check(ds.key + ' FR-1 父卡的 kids 非空', resolved
    .filter((t) => t.role === 'parent')
    .every((t) => Array.isArray(t.kids) && t.kids.length > 0));

  // 集成入口 ③：DOM/SVG 渲染（FR-2/3/4/7）
  const dag: DagData = { tasks, edges, ready };
  const html = renderDagHtml(dag, BASE_STATE);
  check(ds.key + ' FR-2 每张卡都有 ID/标题/类型徽标/状态底色',
    html.indexOf('card-id') >= 0 && html.indexOf('card-title') >= 0 &&
    html.indexOf('chip-type') >= 0 && html.indexOf('data-status') >= 0);
  const cardN = countOf(html, /class="card"/g);
  check(ds.key + ' FR-2 卡数 = 任务数', cardN === tasks.length, 'card=' + cardN + ' tasks=' + tasks.length);
  const nodeN = countOf(html, /class="node/g);
  check(ds.key + ' FR-3 节点数 = 任务数', nodeN === tasks.length, 'node=' + nodeN + ' tasks=' + tasks.length);
  const edgeN = countOf(html, /data-from="/g);
  check(ds.key + ' FR-4 SVG 边线条数 = 队列 edges 数',
    html.indexOf('<svg') >= 0 && html.indexOf('<path') >= 0 && edgeN === edges.length,
    'path=' + edgeN + ' edges=' + edges.length);
  const chainN = countOf(html, /card-chain/g);
  check(ds.key + ' FR-7 子卡链条数 = 父卡数', chainN === parentN, 'chain=' + chainN + ' parent=' + parentN);
  const readyN = countOf(html, /ready-dot/g);
  check(ds.key + ' FR-2 ready 绿点 = 队列 ready[] 数', readyN === ready.length,
    'dot=' + readyN + ' ready=' + ready.length);

  // 集成入口 ④：关键路径 + 只看主线（FR-6）
  const crit = findCriticalPath(tasks);
  const ids = new Set(tasks.map((t) => t.id));
  check(ds.key + ' FR-6 关键路径 ⊆ 任务集且非空',
    crit.size >= 1 && Array.from(crit).every((id) => ids.has(id)), 'size=' + crit.size);
  const focusHtml = renderDagHtml(dag, { dir: 'vertical', crit: false, focus: true, pinned: null });
  const focusN = countOf(focusHtml, /class="node/g);
  check(ds.key + ' FR-6 只看主线收缩到关键路径', focusN === crit.size,
    'focus=' + focusN + ' crit=' + crit.size);

  // 集成入口 ⑤：Canvas 交互视图（FR-5，Node 里用假 canvas 冒烟）
  const ctx = makeCtx();
  const canvas = makeCanvas(ctx, 690);
  let err: unknown = null;
  let viewer: ReturnType<typeof createDagViewer> | null = null;
  try {
    viewer = createDagViewer(canvas as unknown as HTMLCanvasElement, dag, { dir: 'vertical' });
  } catch (e) {
    err = e;
  }
  check(ds.key + ' FR-5 createDagViewer 不抛异常', err === null,
    err ? String((err as Error).message) : '');
  if (viewer) {
    const layout = viewer.layout();
    check(ds.key + ' FR-3 布局覆盖全部任务',
      !!layout && Object.keys(layout.pos).length === tasks.length,
      layout ? 'pos=' + Object.keys(layout.pos).length : 'layout=null');
    check(ds.key + ' FR-5 绑定 mousemove/click/mouseleave',
      canvas.hasListener('mousemove') && canvas.hasListener('click') && canvas.hasListener('mouseleave'));
    const hRes = viewer.patch({ dir: 'horizontal' });
    check(ds.key + ' FR-5 切横向后布局方向生效', hRes.layout.dir === 'horizontal');
    const fRes = viewer.patch({ dir: 'vertical', focus: true });
    check(ds.key + ' FR-5/6 只看主线后可见节点收缩', fRes.visibleIds.length === crit.size,
      'visible=' + fRes.visibleIds.length + ' crit=' + crit.size);
    viewer.destroy();
    check(ds.key + ' FR-5 destroy 后解绑事件', !canvas.hasListener('mousemove'));
  }
});

check('数据集覆盖小图档（≤20 卡）', loadedCounts.some((n) => n <= 20), 'counts=' + loadedCounts.join(','));
check('数据集覆盖压力档（≥50 卡）', loadedCounts.some((n) => n >= 50), 'counts=' + loadedCounts.join(','));

/* ---------------- 降级路径（集成入口的负向对照） ---------------- */

console.log('\n[降级] 集成入口的负向对照');
const cyc = [
  { id: 'x', title: 'X', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', dependsOn: ['z'], layer: 0 },
  { id: 'y', title: 'Y', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', dependsOn: ['x'], layer: 1 },
  { id: 'z', title: 'Z', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', dependsOn: ['y'], layer: 2 },
] as CardData[];
check('有环：renderDagHtml 输出错误提示而不抛异常',
  renderDagHtml({ tasks: cyc, edges: [], ready: [] }, BASE_STATE).indexOf('循环依赖') >= 0);
check('空图：renderDagHtml 输出占位',
  renderDagHtml({ tasks: [], edges: [], ready: [] }, BASE_STATE).indexOf('暂无任务') >= 0);
const valBad = validateQueueFile({
  requirement_id: 'REQ-X',
  tasks: [{ id: 't1', title: 'T1', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', layer: 0, dependsOn: [], requirementId: 'REQ-Y' } as CardData],
  edges: [{ from: 't1', to: 't-ghost' }],
  ready: ['t1', 't-ghost'],
});
const rules = new Set(valBad.issues.map((i) => i.rule));
check('悬空边/串档/非法 ready 被校验拦下（V-2/V-3/V-6）',
  rules.has('V-2') && rules.has('V-3') && rules.has('V-6'));

/* ---------------- 汇总 ---------------- */

console.log('\n' + '='.repeat(56));
if (fail === 0) {
  console.log('全部通过：' + pass + ' / ' + (pass + fail));
  process.exit(0);
}
console.log('失败 ' + fail + ' 项 / 共 ' + (pass + fail) + ' 项：');
for (const f of failures) console.log('  - ' + f);
process.exit(1);
