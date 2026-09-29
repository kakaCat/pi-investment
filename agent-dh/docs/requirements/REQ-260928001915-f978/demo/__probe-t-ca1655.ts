/**
 * 临时联调探针（REQ-260928001915-f978 · t-e4e9db · t-ca1655 联调）—— 跑完即删
 *
 * 目的：对边线渲染器的**对外接口**做「请求样例 → 期望响应 → 实际返回」三方对照，
 * 请求样例按真实消费方（integration.ts）的调用形态构造：
 *   - Canvas 消费方 createDagViewer：renderEdges(ctx, edges, layout, tasks, { critSet, highlight, dimmed, dir })
 *   - DOM 消费方 renderDagHtml ：edgeSvg(edges, layout, tasks, critSet, dir)
 */
import {
  EDGE_DONE, EDGE_DONE_W, EDGE_BASE, EDGE_BASE_W, EDGE_CRIT, EDGE_CRIT_W,
  renderEdges, edgeSvg, type Edge,
} from './edge-renderer';
import { calculateLayout } from './dag-layout';
import { Phase, Side, Role, Status, type CardData } from './card-types';
import { findCriticalPath } from './critical-path';
import { renderDagHtml, resolveTasks, type DagData, type DagState } from './integration';

let pass = 0;
let fail = 0;
const lines: string[] = [];

function card(id: string, status: Status, layer: number, dependsOn?: string[]): CardData {
  return { id, title: '任务 ' + id, phase: Phase.IMPLEMENT, side: Side.FRONTEND, role: Role.SOLO, status, layer, dependsOn };
}

const tasks: CardData[] = [
  card('p1', Status.TODO, 0),
  card('p2', Status.TODO, 1, ['p1']),
  card('p3', Status.TODO, 2, ['p2']),
  card('d1', Status.DONE, 1, ['p1']),
  card('d2', Status.DONE, 2, ['d1']),
  card('x1', Status.DONE, 0),
  card('x2', Status.DONE, 1, ['x1']),
];
const edges: Edge[] = [
  { from: 'p1', to: 'p2' },
  { from: 'p2', to: 'p3' },
  { from: 'p1', to: 'd1' },
  { from: 'd1', to: 'd2' },
  { from: 'x1', to: 'x2' },
];

interface Stroke { color: string; width: number; alpha: number; }
function makePaintCtx() {
  const strokes: Stroke[] = [];
  const ctx = {
    strokes, strokeStyle: '', lineWidth: 0, lineCap: '', globalAlpha: 1,
    save() {}, restore() {}, beginPath() {},
    moveTo(_x: number, _y: number) {}, lineTo(_x: number, _y: number) {},
    bezierCurveTo(_a: number, _b: number, _c: number, _d: number, _e: number, _f: number) {},
    stroke() { strokes.push({ color: ctx.strokeStyle, width: ctx.lineWidth, alpha: ctx.globalAlpha }); },
  };
  return ctx;
}
function canvasOf(c: ReturnType<typeof makePaintCtx>): CanvasRenderingContext2D { return c as unknown as CanvasRenderingContext2D; }
function count(hay: string, needle: string): number { return (hay.split(needle).length - 1); }

function verdict(tag: string, title: string, request: unknown, expected: unknown, actual: unknown): void {
  const ok = JSON.stringify(expected) === JSON.stringify(actual);
  if (ok) pass += 1; else fail += 1;
  lines.push('[' + tag + '] ' + title + '  → ' + (ok ? 'MATCH' : 'MISMATCH'));
  lines.push('  request : ' + JSON.stringify(request));
  lines.push('  expected: ' + JSON.stringify(expected));
  lines.push('  actual  : ' + JSON.stringify(actual));
  if (!ok) lines.push('  ^^ 期望与实际不一致');
}

/* ---------- C1：Canvas 消费方（integration.ts L176-181 同形调用） ---------- */
const resolved = resolveTasks(tasks);
const critSet = findCriticalPath(resolved);
const layout = calculateLayout(resolved, 'vertical', 900);

const ctx1 = makePaintCtx();
const drawn1 = renderEdges(canvasOf(ctx1), edges, layout, resolved, { critSet, highlight: null, dimmed: false, dir: 'vertical' });
verdict(
  'C1', 'renderEdges 三态着色（Canvas 后端 / critSet 由调用方注入）',
  { edges, opts: { critSet: '^findCriticalPath(resolveTasks(tasks))', highlight: null, dimmed: false, dir: 'vertical' } },
  {
    critSet: Array.from(critSet).sort(),
    drawn: 5,
    strokes: 10,
    colors: [EDGE_BASE, EDGE_BASE, EDGE_BASE, EDGE_BASE, EDGE_CRIT, EDGE_CRIT, EDGE_CRIT, EDGE_CRIT, EDGE_DONE, EDGE_DONE],
    widths: [EDGE_BASE_W, EDGE_BASE_W, EDGE_BASE_W, EDGE_BASE_W, EDGE_CRIT_W, EDGE_CRIT_W, EDGE_CRIT_W, EDGE_CRIT_W, EDGE_DONE_W, EDGE_DONE_W],
    allAlpha1: true,
  },
  {
    critSet: Array.from(critSet).sort(),
    drawn: drawn1,
    strokes: ctx1.strokes.length,
    colors: ctx1.strokes.map(s => s.color),
    widths: ctx1.strokes.map(s => s.width),
    allAlpha1: ctx1.strokes.every(s => s.alpha === 1),
  }
);

/* ---------- C2：DOM 消费方（真实集成入口 renderDagHtml → edgeSvg） ---------- */
const data: DagData = { tasks, edges, ready: ['p1', 'x1'] };
const state: DagState = { dir: 'vertical', crit: true, focus: false, pinned: null };
const html = renderDagHtml(data, state);
verdict(
  'C2', 'renderDagHtml 边线 SVG 契约（DOM 后端）',
  { data: { tasks: '7 张', edges, ready: ['p1', 'x1'] }, state },
  { dagTag: true, svgClass: true, eBase: 2, eCrit: 2, eDone: 1, paths: 5, nodes: 7, markers: 3, bezier: true },
  {
    dagTag: html.indexOf('<div class="dsh-pm-np-dag" data-direction="vertical" data-focus="false">') === 0,
    svgClass: count(html, '<svg class="edges"') === 1,
    eBase: count(html, 'class="e-base"'),
    eCrit: count(html, 'class="e-crit"'),
    eDone: count(html, 'class="e-done"'),
    paths: count(html, 'data-from='),
    nodes: count(html, 'class="node'),
    markers: count(html, '<marker id="m-'),
    bezier: /d="M[^"]*C/.test(html),
  }
);

/* ---------- C3：悬空引用（消费方依赖“跳过”语义） ---------- */
const ctx3 = makePaintCtx();
const drawn3 = renderEdges(canvasOf(ctx3), [{ from: 'p1', to: 'p2' }, { from: 'p1', to: 'ghost' }], layout, resolved, { critSet: new Set<string>() });
const svg3 = edgeSvg([{ from: 'p1', to: 'p2' }, { from: 'p1', to: 'ghost' }], layout, resolved, new Set<string>());
verdict(
  'C3', '悬空引用被跳过（消费方不预过滤）',
  { edges: [{ from: 'p1', to: 'p2' }, { from: 'p1', to: 'ghost' }] },
  { drawn: 1, strokes: 2, svgPaths: 1 },
  { drawn: drawn3, strokes: ctx3.strokes.length, svgPaths: count(svg3, 'data-from=') }
);

/* ---------- C4：显式 critSet 注入（“支持传入关键路径节点集合”） ---------- */
const ctx4 = makePaintCtx();
renderEdges(canvasOf(ctx4), [{ from: 'x1', to: 'x2' }, { from: 'p1', to: 'd1' }], layout, resolved, { critSet: new Set(['x1', 'x2']) });
verdict(
  'C4', 'critSet 参数生效（覆盖 done 绿 + 不影响未注入边）',
  { edges: [{ from: 'x1', to: 'x2' }, { from: 'p1', to: 'd1' }], critSet: ['x1', 'x2'] },
  { strokes: 4, colors: [EDGE_CRIT, EDGE_CRIT, EDGE_BASE, EDGE_BASE] },
  { strokes: ctx4.strokes.length, colors: ctx4.strokes.map(s => s.color) }
);

/* ---------- C5：横向布局（消费方 dir 切换） ---------- */
const htmlH = renderDagHtml(data, { dir: 'horizontal', crit: true, focus: false, pinned: null });
verdict(
  'C5', 'dir=horizontal 切换（DOM 消费方）',
  { state: { dir: 'horizontal', crit: true, focus: false, pinned: null } },
  { dataDirection: 'horizontal', paths: 5, eCrit: 2 },
  { dataDirection: htmlH.indexOf('data-direction="horizontal"') >= 0 ? 'horizontal' : 'MISSING', paths: count(htmlH, 'data-from='), eCrit: count(htmlH, 'class="e-crit"') }
);

/* ---------- C6：跨帧复用画笔 & 入参不可变（消费方每帧复用 ctx） ---------- */
const snapshot = JSON.stringify({ tasks: resolved, edges });
const ctx6 = makePaintCtx();
renderEdges(canvasOf(ctx6), edges, layout, resolved, { critSet });
verdict(
  'C6', '绘制后画笔复位 + 入参不被修改',
  { note: '同一 ctx 连续绘制；tasks/edges 快照比对' },
  { strokeStyle: EDGE_BASE, lineWidth: EDGE_BASE_W, inputsUnchanged: true },
  { strokeStyle: ctx6.strokeStyle, lineWidth: ctx6.lineWidth, inputsUnchanged: snapshot === JSON.stringify({ tasks: resolved, edges }) }
);

/* ---------- C7：子集边序 = 消费方过滤后的顺序（focus 折叠时不串色） ---------- */
const keep = new Set(['p1', 'd1', 'd2']);
const subset = edges.filter(e => keep.has(e.from) && keep.has(e.to));
const ctx7 = makePaintCtx();
const drawn7 = renderEdges(canvasOf(ctx7), subset, layout, resolved, { critSet: new Set(['p1', 'd1', 'd2']) });
verdict(
  'C7', '边子集（focus 折叠）逐边独立着色',
  { edges: subset, critSet: ['p1', 'd1', 'd2'] },
  { drawn: 2, colors: [EDGE_CRIT, EDGE_CRIT, EDGE_CRIT, EDGE_CRIT] },
  { drawn: drawn7, colors: ctx7.strokes.map(s => s.color) }
);

console.log(lines.join('\n'));
console.log('\n[联调汇总] ' + pass + '/' + (pass + fail) + ' MATCH' + (fail ? '，' + fail + ' 项不一致' : ''));
if (fail) process.exit(1);
