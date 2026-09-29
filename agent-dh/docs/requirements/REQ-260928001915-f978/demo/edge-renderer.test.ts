/**
 * edge-renderer.ts 单测（REQ-260928001915-f978 · t-e4e9db · FR-4 · t-660826 研发）
 *
 * 运行（无需浏览器 / 无第三方依赖）：
 *   cd docs/requirements/REQ-260928001915-f978 && npx tsx demo/edge-renderer.test.ts
 *
 * 覆盖 FR-4 的着色契约（含边界与优先级）：
 *   ① 颜色/线宽常量：done=rgba(52,199,89,.5)/1.3、base=rgba(0,0,0,.17)/1.2、crit=rgba(0,113,227,.75)/1.8
 *   ② edgeStyle 判定：两端 done→绿；否则→灰；两端在关键路径集合→蓝
 *   ③ 优先级：关键路径 > 已完成链路；仅一端在 critSet 不误标为关键路径
 *   ④ renderEdges（Canvas 后端，本卡主交付）：逐边按样式描边 2 次（线 + 箭头），
 *      返回值 = 实际绘制边数；引用不存在节点的边被跳过；绘制后复位画笔
 *   ⑤ 几何/端口：纵向从卡片下边出发、横向从卡片右边出发；多出边端口铺开不重叠
 *   ⑥ dimming：开启 dimmed 时未高亮边 alpha=0.05、高亮边 alpha=1
 *   ⑦ edgeSvg（DOM 后端）同样按样式产类名 + 箭头 marker + Bézier
 *
 * 退出码 0 = 全绿；1 = 有断言失败。
 */
import {
  EDGE_DONE,
  EDGE_DONE_W,
  EDGE_BASE,
  EDGE_BASE_W,
  EDGE_CRIT,
  EDGE_CRIT_W,
  EDGE_UP,
  EDGE_DOWN,
  EDGE_HL_W,
  allocatePorts,
  edgeGeometry,
  edgeStyle,
  resetEdgePaint,
  renderEdges,
  edgeSvg,
  type Edge,
} from './edge-renderer';
import { CARD_W, CARD_H, calculateLayout } from './dag-layout';
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

function card(id: string, status: Status, layer: number, dependsOn?: string[]): CardData {
  return {
    id,
    title: '任务 ' + id,
    phase: Phase.IMPLEMENT,
    side: Side.FRONTEND,
    role: Role.SOLO,
    status,
    layer,
    dependsOn,
  };
}

interface StrokeRecord {
  color: string;
  width: number;
  alpha: number;
}

/** 最小 Canvas 2D 录制桩：只记录被描边的样式，不需要真实画布 */
function makePaintCtx() {
  const strokes: StrokeRecord[] = [];
  const ctx = {
    strokes,
    strokeStyle: '',
    lineWidth: 0,
    lineCap: '',
    globalAlpha: 1,
    save(): void {},
    restore(): void {},
    beginPath(): void {},
    moveTo(_x: number, _y: number): void {},
    lineTo(_x: number, _y: number): void {},
    bezierCurveTo(_a: number, _b: number, _c: number, _d: number, _e: number, _f: number): void {},
    stroke(): void {
      strokes.push({ color: ctx.strokeStyle, width: ctx.lineWidth, alpha: ctx.globalAlpha });
    },
  };
  return ctx;
}

function ctxOf(ctx: ReturnType<typeof makePaintCtx>): CanvasRenderingContext2D {
  return ctx as unknown as CanvasRenderingContext2D;
}

/* ---------------- ① 常量 ---------------- */

console.log('\n[1] 颜色 / 线宽常量（FR-4 硬编码契约）');
check('done 绿 rgba(52,199,89,.5)', EDGE_DONE === 'rgba(52,199,89,.5)', EDGE_DONE);
check('done 线宽 1.3', EDGE_DONE_W === 1.3, String(EDGE_DONE_W));
check('base 灰 rgba(0,0,0,.17)', EDGE_BASE === 'rgba(0,0,0,.17)', EDGE_BASE);
check('base 线宽 1.2', EDGE_BASE_W === 1.2, String(EDGE_BASE_W));
check('crit 蓝 rgba(0,113,227,.75)', EDGE_CRIT === 'rgba(0,113,227,.75)', EDGE_CRIT);
check('crit 线宽 1.8', EDGE_CRIT_W === 1.8, String(EDGE_CRIT_W));
check('三种边色互不相同', new Set([EDGE_DONE, EDGE_BASE, EDGE_CRIT]).size === 3);
check('高亮色与关键路径色不同（橙 up / 蓝 down）', (EDGE_UP as string) !== (EDGE_DOWN as string) && EDGE_DOWN === '#0071e3' && EDGE_HL_W === 2);

/* ---------------- ② edgeStyle 判定 ---------------- */

console.log('\n[2] edgeStyle 按状态/关键路径着色');
const donePair: CardData[] = [card('d1', Status.DONE, 0), card('d2', Status.DONE, 1)];
const openPair: CardData[] = [card('o1', Status.TODO, 0), card('o2', Status.IN_PROGRESS, 1)];
const mixedPair: CardData[] = [card('m1', Status.DONE, 0), card('m2', Status.TODO, 1)];
const byIdDone: Record<string, CardData> = {};
donePair.forEach(function (c) { byIdDone[c.id] = c; });
const byIdOpen: Record<string, CardData> = {};
openPair.forEach(function (c) { byIdOpen[c.id] = c; });
const byIdMixed: Record<string, CardData> = {};
mixedPair.forEach(function (c) { byIdMixed[c.id] = c; });

const eDone: Edge = { from: 'd1', to: 'd2' };
const stDone = edgeStyle(eDone, byIdDone, new Set(), null);
check('两端 done → 绿 1.3', stDone.color === EDGE_DONE && stDone.width === EDGE_DONE_W);

const stOpen = edgeStyle({ from: 'o1', to: 'o2' }, byIdOpen, new Set(), null);
check('两端未完成 → 灰 1.2', stOpen.color === EDGE_BASE && stOpen.width === EDGE_BASE_W);

const stMixed = edgeStyle({ from: 'm1', to: 'm2' }, byIdMixed, new Set(), null);
check('仅一端 done → 灰（不误判为已完成链路）', stMixed.color === EDGE_BASE && stMixed.width === EDGE_BASE_W);

const stCrit = edgeStyle({ from: 'o1', to: 'o2' }, byIdOpen, new Set(['o1', 'o2']), null);
check('两端在关键路径集合 → 蓝 1.8', stCrit.color === EDGE_CRIT && stCrit.width === EDGE_CRIT_W);

const stCritOverDone = edgeStyle({ from: 'd1', to: 'd2' }, byIdDone, new Set(['d1', 'd2']), null);
check('优先级：关键路径 > 已完成链路', stCritOverDone.color === EDGE_CRIT && stCritOverDone.width === EDGE_CRIT_W);

const stHalfCrit = edgeStyle({ from: 'd1', to: 'd2' }, byIdDone, new Set(['d1']), null);
check('仅一端在 critSet → 不误标关键路径（现为 done 绿）', stHalfCrit.color === EDGE_DONE);

const stGhost = edgeStyle({ from: 'ghost-a', to: 'ghost-b' }, byIdDone, new Set(), null);
check('引用不存在节点 → 退化为灰（不抛异常）', stGhost.color === EDGE_BASE && stGhost.width === EDGE_BASE_W);

const stUp = edgeStyle(eDone, byIdDone, new Set(), { up: new Set(['d2']), down: new Set() });
check('悬停上游 → 橙 2px（供 t6 交互复用）', stUp.color === EDGE_UP && stUp.width === EDGE_HL_W);
const stDown = edgeStyle(eDone, byIdDone, new Set(), { up: new Set(), down: new Set(['d1']) });
check('悬停下游 → 蓝 #0071e3 2px', stDown.color === EDGE_DOWN && stDown.width === EDGE_HL_W);

/* ---------------- ③ 几何与端口 ---------------- */

console.log('\n[3] 边线几何 / 端口铺开');
const gv = edgeGeometry({ x: 100, y: 200 }, { x: 400, y: 500 }, 0.5, 0.5, 'vertical');
check('纵向：起点在源卡下边中点', gv.sx === 100 + CARD_W * 0.5 && gv.sy === 200 + CARD_H);
check('纵向：终点在目标卡上边（按入端口比例）', gv.ty === 500 && gv.tx === 400 + CARD_W * 0.5);
const gh = edgeGeometry({ x: 100, y: 200 }, { x: 400, y: 500 }, 0.5, 0.5, 'horizontal');
check('横向：起点在源卡右边中点', gh.sx === 100 + CARD_W && gh.sy === 200 + CARD_H * 0.5);
check('横向：终点在目标卡左边', gh.tx === 400 && gh.ty === 500 + CARD_H * 0.5);

const fanTasks: CardData[] = [
  card('r', Status.TODO, 0),
  card('l1', Status.TODO, 1),
  card('l2', Status.TODO, 1),
  card('l3', Status.TODO, 1),
];
const fanLayout = calculateLayout(fanTasks, 'vertical', 900);
const fanEdges: Edge[] = [{ from: 'r', to: 'l3' }, { from: 'r', to: 'l1' }, { from: 'r', to: 'l2' }];
const ports = allocatePorts(fanEdges, fanLayout, 'vertical');
check('单出边端口居中（0.5）', ports.outF[0] === 0.5 || ports.outF[1] === 0.5 || ports.outF[2] === 0.5);
check('3 条出边端口铺开且互不相同', new Set([ports.outF[0], ports.outF[1], ports.outF[2]]).size === 3);
check('端口都落在卡边 0.2~0.8 区间', [ports.outF[0], ports.outF[1], ports.outF[2]].every(function (f) { return f >= 0.2 && f <= 0.8; }));
check('入边端口同样铺开（单入边=0.5）', ports.inF[0] === 0.5 && ports.inF[1] === 0.5 && ports.inF[2] === 0.5);

/* ---------------- ④ renderEdges（Canvas 后端，主交付） ---------------- */

console.log('\n[4] renderEdges Canvas 描边');
const mixTasks: CardData[] = [
  card('a', Status.TODO, 0),
  card('b', Status.TODO, 1, ['a']),
  card('c', Status.DONE, 1, ['a']),
  card('d', Status.DONE, 2, ['c']),
];
const mixLayout = calculateLayout(mixTasks, 'vertical', 900);
const mixEdges: Edge[] = [
  { from: 'a', to: 'b' }, // 默认灰
  { from: 'c', to: 'd' }, // 两端 done → 绿
  { from: 'a', to: 'c' }, // 关键路径 → 蓝
];
const snapshot = JSON.stringify({ tasks: mixTasks, edges: mixEdges });
const ctx = makePaintCtx();
const drawn = renderEdges(ctxOf(ctx), mixEdges, mixLayout, mixTasks, { critSet: new Set(['a', 'c']) });
check('返回值 = 绘制边数（3）', drawn === 3, 'got=' + drawn);
check('每条边描边 2 次（线 + 箭头）', ctx.strokes.length === 6, 'got=' + ctx.strokes.length);
check('边1 灰 1.2', ctx.strokes[0].color === EDGE_BASE && ctx.strokes[0].width === EDGE_BASE_W);
check('边2 绿 1.3（两端 done）', ctx.strokes[2].color === EDGE_DONE && ctx.strokes[2].width === EDGE_DONE_W);
check('边3 蓝 1.8（关键路径）', ctx.strokes[4].color === EDGE_CRIT && ctx.strokes[4].width === EDGE_CRIT_W);
check('箭头与线同色同宽', ctx.strokes[1].color === ctx.strokes[0].color && ctx.strokes[1].width === ctx.strokes[0].width && ctx.strokes[5].color === EDGE_CRIT);
check('默认不 dimming（alpha=1）', ctx.strokes.every(function (s) { return s.alpha === 1; }));
check('绘制后画笔复位为普通连线', ctx.strokeStyle === EDGE_BASE && ctx.lineWidth === EDGE_BASE_W);

resetEdgePaint(ctxOf(ctx));
check('resetEdgePaint 显式复位', ctx.strokeStyle === EDGE_BASE && ctx.lineWidth === EDGE_BASE_W && ctx.lineCap === 'round');

const ctxGhost = makePaintCtx();
const drawnGhost = renderEdges(ctxOf(ctxGhost), [{ from: 'a', to: 'ghost' }, { from: 'a', to: 'b' }], mixLayout, mixTasks, {});
check('引用不存在节点的边被跳过（drawn=1）', drawnGhost === 1, 'got=' + drawnGhost);
check('被跳过的边不产生描边（strokes=2）', ctxGhost.strokes.length === 2, 'got=' + ctxGhost.strokes.length);

const ctxDim = makePaintCtx();
renderEdges(ctxOf(ctxDim), [{ from: 'a', to: 'b' }], mixLayout, mixTasks, {
  dimmed: true,
  highlight: { up: new Set(['__none__']), down: new Set() },
});
check('dimmed + 未高亮 → alpha=0.05', ctxDim.strokes.length > 0 && ctxDim.strokes.every(function (s) { return s.alpha === 0.05; }));

const ctxHl = makePaintCtx();
renderEdges(ctxOf(ctxHl), [{ from: 'a', to: 'b' }], mixLayout, mixTasks, {
  dimmed: true,
  highlight: { up: new Set(['b']), down: new Set() },
});
check('dimmed + 高亮边 → alpha=1（不被压暗）', ctxHl.strokes.length > 0 && ctxHl.strokes.every(function (s) { return s.alpha === 1 && s.color === EDGE_UP; }));

check('renderEdges 不修改入参（tasks/edges 快照一致）', JSON.stringify({ tasks: mixTasks, edges: mixEdges }) === snapshot);

/* ---------------- ⑤ edgeSvg（DOM 后端） ---------------- */

console.log('\n[5] edgeSvg DOM 后端');
const svgDone = edgeSvg([{ from: 'c', to: 'd' }], mixLayout, mixTasks, new Set());
check('两端 done → e-done', svgDone.indexOf('class="e-done"') >= 0);
const svgBase = edgeSvg([{ from: 'a', to: 'b' }], mixLayout, mixTasks, new Set());
check('普通 → e-base', svgBase.indexOf('class="e-base"') >= 0);
const svgCrit = edgeSvg([{ from: 'a', to: 'c' }], mixLayout, mixTasks, new Set(['a', 'c']));
check('关键路径 → e-crit', svgCrit.indexOf('class="e-crit"') >= 0);
check('带箭头 marker-end', svgCrit.indexOf('marker-end="url(#m-crit)"') >= 0);
check('Bézier 三次曲线（C 命令）', /d="M[^"]*C/.test(svgBase));
check('保留 data-from / data-to 便于测试与交互', svgBase.indexOf('data-from="a"') >= 0 && svgBase.indexOf('data-to="b"') >= 0);
check('引用不存在节点的边被跳过', edgeSvg([{ from: 'a', to: 'ghost' }], mixLayout, mixTasks, new Set()).indexOf('data-from') < 0);
const svgAll = edgeSvg(mixEdges, mixLayout, mixTasks, new Set(['a', 'c']));
check('三条边各一条 path（marker 内的 <path> 不计）', (svgAll.match(/data-from=/g) || []).length === 3);
check('三条边各配一个箭头 marker-end', (svgAll.match(/marker-end=/g) || []).length === 3);

console.log('\n[汇总] ' + pass + ' 通过 / ' + fail + ' 失败');
if (fail > 0) {
  console.error('失败项：\n  - ' + failures.join('\n  - '));
  process.exit(1);
}
console.log('edge-renderer 自测全绿。');
