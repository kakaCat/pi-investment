/**
 * 边线渲染器（REQ-260928001915-f978 · t-e4e9db · FR-4）
 *
 * 按「任务状态 + 路径类型」给依赖连线着色：
 *   已完成链路（from 与 to 都 done）  绿色 rgba(52,199,89,.5)  1.3px
 *   普通连线                          灰色 rgba(0,0,0,.17)     1.2px
 *   关键路径                          蓝色 rgba(0,113,227,.75)  1.8px 加粗
 *   悬停高亮：上游 #ff9500 / 下游 #0071e3，2px
 *
 * 箭头降噪（2026-09-29 用户：「可以简化现在 dag 的箭头吗太多了」）：见 edgeTiers——
 * 每张卡只留**一条**入边画箭头，并列/冗余入边只留浅色线，跨层绕行线再虚化成短划。
 * 一条依赖都不删：画的是同一批边，变的只是箭头与浓度。
 *
 * 两个后端：
 * - renderEdges(ctx, ...)  Canvas 2D
 * - edgeSvg(...)           SVG 字符串（pmboard 泳道，见 design/interfaces.md）
 */
import type { CardData } from './card-types';
import { CARD_W, CARD_H, type LayoutResult, type LayoutDir, type Point } from './dag-layout';

/** 一条依赖边（from 是前置，to 是后继） */
export interface Edge {
  from: string;
  to: string;
}

export const EDGE_DONE = 'rgba(52,199,89,.5)';
export const EDGE_DONE_W = 1.3;
export const EDGE_BASE = 'rgba(0,0,0,.17)';
export const EDGE_BASE_W = 1.2;
export const EDGE_CRIT = 'rgba(0,113,227,.75)';
export const EDGE_CRIT_W = 1.8;
export const EDGE_UP = '#ff9500';
export const EDGE_DOWN = '#0071e3';
export const EDGE_HL_W = 2;
/** 降噪后的冗余边：无箭头、压到接近底色 */
export const EDGE_FAINT = 'rgba(0,0,0,.09)';
export const EDGE_FAINT_W = 1;
/** 降噪后的「已完成链路」——保留绿色语义，只是淡 */
export const EDGE_DONE_FAINT = 'rgba(52,199,89,.26)';
/** 跨层绕行边的短划间距 */
export const EDGE_DASH: number[] = [3, 4];

export interface NeighborSets {
  up: Set<string>;
  down: Set<string>;
}

export interface EdgeRenderOptions {
  /** 关键路径节点集合 */
  critSet?: Set<string>;
  /** 悬停高亮的上下游（null = 无高亮） */
  highlight?: NeighborSets | null;
  /** 是否 dimming（未高亮边线压暗） */
  dimmed?: boolean;
  /** 布局方向 */
  dir?: LayoutDir;
}

/** 端口分配：同一节点多条出/入边在卡边上铺开，避免全部挤在中心点 */
export interface Ports {
  /** 边序号 -> 出边在源卡边上的比例位置（0~1） */
  outF: Record<number, number>;
  /** 边序号 -> 入边在目标卡边上的比例位置（0~1） */
  inF: Record<number, number>;
}

export function allocatePorts(edges: Edge[], layout: LayoutResult, dir: LayoutDir): Ports {
  const outIdx: Record<string, number[]> = {};
  const inIdx: Record<string, number[]> = {};
  edges.forEach(function (e, i) {
    if (!outIdx[e.from]) outIdx[e.from] = [];
    if (!inIdx[e.to]) inIdx[e.to] = [];
    outIdx[e.from].push(i);
    inIdx[e.to].push(i);
  });

  const frac = function (k: number, n: number): number {
    return n <= 1 ? 0.5 : 0.2 + 0.6 * k / (n - 1);
  };
  const axis = function (id: string): number {
    const p = layout.pos[id];
    if (!p) return 0;
    return dir === 'vertical' ? p.x : p.y;
  };

  const outF: Record<number, number> = {};
  const inF: Record<number, number> = {};

  Object.keys(outIdx).forEach(function (id) {
    const list = outIdx[id].slice().sort(function (a, b) { return axis(edges[a].to) - axis(edges[b].to); });
    list.forEach(function (ei, k) { outF[ei] = frac(k, list.length); });
  });
  Object.keys(inIdx).forEach(function (id) {
    const list = inIdx[id].slice().sort(function (a, b) { return axis(edges[a].from) - axis(edges[b].from); });
    list.forEach(function (ei, k) { inF[ei] = frac(k, list.length); });
  });

  return { outF: outF, inF: inF };
}

/** 边线几何：起止点 + 两个贝塞尔控制点 */
export interface EdgeGeometry {
  sx: number; sy: number;
  c1x: number; c1y: number;
  c2x: number; c2y: number;
  tx: number; ty: number;
}

export function edgeGeometry(
  from: Point,
  to: Point,
  outF: number,
  inF: number,
  dir: LayoutDir
): EdgeGeometry {
  if (dir === 'horizontal') {
    const sx = from.x + CARD_W;
    const sy = from.y + CARD_H * outF;
    const tx = to.x;
    const ty = to.y + CARD_H * inF;
    const dx = Math.max(20, (tx - sx) * 0.45);
    return { sx: sx, sy: sy, c1x: sx + dx, c1y: sy, c2x: tx - dx, c2y: ty, tx: tx, ty: ty };
  }
  const sx = from.x + CARD_W * outF;
  const sy = from.y + CARD_H;
  const tx = to.x + CARD_W * inF;
  const ty = to.y;
  const dy = Math.max(18, (ty - sy) * 0.45);
  return { sx: sx, sy: sy, c1x: sx, c1y: sy + dy, c2x: tx, c2y: ty - dy, tx: tx, ty: ty };
}

/** 一条边的样式判定：关键路径 > 已完成链路 > 普通 */
export function edgeStyle(
  e: Edge,
  byId: Record<string, CardData>,
  critSet: Set<string>,
  highlight: NeighborSets | null | undefined
): { color: string; width: number } {
  const a = byId[e.from];
  const b = byId[e.to];
  if (highlight) {
    const isUp = highlight.up.has(e.to) || highlight.up.has(e.from);
    const isDown = highlight.down.has(e.from);
    if (isUp) return { color: EDGE_UP, width: EDGE_HL_W };
    if (isDown) return { color: EDGE_DOWN, width: EDGE_HL_W };
  }
  if (critSet.has(e.from) && critSet.has(e.to)) return { color: EDGE_CRIT, width: EDGE_CRIT_W };
  if (a && b && a.status === 'done' && b.status === 'done') return { color: EDGE_DONE, width: EDGE_DONE_W };
  return { color: EDGE_BASE, width: EDGE_BASE_W };
}

/** 边级：A=唯一带箭头的入边（每卡一条）· B=并列/冗余入边 · C=跨层绕行边 */
export type EdgeTier = 'A' | 'B' | 'C';

/**
 * 给每条边定级（箭头降噪的唯一判据，Canvas / SVG 两个后端共用）。
 *
 * 规则：①关键路径边恒带箭头；②每张卡只留**一条**带箭头的入边——层级最高（最近一环）
 * 的那条前置，同层并列时取声明靠后的；③其余入边按跨层数分 B（相邻层）/ C（跨层绕行）。
 * 只影响箭头与浓度，**不删边**：依赖信息一条不少。
 */
export function edgeTiers(
  edges: Edge[],
  layout: LayoutResult,
  critSet?: Set<string>,
  dir?: LayoutDir
): EdgeTier[] {
  const direction: LayoutDir = dir || layout.dir;
  const axis = function (id: string): number {
    const p = layout.pos[id];
    if (!p) return 0;
    return direction === 'vertical' ? p.y : p.x;
  };
  // 同一层 = 布局轴上的同一个坐标（层号写在轴坐标上）：去重排序后取索引当层号
  const levels: number[] = [];
  Object.keys(layout.pos).forEach(function (id) {
    const v = axis(id);
    if (levels.indexOf(v) < 0) levels.push(v);
  });
  levels.sort(function (a, b) { return a - b; });
  const layerOf = function (id: string): number {
    const i = levels.indexOf(axis(id));
    return i < 0 ? 0 : i;
  };

  // 每张卡选一条带箭头的入边：层级最高的前置；并列（同层）取声明靠后的那条
  const primary: Record<string, number> = {};
  edges.forEach(function (e, i) {
    const cur = primary[e.to];
    if (cur === undefined) { primary[e.to] = i; return; }
    const d = layerOf(e.from) - layerOf(edges[cur].from);
    if (d > 0 || (d === 0 && i > cur)) primary[e.to] = i;
  });

  const crit = critSet || new Set<string>();
  return edges.map(function (e, i) {
    if (crit.has(e.from) && crit.has(e.to)) return 'A' as EdgeTier;
    if (primary[e.to] === i) return 'A' as EdgeTier;
    return Math.abs(layerOf(e.to) - layerOf(e.from)) >= 2 ? 'C' as EdgeTier : 'B' as EdgeTier;
  });
}

/**
 * 箭头（画在终点，朝向由控制点 2 -> 终点 的方向决定）。
 * 画成两支张开的短线（chevron），与边线同色同粗，视觉上更轻。
 */
function drawArrow(
  ctx: CanvasRenderingContext2D,
  g: EdgeGeometry,
  color: string,
  width: number,
  dimmed: boolean
): void {
  const ang = Math.atan2(g.ty - g.c2y, g.tx - g.c2x);
  const size = 7;
  ctx.save();
  ctx.globalAlpha = dimmed ? 0.05 : 1;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(g.tx - size * Math.cos(ang - 0.42), g.ty - size * Math.sin(ang - 0.42));
  ctx.lineTo(g.tx, g.ty);
  ctx.lineTo(g.tx - size * Math.cos(ang + 0.42), g.ty - size * Math.sin(ang + 0.42));
  ctx.stroke();
  ctx.restore();
}

/** 复位到“普通连线”画笔，避免上一条边的样式泄漏到画布其它绘制 */
export function resetEdgePaint(ctx: CanvasRenderingContext2D): void {
  ctx.strokeStyle = EDGE_BASE;
  ctx.lineWidth = EDGE_BASE_W;
  ctx.lineCap = 'round';
  ctx.setLineDash([]);
}

/** Canvas 后端：绘制全部边线 */
export function renderEdges(
  ctx: CanvasRenderingContext2D,
  edges: Edge[],
  layout: LayoutResult,
  tasks: CardData[],
  opts?: EdgeRenderOptions
): number {
  const o = opts || {};
  const dir: LayoutDir = o.dir || layout.dir;
  const critSet = o.critSet || new Set<string>();
  const highlight = o.highlight || null;
  const ports = allocatePorts(edges, layout, dir);

  const byId: Record<string, CardData> = {};
  tasks.forEach(function (t) { byId[t.id] = t; });
  const tiers = edgeTiers(edges, layout, critSet, dir);

  ctx.save();
  ctx.lineCap = 'round';
  let drawn = 0;
  edges.forEach(function (e, i) {
    const from = layout.pos[e.from];
    const to = layout.pos[e.to];
    if (!from || !to) return;   // 边引用了不存在的节点：跳过（由校验层提示）
    drawn++;
    const st = edgeStyle(e, byId, critSet, highlight);
    const onHover = !!highlight &&
      (highlight.up.has(e.to) || highlight.up.has(e.from) || highlight.down.has(e.from));
    const dimmed = !!o.dimmed && st.color !== EDGE_UP && st.color !== EDGE_DOWN;
    const g = edgeGeometry(from, to, ports.outF[i], ports.inF[i], dir);

    // 降噪：只有 A 级边（每卡一条入边）画箭头；冗余边压淡成细线，跨层绕行再虚化。
    // 悬停命中的边例外——正在看的那条必须有箭头，否则读不出方向。
    const tier = tiers[i];
    const faint = tier !== 'A' && !onHover;
    const a = byId[e.from];
    const b = byId[e.to];
    const color = faint
      ? (a && b && a.status === 'done' && b.status === 'done' ? EDGE_DONE_FAINT : EDGE_FAINT)
      : st.color;
    const width = faint ? EDGE_FAINT_W : st.width;

    ctx.globalAlpha = dimmed ? 0.05 : 1;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.setLineDash(faint && tier === 'C' ? EDGE_DASH : []);
    ctx.beginPath();
    ctx.moveTo(g.sx, g.sy);
    ctx.bezierCurveTo(g.c1x, g.c1y, g.c2x, g.c2y, g.tx, g.ty);
    ctx.stroke();
    ctx.setLineDash([]);
    if (!faint) drawArrow(ctx, g, color, width, dimmed);
  });
  resetEdgePaint(ctx);
  ctx.restore();
  return drawn;
}

/** DOM 后端：SVG 字符串（marker + path，class 与样式表对齐） */
export function edgeSvg(
  edges: Edge[],
  layout: LayoutResult,
  tasks: CardData[],
  critSet: Set<string>,
  dir?: LayoutDir
): string {
  const direction: LayoutDir = dir || layout.dir;
  const ports = allocatePorts(edges, layout, direction);
  const byId: Record<string, CardData> = {};
  tasks.forEach(function (t) { byId[t.id] = t; });

  const markers =
    '<defs>' +
    '<marker id="m-base" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,1 L7,4 L0,7 z" fill="' + EDGE_BASE + '"/></marker>' +
    '<marker id="m-done" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,1 L7,4 L0,7 z" fill="' + EDGE_DONE + '"/></marker>' +
    '<marker id="m-crit" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6.5" markerHeight="6.5" orient="auto"><path d="M0,1 L7,4 L0,7 z" fill="' + EDGE_CRIT + '"/></marker>' +
    '</defs>';

  const tiers = edgeTiers(edges, layout, critSet, direction);
  let paths = '';
  edges.forEach(function (e, i) {
    const from = layout.pos[e.from];
    const to = layout.pos[e.to];
    if (!from || !to) return;
    const g = edgeGeometry(from, to, ports.outF[i], ports.inF[i], direction);
    const d = 'M' + g.sx + ',' + g.sy + ' C' + g.c1x + ',' + g.c1y + ' ' + g.c2x + ',' + g.c2y + ' ' + g.tx + ',' + g.ty;
    const st = edgeStyle(e, byId, critSet, null);
    const cls = st.color === EDGE_CRIT ? 'e-crit' : (st.color === EDGE_DONE ? 'e-done' : 'e-base');
    const mk = cls === 'e-crit' ? 'm-crit' : (cls === 'e-done' ? 'm-done' : 'm-base');
    // 与 Canvas 后端同口径：只有 A 级边挂箭头，冗余边加 e-faint，绕行边改短划
    const tier = tiers[i];
    const faint = tier === 'A' ? '' : ' e-faint';
    const dash = tier === 'C' ? ' stroke-dasharray="3 4"' : '';
    const arrow = tier === 'A' ? ' marker-end="url(#' + mk + ')"' : '';
    paths += '<path class="' + cls + faint + '" data-from="' + e.from + '" data-to="' + e.to +
      '" data-mk="' + mk + '" data-tier="' + tier + '" d="' + d + '"' + dash + arrow + '/>';
  });

  return '<svg class="edges" width="' + layout.width + '" height="' + layout.height + '">' + markers + paths + '</svg>';
}
