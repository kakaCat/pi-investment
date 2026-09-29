/**
 * 父卡子卡链进度条（REQ-260928001915-f978 · t-d379c7 · FR-7）
 *
 * 父卡底部的一条 4 段进度条，对应固定的子卡链阶段：
 *   dev（研发） → integrate（联调） → review（复核） → test（测试）
 * 每段按该阶段子卡的状态着色：已完成=绿、进行中=蓝、待开始=灰，
 * 右侧跟一段 "已完成数/总数" 文本。
 *
 * 两个后端：
 * - renderProgressBar(ctx, ...)  Canvas 2D
 * - chainHtml(kids)              DOM 字符串（pmboard 泳道卡片，见 interfaces.md）
 */
import { STATUS_LABEL } from './card-types';

/** 子卡链的固定四阶段（顺序即渲染顺序） */
export type StageId = 'dev' | 'integrate' | 'review' | 'test';

/** 四阶段顺序表：dev → integrate → review → test */
export const STAGE_ORDER: StageId[] = ['dev', 'integrate', 'review', 'test'];

/** 阶段中文名（含子卡模板里可能出现的其它阶段，未知阶段原样回显） */
export const STAGE_LABEL: Record<string, string> = {
  dev: '研发',
  integrate: '联调',
  review: '复核',
  test: '测试',
  repro: '复现',
  fix: '修复',
  regress: '回归',
  probe: '探针',
  collect: '采集',
  analyze: '分析',
  prepare: '准备',
  run: '运行',
  verify: '验证',
  change: '变更',
  dryrun: '演练',
  apply: '应用'
};

/** 每段的验收含义（tooltip 与自测断言用，逐段可核对） */
export const STAGE_HINT: Record<string, string> = {
  'dev': '研发完成才进入联调',
  'integrate': '联调通过才进入复核',
  'review': '复核通过才进入测试',
  'test': '测试全绿才算交付'
};

/** 进度条上的一段（父卡 kids 的最小形状） */
export interface KidLike {
  id?: string;
  stageKind?: string;
  status: string;
  title?: string;
}

/**
 * 进度段的"进行中"状态集合（卡片已有状态里凡是"在跑"的都算进行中）。
 * 单一事实源：Canvas 着色与 DOM class 都从这里派生，杜绝两个后端口径分叉
 * （父卡子卡链的联调/测试阶段子卡状态是 integrating/testing，不是 in_progress）。
 */
export const IN_PROGRESS_STATUSES: string[] = ['in_progress', 'integrating', 'testing', 'in_review'];

/** 进度段三态：on=已完成 / now=进行中 / ''=待开始（DOM class 与颜色共用） */
export type SegmentClass = 'on' | 'now' | '';

/** 状态 → 三态（Canvas 与 DOM 两个后端共用） */
export function segmentClass(status: string): SegmentClass {
  if (status === 'done') return 'on';
  if (IN_PROGRESS_STATUSES.indexOf(status) >= 0) return 'now';
  return '';
}

/** 三态 → 颜色：已完成=绿 / 进行中=蓝 / 待开始=灰 */
export const SEGMENT_COLOR: Record<SegmentClass, string> = {
  on: '#34c759',
  now: '#0071e3',
  '': 'rgba(0,0,0,.12)'
};

/** 一段的颜色：done=绿 / 进行中=蓝 / 其余=灰 */
export function segmentColor(status: string): string {
  return SEGMENT_COLOR[segmentClass(status)];
}

/** "已完成数/总数"，如 "2/4" */
export function progressText(kids: KidLike[]): string {
  const total = kids.length;
  const done = kids.filter(function (k) { return k.status === 'done'; }).length;
  return done + '/' + total;
}

/**
 * 按 STAGE_ORDER 归位子卡：先把已知阶段按固定顺序排好，未知阶段追加在尾部。
 * 这样即使父卡临时少了某个阶段的子卡，进度条也不会错位。
 */
export function alignKids(kids: KidLike[]): KidLike[] {
  const byStage: Record<string, KidLike> = {};
  const rest: KidLike[] = [];
  kids.forEach(function (k) {
    const s = k.stageKind || '';
    if (STAGE_ORDER.indexOf(s as StageId) >= 0 && !byStage[s]) byStage[s] = k;
    else rest.push(k);
  });
  const out: KidLike[] = [];
  STAGE_ORDER.forEach(function (s) { if (byStage[s]) out.push(byStage[s]); });
  return out.concat(rest);
}

/** 在画布上绘制进度条（x,y 为卡片左上角，w 为卡片内可用宽度） */
export function renderProgressBar(
  ctx: CanvasRenderingContext2D,
  kids: KidLike[],
  x: number,
  y: number,
  w: number
): void {
  if (!kids || !kids.length) return;
  const aligned = alignKids(kids);
  const gap = 3;
  const barW = Math.max(8, w - 34);
  const segW = Math.max(3, (barW - gap * (aligned.length - 1)) / aligned.length);
  const barH = 4;

  ctx.save();
  aligned.forEach(function (k, i) {
    ctx.fillStyle = segmentColor(k.status);
    const sx = x + i * (segW + gap);
    ctx.fillRect(sx, y, segW, barH);
  });

  // 进度文本：已完成数/总数
  ctx.fillStyle = 'rgba(0,0,0,.45)';
  ctx.font = '10px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';
  ctx.fillText(progressText(aligned), x + w, y + barH / 2);
  ctx.restore();
}

/** DOM 版：卡片底部的子卡链进度（class 与 node-panel 样式表对齐） */
export function chainHtml(kids: KidLike[]): string {
  if (!kids || !kids.length) return '';
  const aligned = alignKids(kids);
  let s = '<div class="card-chain">';
  aligned.forEach(function (k) {
    const cls = segmentClass(k.status);
    const label = STAGE_LABEL[k.stageKind || ''] || k.stageKind || '';
    const status = STATUS_LABEL[k.status] || k.status;
    s += '<i class="' + cls + '" title="' + esc(label) + '：' + esc(status) + '"></i>';
  });
  s += '<span>' + progressText(aligned) + '</span></div>';
  return s;
}

/**
 * 卡片层泳道归属（2026-09-28 卡片层契约）。
 *
 * 为什么需要：泳道列原按 card.status 分列，而新式父卡的状态机只有 todo→in_progress→done
 * （PARENT_TRANSITIONS 对 integrating/testing/in_review 无出边），联调/复核/测试改由子卡
 * stageKind（dev/integrate/review/test）承载 ⇒ 那三列**结构性为空**（实测 54 个队列 711 张卡，
 * 落在 integrating/testing/in_review 的为 0，而同期 integrate/test 子卡各 49 张且全部 done）。
 *
 * 口径：非 in_progress 的卡按自身状态；无子卡的卡按自身状态（存量卡仍走五段状态机）；
 * 新式父卡按「链上第一个未完成子卡」的阶段归位；链已全绿而父卡未收尾 → 待复核列（把卡住的
 * 卡浮出来）。未知 stageKind（fix/regress/probe…）回落开发中。
 */
export const STAGE_LANE: Record<string, string> = {
  dev: 'in_progress',
  integrate: 'integrating',
  review: 'in_review',
  test: 'testing'
};

/** 卡 → 泳道列 key（与泳道列 key 同词汇：todo/in_progress/integrating/testing/in_review/done）。 */
export function laneOf(card: { status: string }, kids: KidLike[]): string {
  if (card.status !== 'in_progress' || kids.length === 0) return card.status;
  const aligned = alignKids(kids);
  const cur = aligned.filter(function (k) { return k.status !== 'done'; })[0];
  if (!cur) return 'in_review';
  return STAGE_LANE[cur.stageKind || ''] || 'in_progress';
}

/**
 * 是否「意图=chain 但链未生成」——只在卡**正在跑**、没有子卡、且未显式声明无链时成立。
 *
 * 为什么限定 in_progress：todo 卡开工时才懒展开，"还没链"是正常态；done 的存量卡属历史，
 * 大面积打标只会变噪声。`stages: []` = 显式 solo，永不打标 —— 这正是"不需子卡"与
 * "需要但未生成"必须分开的那条线。
 */
export function chainMissing(card: { status: string; stages?: readonly unknown[] }, kids: readonly unknown[]): boolean {
  if (kids.length > 0) return false;
  if (card.status !== 'in_progress') return false;
  return !(Array.isArray(card.stages) && card.stages.length === 0);
}

/** 折叠到卡片层的最小输入形状。 */
export interface CardLevelInput {
  id: string;
  parentId?: string;
  dependsOn?: string[];
}

/**
 * 折叠到卡片层（2026-09-28 卡片层契约）：DAG 只画顶层卡，子卡链折进卡底进度条。
 *
 * 边重路由：依赖里指向**子卡**的 → 上提到它的父卡；同一父卡内部的链边（dev→integrate→
 * review→test）折叠后成自环，直接丢弃；指向本队列外、画不出节点的悬空依赖一并丢弃。
 * 保留跨卡依赖——实测 73 条（22 条指向父卡、51 条指向存量卡），它们才是排期语义。
 * 实测收益（REQ-260924213231-b1c4）：65 节点/12 层 → 13 张顶层卡/9 层（原图 80% 节点是子卡）。
 */
export function collapseToCardLevel<T extends CardLevelInput>(tasks: T[]): { tops: T[]; deps: Record<string, string[]> } {
  const parentOf: Record<string, string> = {};
  tasks.forEach(function (t) { if (t.parentId) parentOf[t.id] = t.parentId; });
  const tops = tasks.filter(function (t) { return !t.parentId; });
  const isTop: Record<string, boolean> = {};
  tops.forEach(function (t) { isTop[t.id] = true; });
  const deps: Record<string, string[]> = {};
  tops.forEach(function (t) {
    const seen: Record<string, boolean> = {};
    const list: string[] = [];
    const add = function (raw: string): void {
      const o = parentOf[raw] || raw;
      if (o === t.id || !isTop[o] || seen[o]) return;
      seen[o] = true;
      list.push(o);
    };
    (t.dependsOn || []).forEach(add);
    // 子卡的跨卡依赖上提到父卡，否则折叠后会丢掉真实的跨卡顺序。
    tasks.forEach(function (k) { if (k.parentId === t.id) (k.dependsOn || []).forEach(add); });
    deps[t.id] = list;
  });
  return { tops: tops, deps: deps };
}

/** 最小 HTML 转义（DOM 后端共用） */
export function esc(s: unknown): string {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
