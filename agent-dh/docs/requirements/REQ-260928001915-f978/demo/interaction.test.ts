/**
 * interaction.ts 单测（REQ-260928001915-f978 · t-73c392 · FR-5 · 研发）
 *
 * 运行（无需浏览器 / 无第三方依赖）：
 *   cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/interaction.test.ts
 *
 * 覆盖 FR-5 的悬停交互契约：
 *   ① dimming 常量：节点 0.18 / 边线 0.05，paintDim 写入 ctx.globalAlpha
 *   ② resolveHighlight：self + up（可达前驱橙）/ down（可达后继蓝），id=null → 空集
 *   ③ setupInteraction：mousemove 命中高亮、移到空白清除、同 id 去重
 *   ④ 点击钉住：点卡片 → pinned；再点同一卡 → 取消；点空白 → 取消
 *   ⑤ 钉住态：mousemove 不改高亮、mouseleave 不取消；点别的卡切换钉住
 *   ⑥ destroy 解绑：解绑后事件不再回调
 *   ⑦ bindDomInteraction：DOM 事件委托（mouseover/mouseout/click）同语义
 *   ⑧ 跨模块对齐：renderEdges/renderCard 的 dimming 实际取值与 ②的常量一致
 *
 * 退出码 0 = 全绿；1 = 有断言失败。
 */
import {
  setupInteraction,
  bindDomInteraction,
  resolveHighlight,
  paintDim,
  DIM_NODE_ALPHA,
  DIM_EDGE_ALPHA,
  type InteractionOptions,
} from './interaction';
import { renderEdges, EDGE_UP, type Edge } from './edge-renderer';
import { renderCard } from './card-renderer';
import { calculateLayout } from './dag-layout';
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

/* ---------------- 测试夹具 ---------------- */

type Handler = (ev: any) => void;

/** 最小 canvas 桩：记录监听器，可按类型派发事件 */
class FakeCanvas {
  private ls: Record<string, Handler[]> = {};
  rect = { left: 10, top: 20 };

  addEventListener(t: string, fn: Handler): void {
    (this.ls[t] || (this.ls[t] = [])).push(fn);
  }
  removeEventListener(t: string, fn: Handler): void {
    this.ls[t] = (this.ls[t] || []).filter(function (f) { return f !== fn; });
  }
  getBoundingClientRect(): { left: number; top: number } {
    return { left: this.rect.left, top: this.rect.top };
  }
  /** 在画布局部坐标 (x, y) 派发一个鼠标事件 */
  dispatch(t: string, x?: number, y?: number): void {
    (this.ls[t] || []).slice().forEach(function (fn) {
      fn({ clientX: (x === undefined ? 0 : x) + 10, clientY: (y === undefined ? 0 : y) + 20 });
    });
  }
  count(t: string): number {
    return (this.ls[t] || []).length;
  }
}

function canvasOf(c: FakeCanvas): HTMLCanvasElement {
  return c as unknown as HTMLCanvasElement;
}

/** 命中区：id -> 画布局部矩形（左下角 0,0 起） */
const BOXES: Record<string, { x: number; y: number; w: number; h: number }> = {
  a: { x: 0, y: 0, w: 60, h: 30 },
  b: { x: 100, y: 0, w: 60, h: 30 },
  c: { x: 200, y: 0, w: 60, h: 30 },
  d: { x: 100, y: 60, w: 60, h: 30 },
};

function hit(x: number, y: number): string | null {
  for (const id in BOXES) {
    const b = BOXES[id];
    if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return id;
  }
  return null;
}

/** 点某 id 的中心（画布局部坐标） */
function centerOf(id: string): { x: number; y: number } {
  const b = BOXES[id];
  return { x: b.x + b.w / 2, y: b.y + b.h / 2 };
}

function task(id: string, dependsOn?: string[]): CardData {
  return {
    id,
    title: '任务 ' + id,
    phase: Phase.IMPLEMENT,
    side: Side.FRONTEND,
    role: Role.SOLO,
    status: Status.TODO,
    layer: 0,
    dependsOn,
  };
}

/* 图：a → b → c，a → d */
const TASKS: CardData[] = [task('a'), task('b', ['a']), task('c', ['b']), task('d', ['a'])];
const EDGES: Edge[] = [{ from: 'a', to: 'b' }, { from: 'b', to: 'c' }, { from: 'a', to: 'd' }];

function sorted(s: Set<string>): string[] {
  return Array.from(s).sort();
}

/* ---------------- ① dimming 常量与 paintDim ---------------- */

console.log('[1] dimming 常量 / paintDim');
check('节点 dim 透明度 = 0.18', DIM_NODE_ALPHA === 0.18, '实际 ' + DIM_NODE_ALPHA);
check('边线 dim 透明度 = 0.05', DIM_EDGE_ALPHA === 0.05, '实际 ' + DIM_EDGE_ALPHA);
const paintCtx = { globalAlpha: 1 } as { globalAlpha: number };
paintDim(paintCtx as unknown as CanvasRenderingContext2D, DIM_NODE_ALPHA);
check('paintDim 写入 ctx.globalAlpha', paintCtx.globalAlpha === 0.18, '实际 ' + paintCtx.globalAlpha);

/* ---------------- ② resolveHighlight ---------------- */

console.log('\n[2] resolveHighlight（self / up 橙 / down 蓝）');
const hlB = resolveHighlight(TASKS, 'b');
check('hover b：self=b', hlB.self === 'b');
check('hover b：上游 = {a}', sorted(hlB.up).join(',') === 'a', '实际 {' + sorted(hlB.up).join(',') + '}');
check('hover b：下游 = {c}', sorted(hlB.down).join(',') === 'c', '实际 {' + sorted(hlB.down).join(',') + '}');
check('hover b：self 不在 up/down 内', !hlB.up.has('b') && !hlB.down.has('b'));
const hlA = resolveHighlight(TASKS, 'a');
check('起点 a：上游为空', hlA.up.size === 0);
check('起点 a：下游 = {b,c,d}（可达传递）', sorted(hlA.down).join(',') === 'b,c,d', '实际 {' + sorted(hlA.down).join(',') + '}');
const hlNull = resolveHighlight(TASKS, null);
check('id=null → 空高亮（self=null 且集合为空）', hlNull.self === null && hlNull.up.size === 0 && hlNull.down.size === 0);

/* ---------------- ③④⑤ setupInteraction ---------------- */

console.log('\n[3] setupInteraction（Canvas）：悬停 / 钉住 / 取消');
const canvas = new FakeCanvas();
const calls: Array<string | null> = [];
const opts: InteractionOptions = { hitTest: hit, onChange: function (id) { calls.push(id); } };
const ctrl = setupInteraction(canvasOf(canvas), opts);

check('已绑定 mousemove', canvas.count('mousemove') === 1);
check('已绑定 click', canvas.count('click') === 1);
check('已绑定 mouseleave', canvas.count('mouseleave') === 1);

// 悬停 b（容器有 10/20 偏移，命中测试在局部坐标）
const pb = centerOf('b');
canvas.dispatch('mousemove', pb.x, pb.y);
check('mousemove 命中 b → onChange(b)', calls.length === 1 && calls[0] === 'b', JSON.stringify(calls));
canvas.dispatch('mousemove', pb.x + 1, pb.y + 1);
check('同一张卡重复 mousemove 去重（不重复回调）', calls.length === 1, JSON.stringify(calls));
canvas.dispatch('mousemove', 500, 500);
check('移到空白 → onChange(null)', calls.length === 2 && calls[1] === null, JSON.stringify(calls));

// 点击钉住
canvas.dispatch('click', pb.x, pb.y);
check('click 卡片 → pinned=b 且 onChange(b)', ctrl.pinned === 'b' && calls[calls.length - 1] === 'b', JSON.stringify(calls));
canvas.dispatch('mouseleave');
check('钉住时 mouseleave 不取消高亮（无新回调）', ctrl.pinned === 'b' && calls[calls.length - 1] === 'b', JSON.stringify(calls));
const pc = centerOf('c');
canvas.dispatch('mousemove', pc.x, pc.y);
check('钉住时悬停别的卡不改高亮（无新回调）', calls[calls.length - 1] === 'b', JSON.stringify(calls));

// 再点同一卡取消
canvas.dispatch('click', pb.x, pb.y);
check('再点同一卡 → pinned=null 且 onChange(null)', ctrl.pinned === null && calls[calls.length - 1] === null, JSON.stringify(calls));

// 点空白取消
canvas.dispatch('click', pb.x, pb.y);
check('重新钉住 b', ctrl.pinned === 'b');
canvas.dispatch('click', 500, 500);
check('点击画布空白 → 取消高亮', ctrl.pinned === null && calls[calls.length - 1] === null, JSON.stringify(calls));

// 点别的卡切换钉住
canvas.dispatch('click', pb.x, pb.y);
canvas.dispatch('click', pc.x, pc.y);
check('钉住态点别的卡 → 切换钉住到 c', ctrl.pinned === 'c' && calls[calls.length - 1] === 'c', JSON.stringify(calls));

// reset
ctrl.reset();
check('reset() → pinned 清空并回传 null', ctrl.pinned === null && calls[calls.length - 1] === null);

/* ---------------- ⑥ destroy ---------------- */

console.log('\n[4] destroy 解绑');
const before = calls.length;
ctrl.destroy();
check('destroy 后三个监听器全部解绑', canvas.count('mousemove') === 0 && canvas.count('click') === 0 && canvas.count('mouseleave') === 0);
canvas.dispatch('mousemove', pb.x, pb.y);
canvas.dispatch('click', pb.x, pb.y);
check('解绑后事件不再触发回调', calls.length === before, 'before=' + before + ' after=' + calls.length);

/* ---------------- ⑦ bindDomInteraction ---------------- */

console.log('\n[5] bindDomInteraction（DOM 事件委托）');
interface DomNode { closest(sel: string): { getAttribute(a: string): string | null } | null }
function domNode(id: string | null): DomNode {
  return {
    closest: function (sel: string) {
      if (sel !== '[data-id]' || id === null) return null;
      return { getAttribute: function (a: string) { return a === 'data-id' ? id : null; } };
    },
  };
}
const domLs: Record<string, Handler[]> = {};
const domRoot = {
  addEventListener: function (t: string, fn: Handler) { (domLs[t] || (domLs[t] = [])).push(fn); },
  removeEventListener: function (t: string, fn: Handler) { domLs[t] = (domLs[t] || []).filter(function (f) { return f !== fn; }); },
  dispatch: function (t: string, node: DomNode) { (domLs[t] || []).slice().forEach(function (fn) { fn({ target: node }); }); },
  count: function (t: string) { return (domLs[t] || []).length; },
};
const domCalls: Array<string | null> = [];
const domCtrl = bindDomInteraction(domRoot as unknown as HTMLElement, {
  hitTest: function () { return null; },
  onChange: function (id) { domCalls.push(id); },
});
domRoot.dispatch('mouseover', domNode('b'));
check('mouseover 节点 → onChange(b)', domCalls.length === 1 && domCalls[0] === 'b', JSON.stringify(domCalls));
domCalls.length = 0;
domRoot.dispatch('click', domNode('b'));
check('click 节点 → pinned=b', domCtrl.pinned === 'b' && domCalls[0] === 'b', JSON.stringify(domCalls));
domCalls.length = 0;
domRoot.dispatch('mouseover', domNode('c'));
check('钉住时 mouseover 不改高亮', domCalls.length === 0 && domCtrl.pinned === 'b', JSON.stringify(domCalls));
domCalls.length = 0;
domRoot.dispatch('click', domNode(null));
check('点击空白 → 取消钉住', domCtrl.pinned === null && domCalls[0] === null, JSON.stringify(domCalls));
domCalls.length = 0;
domRoot.dispatch('mouseout', domNode('c'));
check('未钉住时 mouseout → onChange(null)', domCalls.length === 1 && domCalls[0] === null, JSON.stringify(domCalls));
domCalls.length = 0;
domCtrl.destroy();
check('destroy 后 DOM 监听器全部解绑', domRoot.count('mouseover') === 0 && domRoot.count('mouseout') === 0 && domRoot.count('click') === 0);

/* ---------------- ⑧ 跨模块 dimming 取值对齐 ---------------- */

console.log('\n[6] 渲染器实际 dimming 取值与常量对齐');
interface Paint { kind: string; alpha: number; color: string }
function makeCtx(): { ctx: any; paints: Paint[] } {
  const paints: Paint[] = [];
  const ctx: any = {
    paints,
    globalAlpha: 1,
    strokeStyle: '',
    lineWidth: 0,
    lineCap: '',
    font: '',
    textAlign: '',
    textBaseline: '',
    fillStyle: '',
    save: function () {},
    restore: function () {},
    beginPath: function () {},
    closePath: function () {},
    moveTo: function () {},
    lineTo: function () {},
    quadraticCurveTo: function () {},
    bezierCurveTo: function () {},
    arc: function () {},
    clip: function () {},
    setLineDash: function () {},
    fillRect: function () {},
    fillText: function () {},
    measureText: function () { return { width: 10 }; },
    stroke: function () { paints.push({ kind: 'stroke', alpha: ctx.globalAlpha, color: ctx.strokeStyle }); },
    fill: function () { paints.push({ kind: 'fill', alpha: ctx.globalAlpha, color: ctx.fillStyle }); },
  };
  return { ctx, paints };
}

// 边线：未高亮边 dim→0.05，高亮（上游）边 alpha=1 且用橙色
const layout = calculateLayout(TASKS, 'vertical', 900);
const edgeCase = makeCtx();
renderEdges(edgeCase.ctx, EDGES, layout, TASKS, {
  critSet: new Set<string>(),
  highlight: { up: new Set(['a']), down: new Set() },
  dimmed: true,
  dir: 'vertical',
});
const dimEdgePaints = edgeCase.paints.filter(function (p) { return p.alpha === 0.05; });
const hlEdgePaints = edgeCase.paints.filter(function (p) { return p.alpha === 1 && p.color === EDGE_UP; });
check('未高亮边线 alpha=0.05（与 DIM_EDGE_ALPHA 一致）', dimEdgePaints.length > 0, '0.05 描边数 ' + dimEdgePaints.length);
check('高亮上游边线 alpha=1 且橙色', hlEdgePaints.length > 0, '高亮描边数 ' + hlEdgePaints.length);

// 卡片：dimmed 时背景填充 alpha=0.18
const cardCase = makeCtx();
renderCard(cardCase.ctx, TASKS[0], 0, 0, { dimmed: true });
check('未高亮卡片填充 alpha=0.18（与 DIM_NODE_ALPHA 一致）', cardCase.paints.some(function (p) { return p.kind === 'fill' && p.alpha === 0.18; }));
const cardCase2 = makeCtx();
renderCard(cardCase2.ctx, TASKS[0], 0, 0, { dimmed: false });
check('未 dimming 的卡片填充 alpha=1', cardCase2.paints.some(function (p) { return p.kind === 'fill' && p.alpha === 1; }));

/* ---------------- 汇总 ---------------- */

console.log('\n[汇总] ' + pass + ' 通过 / ' + fail + ' 失败');
if (fail > 0) {
  console.error('失败项：\n  - ' + failures.join('\n  - '));
  process.exit(1);
}
console.log('interaction 自测全绿。');
