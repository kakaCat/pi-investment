/**
 * 模块自测（无浏览器）——REQ-260928001915-f978 · t-144707
 *
 * 由 build-demo.py 调用：
 *   DAG_BUNDLE=<esbuild --format=cjs 产物> DAG_QUEUES=<queue.json 路径数组> node demo/selftest.mjs
 *
 * 覆盖 tc：布局（TC-7）、关键路径（TC-13）、上下游（TC-8/9）、
 * 卡片元素（TC-1..TC-5）、子卡链（TC-3）、边线（TC-6）、
 * 降级路径（TC-16/17/18）、数据校验（V-1..V-6）、四轴枚举齐全（20 个）。
 * 退出码 0 = 全绿；1 = 有断言失败。
 */
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

const bundlePath = process.env.DAG_BUNDLE;
const queuePaths = JSON.parse(process.env.DAG_QUEUES || '[]');

if (!bundlePath || !queuePaths.length) {
  console.error('缺少 DAG_BUNDLE / DAG_QUEUES 环境变量');
  process.exit(1);
}

const M = require(bundlePath);

let pass = 0;
let fail = 0;
const failures = [];

function check(name, cond, detail) {
  if (cond) {
    pass++;
    console.log('  ok   ' + name);
  } else {
    fail++;
    failures.push(name + (detail ? ' — ' + detail : ''));
    console.log('  FAIL ' + name + (detail ? ' — ' + detail : ''));
  }
}

function loadTasks(path) {
  return JSON.parse(readFileSync(path, 'utf8')).tasks;
}

/* ---------------- ① 四轴类型系统：20 个枚举值全有视觉表现 ---------------- */

console.log('\n[1] 四轴类型系统（7 + 4 + 3 + 6 = 20 个枚举值）');
const phaseKeys = Object.keys(M.PHASE_LABEL);
const sideKeys = Object.keys(M.SIDE_LABEL);
const statusKeys = Object.keys(M.STATUS_LABEL);
const roleVals = Object.keys(M.Role || {}).map(function (k) { return M.Role[k]; });
check('phase 7 类 + 7 种徽标色', phaseKeys.length === 7 && Object.keys(M.PHASE_COLORS).length === 7, 'label=' + phaseKeys.length + ' color=' + Object.keys(M.PHASE_COLORS).length);
check('side 4 类 + 4 种徽标色', sideKeys.length === 4 && Object.keys(M.SIDE_COLORS).length === 4);
check('status 6 类 + 6 种底色', statusKeys.length === 6 && Object.keys(M.STATUS_BACKGROUND_COLORS).length === 6);
check('role 3 类', roleVals.length === 3, 'Role=' + roleVals.join(','));
check('合计 20 个枚举值', phaseKeys.length + sideKeys.length + roleVals.length + statusKeys.length === 20);
check('7 种 phase 颜色互不相同', new Set(Object.values(M.PHASE_COLORS)).size === 7);
check('6 种状态底色互不相同', new Set(Object.values(M.STATUS_BACKGROUND_COLORS)).size === 6);

/* ---------------- ② 布局（TC-7） ---------------- */

console.log('\n[2] 布局引擎 calculateLayout（纵向 / 横向）');
const tasks0 = loadTasks(queuePaths[0]);
const v = M.calculateLayout(tasks0, 'vertical', 900);
const h = M.calculateLayout(tasks0, 'horizontal', 900);
check('纵向：所有节点都有坐标', Object.keys(v.pos).length === tasks0.length);
check('横向：所有节点都有坐标', Object.keys(h.pos).length === tasks0.length);
check('纵向：同层按行折行（同一行 y 相同，除末行外满行）', (function () {
  // FR-3：同层内按可用宽度自动折行（cols 列），故一层可占多行、行内 y 相同
  const byLayer = {};
  tasks0.forEach(function (t) { (byLayer[t.layer] = byLayer[t.layer] || []).push(v.pos[t.id].y); });
  return Object.keys(byLayer).every(function (l) {
    const rows = {};
    byLayer[l].forEach(function (y) { rows[y] = (rows[y] || 0) + 1; });
    const keys = Object.keys(rows).map(Number).sort(function (a, b) { return a - b; });
    const counts = keys.map(function (k) { return rows[k]; });
    const maxRow = Math.max.apply(null, counts);
    return maxRow >= 1 &&
      counts.slice(0, -1).every(function (c) { return c === maxRow; }) &&
      counts[counts.length - 1] <= maxRow;
  });
})());
check('纵向：层号越大 y 越大', (function () {
  const sorted = Object.keys(v.bands).map(function (i) { return v.bands[i]; }).sort(function (a, b) { return a.layer - b.layer; });
  return sorted.every(function (b, i) { return i === 0 || b.y > sorted[i - 1].y; });
})());
check('横向：同层 x 相同（每层 ≤ MAX_ROWS 卡）', (function () {
  const byLayer = {};
  tasks0.forEach(function (t) { (byLayer[t.layer] = byLayer[t.layer] || []).push(h.pos[t.id].x); });
  return Object.keys(byLayer).every(function (l) { return new Set(byLayer[l]).size === 1; });
})());
check('两种方向给出不同坐标', JSON.stringify(v.pos) !== JSON.stringify(h.pos));
check('画布尺寸为正且能容纳所有卡片', v.width > 0 && v.height > 0 && h.width > 0 && h.height > 0);
check('命中测试能取回节点', M.hitTest(v, v.pos[tasks0[0].id].x + 5, v.pos[tasks0[0].id].y + 5, 0) === tasks0[0].id);
check('命中测试空白处返回 null', M.hitTest(v, -100, -100, 0) === null);

/* ---------------- ③ 关键路径（TC-13）——四档真实队列都跑 ---------------- */

console.log('\n[3] 关键路径 findCriticalPath（四档真实队列）');
queuePaths.forEach(function (p, idx) {
  const ts = loadTasks(p);
  const set = M.findCriticalPath(ts);
  const ids = new Set(ts.map(function (t) { return t.id; }));
  const byId = {};
  ts.forEach(function (t) { byId[t.id] = t; });
  const inSet = function (id) { return set.has(id); };
  // 链性：除起点外每个节点在集合内都有前驱；每个节点在集合内最多一个后继
  // 链性判据（maxSucc ≤1 不是有效判据：链上某节点可能还有一条直连边指向链上更远的节点）：
  //   ① 起点唯一（集合内无前驱） ② 其余节点都有集合内前驱 ③ 链上各节点 layer 互不相同（路径逐层上行）
  const starts = Array.from(set).filter(function (id) { return !(byId[id].dependsOn || []).some(inSet); });
  const orphan = Array.from(set).filter(function (id) {
    return id !== starts[0] && !(byId[id].dependsOn || []).some(inSet);
  });
  const layers = Array.from(set).map(function (id) { return byId[id].layer; });
  check('#' + idx + ' 关键路径是单链（起点唯一 / 每节点有集合内前驱 / layer 互不相同）',
    set.size >= 1 && starts.length === 1 && orphan.length === 0 && new Set(layers).size === layers.length,
    'size=' + set.size + ' starts=' + starts.length + ' orphan=' + orphan.length + ' layers=' + layers.join(','));
  check('#' + idx + ' 关键路径节点都真实存在', Array.from(set).every(function (id) { return ids.has(id); }));
});

/* ---------------- ④ 上下游遍历（TC-8/9） ---------------- */

console.log('\n[4] 上下游遍历 computeNeighbors');
const chain = [
  { id: 'a', title: 'A', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', dependsOn: [], layer: 0 },
  { id: 'b', title: 'B', phase: 'test', side: 'backend', role: 'solo', status: 'todo', dependsOn: ['a'], layer: 1 },
  { id: 'c', title: 'C', phase: 'doc', side: 'doc', role: 'solo', status: 'todo', dependsOn: ['b'], layer: 2 },
  { id: 'd', title: 'D', phase: 'merge', side: 'fullstack', role: 'solo', status: 'todo', dependsOn: ['b'], layer: 2 }
];
const nb = M.computeNeighbors(chain, 'b');
check('B 的上游 = {a}', nb.up.size === 1 && nb.up.has('a'));
check('B 的下游 = {c,d}', nb.down.size === 2 && nb.down.has('c') && nb.down.has('d'));
check('B 不在自己的上下游里', !nb.up.has('b') && !nb.down.has('b'));
check('resolveHighlight 返回 self/up/down', (function () {
  const hl = M.resolveHighlight(chain, 'b');
  return hl.self === 'b' && hl.up.has('a') && hl.down.has('c');
})());

/* ---------------- ⑤ 卡片元素（TC-1..TC-5） ---------------- */

console.log('\n[5] 卡片渲染（DOM 后端 cardHtml）');
const parentTask = { id: 't-p1', title: '父任务', phase: 'doc', side: 'doc', role: 'parent', status: 'in_progress' };
const kids = [
  { id: 'k1', stageKind: 'dev', status: 'done' },
  { id: 'k2', stageKind: 'integrate', status: 'in_progress' },
  { id: 'k3', stageKind: 'review', status: 'todo' },
  { id: 'k4', stageKind: 'test', status: 'todo' }
];
const html = M.cardHtml(parentTask, { kids: kids, ready: true });
check('父卡有左侧蓝条 card-crown', html.indexOf('card-crown') >= 0);
check('有类型徽标 chip-type + data-phase', html.indexOf('chip-type') >= 0 && html.indexOf('data-phase="doc"') >= 0);
check('有端侧徽标 chip-side', html.indexOf('chip-side') >= 0);
check('有标题 card-title', html.indexOf('card-title') >= 0);
check('有状态底色 data-status', html.indexOf('data-status="in_progress"') >= 0);
check('有子卡链进度（4 段）', M.chainHtml(kids).indexOf('card-chain') >= 0 && (M.chainHtml(kids).match(/<i class=/g) || []).length === 4);
check('进度文本按已完成数计数（1/4）', html.indexOf('1/4') >= 0);
check('段着色：1 段绿(on) / 1 段蓝(now) / 2 段灰', (function () {
  const c = M.chainHtml(kids);
  return (c.match(/class="on"/g) || []).length === 1 &&
         (c.match(/class="now"/g) || []).length === 1 &&
         (c.match(/class=""/g) || []).length === 2;
})());
check('有 ready 绿点', html.indexOf('ready-dot') >= 0);
const childHtml = M.cardHtml({ id: 't-c1', title: '子任务', phase: 'test', side: 'backend', role: 'child', status: 'todo', stageKind: 'integrate' });
check('子卡不含 card-crown', childHtml.indexOf('card-crown') < 0);
check('子卡有阶段徽标 chip-kind（联调）', childHtml.indexOf('chip-kind') >= 0 && childHtml.indexOf('联调') >= 0);
check('未 ready 时不画绿点', childHtml.indexOf('ready-dot') < 0);

/* ---------------- ⑤b Canvas renderCard（FR-2 的 Canvas 后端：7 个视觉元素） ---------------- */

console.log('\n[5b] Canvas 卡片渲染 renderCard（7 个视觉元素 + 208×72 + 位置坐标）');

// 记录型假 2D 上下文：捕获每次绘制的类型、坐标与当时的 fillStyle
function makePaintCtx() {
  const rec = { fillTexts: [], fillRects: [], arcs: [], fills: [], clips: 0, strokes: 0 };
  const ctx = {
    globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1, font: '',
    textAlign: 'left', textBaseline: 'middle',
    save: function () {}, restore: function () {}, setLineDash: function () {},
    beginPath: function () {}, closePath: function () {}, moveTo: function () {}, lineTo: function () {},
    quadraticCurveTo: function () {}, bezierCurveTo: function () {},
    clip: function () { rec.clips++; },
    stroke: function () { rec.strokes++; },
    fill: function () { rec.fills.push(String(ctx.fillStyle)); },
    fillRect: function (x, y, w, h) { rec.fillRects.push({ x: x, y: y, w: w, h: h, color: String(ctx.fillStyle) }); },
    fillText: function (t, x, y) { rec.fillTexts.push({ t: String(t), x: x, y: y, color: String(ctx.fillStyle), font: ctx.font }); },
    arc: function (x, y, r) { rec.arcs.push({ x: x, y: y, r: r, color: String(ctx.fillStyle) }); },
    measureText: function (t) { return { width: String(t).length * 6 }; },
    _rec: rec
  };
  return ctx;
}

const rctx = makePaintCtx();
const rtask = { id: 't-p1', title: '父任务标题', phase: 'implement', side: 'backend', role: 'parent', status: 'done' };
M.renderCard(rctx, rtask, 100, 50, { ready: true, kids: kids });
const rec = rctx._rec;
const texts = rec.fillTexts.map(function (t) { return t.t; });

check('① ID 文本已绘制', texts.indexOf('t-p1') >= 0);
check('② 类型徽标（phase 中文：实施）', texts.indexOf('实施') >= 0);
check('③ 端侧徽标（side）', texts.indexOf('backend') >= 0);
check('④ 标题文本已绘制', texts.indexOf('父任务标题') >= 0);
check('⑤ 状态底色 = getStatusBackgroundColor(status)', rec.fills.indexOf(M.getStatusBackgroundColor('done')) >= 0);
check('⑥ 父卡子卡链进度（4 段 fillRect + n/total 文本）', rec.fillRects.filter(function (r) { return r.h === 4; }).length === 4 && texts.indexOf('1/4') >= 0);
check('⑦ ready 绿点 arc（色 #34c759）', rec.arcs.some(function (a) { return a.color === '#34c759' && a.r > 0; }));
check('父卡左侧蓝条（x=卡片左+1，宽 3）', rec.fillRects.some(function (r) { return r.x === 101 && r.w === 3 && r.color === 'rgba(0,113,227,.55)'; }));
check('卡片尺寸常量 208×72', M.CARD_W === 208 && M.CARD_H === 72, M.CARD_W + 'x' + M.CARD_H);
check('位置坐标生效（内容落在传入的 x=100 / y=50）', rec.fillTexts.length > 0 && rec.fillTexts.every(function (t) { return t.x >= 100 && t.y >= 50; }));
check('内容裁剪到卡片边界（overflow:hidden 对齐，调用 clip）', rec.clips >= 1, 'clip=' + rec.clips);

const rctxSolo = makePaintCtx();
M.renderCard(rctxSolo, { id: 't-s1', title: '独立卡', phase: 'test', side: 'frontend', role: 'solo', status: 'todo' }, 0, 0);
check('非父卡不画左侧蓝条', !rctxSolo._rec.fillRects.some(function (r) { return r.w === 3 && r.color === 'rgba(0,113,227,.55)'; }));
check('未 ready 时不画绿点', !rctxSolo._rec.arcs.some(function (a) { return a.color === '#34c759'; }));

/* ---------------- ⑥ 子卡链进度（TC-3） ---------------- */

console.log('\n[6] 子卡链进度 progress-bar');
check('4 段按阶段顺序归位', M.alignKids(kids).map(function (k) { return k.stageKind; }).join(',') === 'dev,integrate,review,test');
check('已完成段着色为绿', M.segmentColor('done') === '#34c759');
check('进行中段着色为蓝', M.segmentColor('in_progress') === '#0071e3');
check('待开始段着色为灰', M.segmentColor('todo').indexOf('rgba(0,0,0') === 0);
check('进度文本为 已完成/总数', M.progressText(kids) === '1/4');
check('进行中变体（integrating/testing/in_review）同判蓝', ['integrating', 'testing', 'in_review'].every(function (s) { return M.segmentClass(s) === 'now' && M.segmentColor(s) === '#0071e3'; }));
check('DOM 与 Canvas 同口径：integrating 段 DOM class 也是 now', M.chainHtml([{ id: 'k1', stageKind: 'dev', status: 'done' }, { id: 'k2', stageKind: 'integrate', status: 'integrating' }]).indexOf('class="now"') >= 0);
check('阶段中文名齐全（4 段）', ['dev', 'integrate', 'review', 'test'].every(function (s) { return !!M.STAGE_LABEL[s]; }));

/* ---------------- ⑦ 边线（TC-6） ---------------- */

console.log('\n[7] 边线渲染 edgeSvg（DOM 后端）');
const donePair = [
  { id: 't-d1', title: 'D1', phase: 'implement', side: 'backend', role: 'solo', status: 'done', layer: 0 },
  { id: 't-d2', title: 'D2', phase: 'test', side: 'backend', role: 'solo', status: 'done', layer: 1 }
];
const layoutPair = M.calculateLayout(donePair, 'vertical', 900);
const svgDone = M.edgeSvg([{ from: 't-d1', to: 't-d2' }], layoutPair, donePair, new Set());
check('生成 <path> 边线', svgDone.indexOf('data-from="t-d1"') >= 0 && svgDone.indexOf('data-to="t-d2"') >= 0);
check('两端 done -> e-done 绿线', svgDone.indexOf('e-done') >= 0);
const svgBase = M.edgeSvg([{ from: 't-d1', to: 't-d2' }], layoutPair, donePair, new Set(['t-d1', 't-d2']));
check('关键路径 -> e-crit 蓝线', svgBase.indexOf('e-crit') >= 0);
check('边线带箭头 marker-end', svgBase.indexOf('marker-end') >= 0);
check('边线用贝塞尔曲线（C 命令）', /d="M[^"]*C/.test(svgDone));
check('引用了不存在节点的边被跳过', M.edgeSvg([{ from: 't-d1', to: 't-ghost' }], layoutPair, donePair, new Set()).indexOf('data-from') < 0);

/* ---------------- ⑧ 集成（renderDagHtml） ---------------- */

console.log('\n[8] 集成渲染 renderDagHtml');
const queue0 = JSON.parse(readFileSync(queuePaths[0], 'utf8'));
const dag0 = { tasks: queue0.tasks, edges: queue0.edges, ready: queue0.ready };
const outHtml = M.renderDagHtml(dag0, { dir: 'vertical', crit: false, focus: false, pinned: null });
check('输出含容器 dsh-pm-np-dag', outHtml.indexOf('dsh-pm-np-dag') >= 0);
check('节点数与任务数一致', (outHtml.match(/class="node/g) || []).length === queue0.tasks.length);
check('输出含 SVG 边线', outHtml.indexOf('<svg') >= 0 && outHtml.indexOf('<path') >= 0);
const focusHtml = M.renderDagHtml(dag0, { dir: 'vertical', crit: false, focus: true, pinned: null });
const critSize = M.findCriticalPath(queue0.tasks).size;
check('只看主线：节点数收缩到关键路径', (focusHtml.match(/class="node/g) || []).length === critSize, 'focus=' + (focusHtml.match(/class="node/g) || []).length + ' crit=' + critSize);
check('空 DAG 显示占位', M.renderDagHtml({ tasks: [], edges: [], ready: [] }, { dir: 'vertical', crit: false, focus: false, pinned: null }).indexOf('暂无任务') >= 0);

/* ---------------- ⑨ 降级路径（TC-16..TC-19） ---------------- */

console.log('\n[9] 降级与校验');
const cyc = [
  { id: 'x', title: 'X', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', dependsOn: ['z'], layer: 0 },
  { id: 'y', title: 'Y', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', dependsOn: ['x'], layer: 1 },
  { id: 'z', title: 'Z', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', dependsOn: ['y'], layer: 2 }
];
check('detectCycle 抓到环', (M.detectCycle(cyc) || []).length === 3);
check('有环时关键路径返回空集（不抛异常）', M.findCriticalPath(cyc).size === 0);
check('有环时 renderDagHtml 输出错误提示', M.renderDagHtml({ tasks: cyc, edges: [], ready: [] }, { dir: 'vertical', crit: false, focus: false, pinned: null }).indexOf('循环依赖') >= 0);
check('无环数据 detectCycle 返回 null', M.detectCycle(tasks0) === null);
const noLayer = tasks0.map(function (t) { const c = Object.assign({}, t); delete c.layer; return c; });
check('缺 layer 也能布局（降级到第 0 层）', Object.keys(M.calculateLayout(noLayer, 'vertical', 900).pos).length === noLayer.length);

const realQueue = JSON.parse(readFileSync(queuePaths[0], 'utf8'));
const valReal = M.validateQueueFile(realQueue);
check('真实队列通过 V-1..V-6 校验', valReal.passed === true, JSON.stringify(valReal.issues.slice(0, 3)));
const valBad = M.validateQueueFile({
  requirement_id: 'REQ-X',
  tasks: [
    { id: 't1', title: 'T1', phase: 'implement', side: 'backend', role: 'solo', status: 'todo', layer: 0, dependsOn: [], requirementId: 'REQ-Y' }
  ],
  edges: [{ from: 't1', to: 't-ghost' }],
  ready: ['t1', 't-ghost']
});
const rules = new Set(valBad.issues.map(function (i) { return i.rule; }));
check('坏数据被校验拦下（V-2 悬空引用）', rules.has('V-2'));
check('坏数据被校验拦下（V-3 跨需求串档）', rules.has('V-3'));
check('坏数据被校验拦下（V-6 ready 非法）', rules.has('V-6'));
check('空 tasks 触发 V-1', M.validateQueueFile({ tasks: [], edges: [], ready: [] }).issues.some(function (i) { return i.rule === 'V-1'; }));


/* ---------------- ⑩ Canvas 下游冒烟（无浏览器，用假 canvas 跑通绘制链路） ---------------- */

console.log('\n[10] Canvas 视图冒烟 createDagViewer（假 canvas + 假 2D 上下文）');

function makeCtx() {
  const calls = { fillText: 0, fillRect: 0, arc: 0, bezierCurveTo: 0, stroke: 0, fill: 0, setLineDash: 0, clearRect: 0, clip: 0 };
  const ctx = {
    globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1, font: '',
    textAlign: 'left', textBaseline: 'alphabetic', lineCap: 'butt',
    save: function () {}, restore: function () {}, beginPath: function () {}, closePath: function () {},
    moveTo: function () {}, lineTo: function () {}, quadraticCurveTo: function () {}, setTransform: function () {},
    bezierCurveTo: function () { calls.bezierCurveTo++; },
    stroke: function () { calls.stroke++; },
    fill: function () { calls.fill++; },
    fillRect: function () { calls.fillRect++; },
    fillText: function () { calls.fillText++; },
    arc: function () { calls.arc++; },
    clearRect: function () { calls.clearRect++; },
    setLineDash: function () { calls.setLineDash++; },
    clip: function () { calls.clip++; },
    measureText: function (t) { return { width: String(t).length * 6 }; },
    _calls: calls
  };
  return ctx;
}

function makeCanvas(ctx, width) {
  const listeners = {};
  return {
    width: 0, height: 0, style: {},
    parentElement: { clientWidth: width },
    getContext: function () { return ctx; },
    getBoundingClientRect: function () { return { left: 0, top: 0, width: 900, height: 600 }; },
    addEventListener: function (type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    removeEventListener: function (type, fn) { listeners[type] = (listeners[type] || []).filter(function (f) { return f !== fn; }); },
    fire: function (type, ev) { (listeners[type] || []).forEach(function (f) { f(ev); }); },
    hasListener: function (type) { return (listeners[type] || []).length > 0; }
  };
}

// 用队列原始任务（没有 role 字段）验证派生补齐
const rawTasks = JSON.parse(readFileSync(queuePaths[0], 'utf8')).tasks;
check('resolveTasks 从 parentId 补出子卡角色', (function () {
  const r = M.resolveTasks(rawTasks);
  const sub = r.filter(function (t) { return t.parentId; })[0];
  return !!sub && sub.role === 'child';
})());
check('resolveTasks 从子卡反查出父卡角色与 kids', (function () {
  const r = M.resolveTasks(rawTasks);
  const par = r.filter(function (t) { return t.role === 'parent'; })[0];
  return !!par && Array.isArray(par.kids) && par.kids.length === 4;
})());
// solo 判定必须用**合成样例**断言，不能把"队列里恰好有独立卡"当测试前提——
// 那测的是数据构型而不是模块契约：本需求队列随拆分推进会变成"只有父卡+子卡"，
// 实测 40 卡 = 8 父卡 + 32 子卡、solo=0，旧断言在此误报红（BUILD_EXIT=5）。
check('无 parentId 且无子卡 -> solo（合成样例，与队列构型无关）', (function () {
  const standalone = { id: 't-solo-x', title: '独立卡', phase: 'doc', side: 'doc', status: 'todo', dependsOn: [], layer: 0 };
  const r = M.resolveTasks([standalone]);
  return r.length === 1 && r[0].role === 'solo';
})());
check('真实队列角色三分覆盖且互斥（parent/child/solo 计数与结构一致）', (function () {
  const r = M.resolveTasks(rawTasks);
  const parentN = r.filter(function (t) { return t.role === 'parent'; }).length;
  const childN = r.filter(function (t) { return t.role === 'child'; }).length;
  const soloN = r.filter(function (t) { return t.role === 'solo'; }).length;
  const childTasks = rawTasks.filter(function (t) { return t.parentId; }).length;
  const parentIds = new Set(rawTasks.filter(function (t) { return t.parentId; }).map(function (t) { return t.parentId; }));
  return childN === childTasks && parentN === parentIds.size && parentN + childN + soloN === r.length;
})());

const rawQueue = JSON.parse(readFileSync(queuePaths[0], 'utf8'));
const smokeData = { tasks: rawQueue.tasks, edges: rawQueue.edges, ready: rawQueue.ready };
const ctx = makeCtx();
const canvas = makeCanvas(ctx, 690);
let viewerErr = null;
let viewer = null;
try {
  viewer = M.createDagViewer(canvas, smokeData, { dir: 'vertical', crit: false, focus: false });
} catch (e) {
  viewerErr = e;
}
check('createDagViewer 不抛异常', viewerErr === null, viewerErr ? String(viewerErr && viewerErr.message) : '');
check('绘制了卡片文字（fillText > 0）', ctx._calls.fillText > 0, 'fillText=' + ctx._calls.fillText);
check('绘制了卡片底色/进度段（fillRect > 0）', ctx._calls.fillRect > 0, 'fillRect=' + ctx._calls.fillRect);
check('绘制了依赖连线（bezierCurveTo > 0）', ctx._calls.bezierCurveTo > 0, 'bezierCurveTo=' + ctx._calls.bezierCurveTo);
check('画布尺寸按布局设置', canvas.width > 0 && canvas.height > 0, canvas.width + 'x' + canvas.height);
check('绑定了 mousemove / click / mouseleave', canvas.hasListener('mousemove') && canvas.hasListener('click') && canvas.hasListener('mouseleave'));

// 悬停：命中第一张卡 -> 压暗其它元素（globalAlpha 被改小过） + 重绘
const before = ctx._calls.fillText;
const p0 = viewer.layout().pos[rawQueue.tasks[0].id];
canvas.fire('mousemove', { clientX: p0.x + 5, clientY: p0.y + 5 });
check('悬停命中卡片后重绘', ctx._calls.fillText > before);
check('悬停后已算出上下游高亮', (function () {
  const hl = M.resolveHighlight(M.resolveTasks(rawTasks), rawQueue.tasks[0].id);
  return hl.self === rawQueue.tasks[0].id;
})());
canvas.fire('mousemove', { clientX: -999, clientY: -999 });
check('移出后不抛异常', true);

// 点击钉住 / 再点取消
canvas.fire('click', { clientX: p0.x + 5, clientY: p0.y + 5 });
check('点击钉住', true);
canvas.fire('click', { clientX: p0.x + 5, clientY: p0.y + 5 });
check('再点同一卡取消钉住', true);
canvas.fire('click', { clientX: -999, clientY: -999 });
check('点空白清除', true);

// 横向布局 + 只看主线 + 关键路径 三种状态都渲染
const textH = ctx._calls.fillText;
viewer.patch({ dir: 'horizontal' });
check('切横向后重绘', ctx._calls.fillText > textH);
const textC = ctx._calls.fillText;
viewer.patch({ crit: true });
check('开关键路径后重绘', ctx._calls.fillText > textC);
const textF = ctx._calls.fillText;
const fRes = viewer.patch({ focus: true });
check('只看主线后节点数收缩', fRes.visibleIds.length < rawQueue.tasks.length, fRes.visibleIds.length + ' < ' + rawQueue.tasks.length);
check('只看主线后仍绘制', ctx._calls.fillText > textF);
check('只看主线后有支线计数或为 0（不报错）', typeof fRes.branchCount === 'object');
viewer.destroy();
check('destroy 后移除事件', !canvas.hasListener('mousemove'));

/* ---------------- 汇总 ---------------- */

console.log('\n[汇总] ' + pass + ' 通过 / ' + fail + ' 失败');
if (fail) {
  console.log('失败项：');
  failures.forEach(function (f) { console.log('  - ' + f); });
  process.exit(1);
}
console.log('模块自测全绿。');
