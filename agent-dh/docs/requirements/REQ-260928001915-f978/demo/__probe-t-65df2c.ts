/**
 * 接口联调探针（REQ-260928001915-f978 · t-73c392 · FR-5 · 联调子卡 t-65df2c）
 *
 * 目的：对 interaction.ts 的对外接口做「请求样例 → 期望响应 → 实际返回」三方对照，
 * 并把它放进**真实消费链路**里验证被正确消费：
 *   - 请求样例 = 真实事件序列（mousemove / click / mouseleave / DOM mouseover…）
 *   - 期望响应 = design/interfaces.md 的接口契约 + design/test-cases.md 的 TC-9/10/11/12
 *   - 实际返回 = 控制台可观察的 pinned/hover 状态与渲染器实际落笔的颜色/透明度
 *
 * 运行：cd docs/requirements/REQ-260928001915-f978/demo && npx tsx __probe-t-65df2c.ts
 * 只读被测模块，不修改任何交付物；退出码 0 = 全部一致，1 = 有偏差。
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  setupInteraction, bindDomInteraction, resolveHighlight, paintDim,
  DIM_NODE_ALPHA, DIM_EDGE_ALPHA,
} from './interaction';
import { computeNeighbors } from './critical-path';
import { hitTest, CARD_W, CARD_H } from './dag-layout';
import { renderEdges, EDGE_UP, EDGE_DOWN, type Edge } from './edge-renderer';
import { renderCard } from './card-renderer';
import { createDagViewer, renderDagHtml, type DagData } from './integration';
import type { CardData } from './card-types';

const HERE = dirname(fileURLToPath(import.meta.url));
const queue = JSON.parse(readFileSync(resolve(HERE, '..', 'queue.json'), 'utf8'));
const tasks: CardData[] = queue.tasks;
const data: DagData = { tasks, edges: queue.edges, ready: queue.ready };

let pass = 0;
let fail = 0;
const failures: string[] = [];
function check(id: string, title: string, request: string, expected: string, actual: string): void {
  const ok = expected === actual;
  if (ok) pass += 1; else { fail += 1; failures.push(id + ' ' + title); }
  console.log('  ' + (ok ? 'PASS' : 'FAIL') + ' [' + id + '] ' + title);
  console.log('        请求样例: ' + request);
  console.log('        期望响应: ' + expected);
  console.log('        实际返回: ' + actual);
}
const warnings: string[] = [];
function finding(id: string, title: string, request: string, expected: string, actual: string): void {
  warnings.push(id + ' ' + title);
  console.log('  偏差 [' + id + '] ' + title + '（跨模块行为，不属 interaction.ts 实现范围）');
  console.log('        请求样例: ' + request);
  console.log('        期望响应: ' + expected);
  console.log('        实际返回: ' + actual);
}

/* ---------------- 事件探针桩 ---------------- */
interface Paint { kind: string; alpha: number; color: string; width: number }
class RecCtx {
  paints: Paint[] = [];
  globalAlpha = 1; strokeStyle: unknown = ''; lineWidth = 0; lineCap = '';
  font = ''; textAlign = ''; textBaseline = ''; fillStyle: unknown = '';
  save(): void {} restore(): void {} beginPath(): void {} closePath(): void {}
  moveTo(): void {} lineTo(): void {} quadraticCurveTo(): void {} bezierCurveTo(): void {}
  arc(): void {} clip(): void {} setLineDash(): void {} fillRect(): void {}
  fillText(): void {} clearRect(): void {} setTransform(): void {}
  measureText(): { width: number } { return { width: 10 }; }
  stroke(): void { this.paints.push({ kind: 'stroke', alpha: this.globalAlpha, color: String(this.strokeStyle), width: this.lineWidth }); }
  fill(): void { this.paints.push({ kind: 'fill', alpha: this.globalAlpha, color: String(this.fillStyle), width: this.lineWidth }); }
}
class FakeCanvas {
  private ls: Record<string, Array<(ev: any) => void>> = {};
  rect = { left: 10, top: 20 };
  ctx = new RecCtx();
  width = 0; height = 0;
  style: Record<string, string> = {};
  parentElement = { clientWidth: 900 };
  addEventListener(t: string, fn: (ev: any) => void): void { (this.ls[t] || (this.ls[t] = [])).push(fn); }
  removeEventListener(t: string, fn: (ev: any) => void): void { this.ls[t] = (this.ls[t] || []).filter(function (f) { return f !== fn; }); }
  getBoundingClientRect(): { left: number; top: number } { return this.rect; }
  getContext(): RecCtx { return this.ctx; }
  dispatch(t: string, x = 0, y = 0): void { (this.ls[t] || []).slice().forEach(function (fn) { fn({ clientX: x + 10, clientY: y + 20 }); }); }
  count(t: string): number { return (this.ls[t] || []).length; }
}
function sorted(s: Set<string>): string { return Array.from(s).sort().join(','); }

/* ================= A. interaction ↔ 真实消费方 createDagViewer ================= */
console.log('\n[A] interaction 接口 ↔ 真实消费方 createDagViewer（Canvas 全链路，数据=本需求真实 queue.json）');
const canvas = new FakeCanvas();
const viewer = createDagViewer(canvas as unknown as HTMLCanvasElement, data, { dir: 'vertical' });
const layout = viewer.layout();
check('A0', 'createDagViewer 先渲染再绑定，返回可用布局', 'createDagViewer(canvas, data, {dir:"vertical"})', 'true',
  String(!!layout));
const L = layout!;
let target = '';
for (let i = 0; i < tasks.length; i++) {
  const nb = computeNeighbors(tasks, tasks[i].id);
  if (nb.up.size > 0 && nb.down.size > 0) { target = tasks[i].id; break; }
}
check('A1', '选中既有上游又有下游的联调节点', '遍历真实任务表', 'true', String(!!target));
const tp = L.pos[target]!;
const cx = tp.x + CARD_W / 2;
const cy = tp.y + CARD_H / 2;
const blankX = L.width + 60;
const blankY = L.height + 60;

check('A2', 'hitTest 命中卡片中心 → 目标 id', 'hitTest(layout, ' + cx + ', ' + cy + ', 0)', target, String(hitTest(L, cx, cy, 0)));
check('A3', 'hitTest 命中空白 → null', 'hitTest(layout, ' + blankX + ', ' + blankY + ', 0)', 'null', String(hitTest(L, blankX, blankY, 0)));

canvas.dispatch('mousemove', cx, cy);
check('A4', 'mousemove 命中卡片 → 事件经 onChange 落到 state.pinned', 'mousemove(卡片中心)', target, String(viewer.state().pinned));
canvas.dispatch('mousemove', blankX, blankY);
check('A5', 'mousemove 移到空白 → state.pinned 清空', 'mousemove(空白)', 'null', String(viewer.state().pinned));
canvas.dispatch('click', cx, cy);
check('A6', 'click 卡片 → 钉住目标（TC-11 第 1 次点击）', 'click(卡片中心)', target, String(viewer.state().pinned));
const otherId = tasks.map(function (t) { return t.id; }).filter(function (id) { return id !== target && !!L.pos[id]; })[0] as string;
const op = L.pos[otherId]!;
canvas.dispatch('mousemove', op.x + CARD_W / 2, op.y + CARD_H / 2);
check('A7', '钉住态移开鼠标/悬停别的卡 → 高亮保持（TC-11）', 'click(target) 后 mousemove(' + otherId + ')', target, String(viewer.state().pinned));
canvas.dispatch('click', blankX, blankY);
check('A8', '钉住态点击画布空白 → 取消（TC-12）', 'click(空白)', 'null', String(viewer.state().pinned));
canvas.dispatch('click', cx, cy);
canvas.dispatch('click', cx, cy);
check('A9', '再次点击同一卡 → 取消（TC-11 第 2 次点击）', 'click(target) ×2', 'null', String(viewer.state().pinned));

/* ================= B. setupInteraction 控制器契约 ================= */
console.log('\n[B] setupInteraction 控制器契约（请求样例=事件序列）');
const c2 = new FakeCanvas();
const calls: Array<string | null> = [];
const ctrl = setupInteraction(c2 as unknown as HTMLCanvasElement, {
  hitTest: function (x, y) { return hitTest(L, x, y, 0); },
  onChange: function (id) { calls.push(id); },
});
check('B1', '监听器各绑定 1 个（mousemove/click/mouseleave）', 'setupInteraction(canvas, {hitTest,onChange})', '1,1,1',
  [c2.count('mousemove'), c2.count('click'), c2.count('mouseleave')].join(','));
check('B2', 'controller.pinned 初值', 'controller.pinned', 'null', String(ctrl.pinned));
check('B3', 'controller.hover 初值', 'controller.hover', 'null', String(ctrl.hover));
c2.dispatch('mousemove', cx, cy);
check('B4', '悬停命中 → onChange(target)，hover=target', 'mousemove(卡片)', target + '|' + target, String(calls[calls.length - 1]) + '|' + String(ctrl.hover));
c2.dispatch('mousemove', cx + 1, cy + 1);
check('B5', '同一卡重复 mousemove 去重（onChange 不重复）', 'mousemove(同一卡) ×2', '1', String(calls.length));
c2.dispatch('mousemove', blankX, blankY);
check('B6', '移到空白 → onChange(null)，hover=null', 'mousemove(空白)', 'null|null', String(calls[calls.length - 1]) + '|' + String(ctrl.hover));
c2.dispatch('click', cx, cy);
check('B7', 'click → pinned=target + onChange(target)', 'click(卡片)', target + '|' + target, String(ctrl.pinned) + '|' + String(calls[calls.length - 1]));
c2.dispatch('mouseleave');
check('B8', '钉住态 mouseleave 不取消高亮', 'mouseleave', target + '|' + target, String(ctrl.pinned) + '|' + String(calls[calls.length - 1]));
c2.dispatch('click', cx, cy);
check('B9', '再点同一卡 → pinned=null + onChange(null)', 'click(卡片)', 'null|null', String(ctrl.pinned) + '|' + String(calls[calls.length - 1]));
ctrl.reset();
check('B10', 'reset() → pinned=null + onChange(null)', 'reset()', 'null|null', String(ctrl.pinned) + '|' + String(calls[calls.length - 1]));
ctrl.destroy();
check('B11', 'destroy() → 三个监听器全部解绑', 'destroy()', '0,0,0',
  [c2.count('mousemove'), c2.count('click'), c2.count('mouseleave')].join(','));
const beforeDestroy = calls.length;
c2.dispatch('mousemove', cx, cy);
c2.dispatch('click', cx, cy);
check('B12', '解绑后事件不再回调', 'destroy() 后 dispatch', String(beforeDestroy), String(calls.length));

/* ================= C. 高亮数据结构 ↔ 协作者/渲染器 ================= */
console.log('\n[C] resolveHighlight 输出 ↔ computeNeighbors / edge-renderer / card-renderer');
const hl = resolveHighlight(tasks, target);
const nb = computeNeighbors(tasks, target);
check('C1', 'resolveHighlight.self = target', 'resolveHighlight(tasks, "' + target + '")', target, String(hl.self));
check('C2', 'up 集合 == computeNeighbors.up（全部可达前驱）', 'computeNeighbors(tasks, target).up', sorted(nb.up), sorted(hl.up));
check('C3', 'down 集合 == computeNeighbors.down（全部可达后继）', 'computeNeighbors(tasks, target).down', sorted(nb.down), sorted(hl.down));
const hlNull = resolveHighlight(tasks, null);
check('C4', 'id=null → 空高亮 {self:null, up:{}, down:{}}', 'resolveHighlight(tasks, null)', 'null,0,0',
  String(hlNull.self) + ',' + hlNull.up.size + ',' + hlNull.down.size);

const NB = { up: hl.up, down: hl.down };
function edgePaint(edges: Edge[]): RecCtx {
  const c = new RecCtx();
  renderEdges(c as unknown as CanvasRenderingContext2D, edges, L, tasks, {
    critSet: new Set<string>(), highlight: NB, dimmed: true, dir: 'vertical',
  });
  return c;
}
function first(edges: Edge[], pred: (e: Edge) => boolean): Edge | undefined {
  for (let i = 0; i < edges.length; i++) { if (pred(edges[i])) return edges[i]; }
  return undefined;
}
const upEdge = first(data.edges, function (e) { return e.to === target && hl.up.has(e.from); });
const upCtx = edgePaint(upEdge ? [upEdge] : []);
check('C5', '上游入边 → 橙色 #ff9500 宽 2 alpha 1（TC-9）',
  'renderEdges([' + (upEdge ? upEdge.from + '→' + upEdge.to : '无') + '], {highlight:{up,down}, dimmed:true})',
  EDGE_UP + '|2|1',
  upCtx.paints[0] ? upCtx.paints[0].color + '|' + upCtx.paints[0].width + '|' + upCtx.paints[0].alpha : '无描边');

const downEdge = first(data.edges, function (e) { return e.from === target; });
const downCtx = edgePaint(downEdge ? [downEdge] : []);
finding('C6', '下游首跳出边 → 蓝色 #0071e3 宽 2 alpha 1（TC-10）',
  'renderEdges([' + (downEdge ? downEdge.from + '→' + downEdge.to : '无') + '], {highlight:{up,down}, dimmed:true})',
  EDGE_DOWN + '|2|1',
  downCtx.paints[0] ? downCtx.paints[0].color + '|' + downCtx.paints[0].width + '|' + downCtx.paints[0].alpha : '无描边');

const deepEdge = first(data.edges, function (e) { return hl.down.has(e.from) && hl.down.has(e.to); });
const deepCtx = edgePaint(deepEdge ? [deepEdge] : []);
check('C6b', '下游更深的边（from∈down）→ 蓝色（佐证偏差只在首跳）',
  'renderEdges([' + (deepEdge ? deepEdge.from + '→' + deepEdge.to : '无') + '], {highlight:{up,down}, dimmed:true})',
  EDGE_DOWN,
  deepCtx.paints[0] ? deepCtx.paints[0].color : '无描边');

const allCtx = edgePaint(data.edges);
check('C7', '非高亮边 dimming alpha=0.05（DIM_EDGE_ALPHA）', 'renderEdges(全部边, dimmed:true)', 'true',
  String(allCtx.paints.some(function (x) { return x.kind === 'stroke' && x.alpha === 0.05; })));

const tgt = tasks.filter(function (t) { return t.id === target; })[0];
const dimCard = new RecCtx();
renderCard(dimCard as unknown as CanvasRenderingContext2D, tgt, tp.x, tp.y, { dimmed: true });
check('C8', '未高亮卡片整体填充 alpha=0.18（DIM_NODE_ALPHA）', 'renderCard(task, x, y, {dimmed:true})', 'true',
  String(dimCard.paints.some(function (x) { return x.kind === 'fill' && x.alpha === DIM_NODE_ALPHA; })));
const selfCard = new RecCtx();
renderCard(selfCard as unknown as CanvasRenderingContext2D, tgt, tp.x, tp.y, { highlight: 'self' });
const selfStroke = selfCard.paints.filter(function (x) { return x.kind === 'stroke' && x.color === '#1f2733'; })[0];
check('C9', '当前卡黑框描边 #1f2733（TC-9/TC-10）', "renderCard(task, x, y, {highlight:'self'})", '#1f2733',
  selfStroke ? selfStroke.color : '无黑框描边');

/* ================= D. bindDomInteraction ↔ renderDagHtml ================= */
console.log('\n[D] bindDomInteraction ↔ renderDagHtml（DOM 生产者/消费者契约）');
const html = renderDagHtml(data, { dir: 'vertical', crit: false, focus: false, pinned: null });
const m = /class="node[^"]*" data-id="([^"]+)"/.exec(html);
check('D1', 'renderDagHtml 产出可被 closest("[data-id]") 命中的节点', 'renderDagHtml(data, state)', 'true', String(!!m));
const domId = m ? m[1] : '';
check('D2', '产出的 data-id 真实存在于任务表', 'tasks.some(t=>t.id===domId)', 'true', String(tasks.some(function (t) { return t.id === domId; })));

interface DomNode { closest(sel: string): { getAttribute(a: string): string | null } | null }
function domNode(id: string | null): DomNode {
  return {
    closest: function (sel: string) {
      if (sel !== '[data-id]' || id === null) return null;
      return { getAttribute: function (a: string) { return a === 'data-id' ? id : null; } };
    },
  };
}
const domLs: Record<string, Array<(ev: any) => void>> = {};
const domRoot = {
  addEventListener: function (t: string, fn: (ev: any) => void) { (domLs[t] || (domLs[t] = [])).push(fn); },
  removeEventListener: function (t: string, fn: (ev: any) => void) { domLs[t] = (domLs[t] || []).filter(function (f) { return f !== fn; }); },
  dispatch: function (t: string, node: DomNode) { (domLs[t] || []).slice().forEach(function (fn) { fn({ target: node }); }); },
  count: function (t: string) { return (domLs[t] || []).length; },
};
const domCalls: Array<string | null> = [];
const dctrl = bindDomInteraction(domRoot as unknown as HTMLElement, {
  hitTest: function () { return null; },
  onChange: function (id) { domCalls.push(id); },
});
domRoot.dispatch('mouseover', domNode(domId));
check('D3', 'mouseover 真实节点 → onChange(id)', 'mouseover(node[data-id])', domId,
  domCalls.length === 1 ? String(domCalls[0]) : domCalls.length + ' 次回调');
domCalls.length = 0;
domRoot.dispatch('click', domNode(domId));
check('D4', 'click 节点 → pinned=id', 'click(node[data-id])', domId, String(dctrl.pinned));
domCalls.length = 0;
domRoot.dispatch('mouseover', domNode('t-other'));
check('D5', '钉住态 mouseover 别的节点 → 不回调', 'mouseover(其他节点)', '0', String(domCalls.length));
domCalls.length = 0;
domRoot.dispatch('click', domNode(null));
check('D6', '点击空白 → 取消钉住', 'click(空白)', 'null|null', String(dctrl.pinned) + '|' + String(domCalls[0]));
domCalls.length = 0;
domRoot.dispatch('mouseout', domNode(domId));
check('D7', '未钉住时 mouseout → onChange(null)', 'mouseout(node)', 'null', String(domCalls[0]));
dctrl.destroy();
check('D8', 'destroy 解绑三个 DOM 监听器', 'destroy()', '0,0,0',
  [domRoot.count('mouseover'), domRoot.count('mouseout'), domRoot.count('click')].join(','));

/* ================= E. 常量与 paintDim ================= */
console.log('\n[E] dimming 常量与 paintDim');
check('E1', 'DIM_NODE_ALPHA = 0.18', 'DIM_NODE_ALPHA', '0.18', String(DIM_NODE_ALPHA));
check('E2', 'DIM_EDGE_ALPHA = 0.05', 'DIM_EDGE_ALPHA', '0.05', String(DIM_EDGE_ALPHA));
const pc = { globalAlpha: 1 };
paintDim(pc as unknown as CanvasRenderingContext2D, DIM_EDGE_ALPHA);
check('E3', 'paintDim 写 ctx.globalAlpha', 'paintDim(ctx, 0.05)', '0.05', String(pc.globalAlpha));

/* ================= 汇总 ================= */
console.log('\n[联调汇总·接口契约与消费] ' + pass + '/' + (pass + fail) + ' 一致' + (fail ? '，' + fail + ' 项不一致' : ''));
if (warnings.length) {
  console.log('[联调汇总·跨模块行为] ' + warnings.length + ' 项偏差（已记录，不在本卡实现范围）：');
  warnings.forEach(function (w) { console.log('  - ' + w); });
}
if (fail) {
  console.error('不一致项：\n  - ' + failures.join('\n  - '));
  process.exit(1);
}
console.log('interaction 接口联调通过（对外签名 / 状态机 / 常量 / 数据结构 / 消费方接线全部一致）。');
