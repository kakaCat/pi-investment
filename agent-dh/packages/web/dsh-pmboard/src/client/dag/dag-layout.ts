/**
 * DAG 布局引擎（REQ-260928001915-f978 · t-4256bf · FR-3）
 *
 * 消费 queue.json 的 tasks（含 layer/dependsOn），为每个节点算出画布上的
 * 左上角坐标 (x, y) 与整张画布的宽高。两种布局方向：
 *
 * - 'vertical'   纵向：层级从上到下，**同层不折行**（每层一行，画布按最宽层展开，容器窄则横向滚动；
 *                 2026-09-29 用户裁定 C：会话面板「一行只能放 2 个」的限制去掉）
 * - 'horizontal' 横向：层级从左到右，同层纵向堆叠（最多 MAX_ROWS 行）
 *
 * 纯函数、无副作用：同一输入必得同一输出，可在 Node 里直接单测。
 */
import type { CardData } from './card-types';

/** 卡片尺寸（px，与原型 prototype.html 一致） */
export const CARD_W = 208;
export const CARD_H = 72;
/** 同层内间距 */
export const GAP_X = 14;
export const GAP_Y = 22;
/** 左侧层级标签（L0/L1…）留白 */
export const GUTTER = 42;
/** 层与层之间的额外间距 */
export const BAND_GAP = 30;
/** 画布内边距 */
export const PAD = 14;
/** 横向布局每列最多堆叠多少张卡 */
export const MAX_ROWS = 8;

/** 布局方向 */
export type LayoutDir = 'vertical' | 'horizontal';

export interface Point {
  x: number;
  y: number;
}

/** 层带：纵向布局下每层所占的纵向区间（用于在左侧画 L0/L1 标签） */
export interface Band {
  layer: number;
  y: number;
  count: number;
}

export interface LayoutResult {
  /** 节点 id -> 左上角坐标 */
  pos: Record<string, Point>;
  /** 每层的纵向区间 */
  bands: Band[];
  /** 画布宽度（px） */
  width: number;
  /** 画布高度（px） */
  height: number;
  /** 本次采用的布局方向 */
  dir: LayoutDir;
}

/** 按 layer 分组；缺 layer 的任务降到第 0 层（降级不崩） */
function groupByLayer(tasks: CardData[]): CardData[][] {
  const layers: CardData[][] = [];
  tasks.forEach(function (t) {
    const l = typeof t.layer === 'number' && t.layer >= 0 ? t.layer : 0;
    if (!layers[l]) layers[l] = [];
    layers[l].push(t);
  });
  return layers;
}

/** 前驱在本层内的平均序号（无前驱 = 0）；纯计算，不写回任务对象 */
function barycenter(t: CardData, order: Record<string, number>): number {
  const ps = (t.dependsOn || [])
    .filter(function (d) { return order[d] !== undefined; })
    .map(function (d) { return order[d]; });
  return ps.length
    ? ps.reduce(function (a, b) { return a + b; }, 0) / ps.length
    : 0;
}

/**
 * 同层内按前驱的平均序号排序，减少跨层连线交叉（迭代两轮足够收敛）。
 *
 * 排序键只存在局部数组里（不写 `_bary` 到任务对象上）——本模块声称纯函数，
 * 调用方的 CardData 必须保持不可变；否则 `calculateLayout(tasks)` 会静默给
 * 每个输入对象加键，违反契约也会污染缓存/序列化结果。
 */
function orderWithinLayers(layers: CardData[][]): void {
  const order: Record<string, number> = {};
  layers.forEach(function (arr) {
    if (!arr) return;
    arr.forEach(function (t, i) { order[t.id] = i; });
  });
  for (let pass = 0; pass < 2; pass++) {
    for (let l = 1; l < layers.length; l++) {
      const arr = layers[l];
      if (!arr) continue;
      const keyed = arr.map(function (t) { return { task: t, bary: barycenter(t, order) }; });
      keyed.sort(function (a, b) { return a.bary - b.bary; });
      arr.length = 0;
      for (let i = 0; i < keyed.length; i++) {
        arr.push(keyed[i].task);
        order[keyed[i].task.id] = i;
      }
    }
  }
}

/**
 * 计算布局。
 *
 * @param tasks   任务列表（含 layer / dependsOn）
 * @param dir     'vertical' 纵向 | 'horizontal' 横向
 * @param availW  容器可用宽度（纵向布局**不再**据此折行，只作为画布最小宽度；横向布局不使用）
 */
export function calculateLayout(tasks: CardData[], dir: LayoutDir, availW: number): LayoutResult {
  const layers = groupByLayer(tasks);
  orderWithinLayers(layers);

  const pos: Record<string, Point> = {};
  const bands: Band[] = [];
  let width = 0;
  let height = 0;

  if (dir === 'horizontal') {
    // horizontal：每层占一列（层内超过 MAX_ROWS 再折列），x 逐层递增
    let x = PAD + GUTTER;
    let maxRows = 1;
    layers.forEach(function (arr, l) {
      if (!arr || !arr.length) return;
      maxRows = Math.max(maxRows, Math.min(MAX_ROWS, arr.length));
      bands.push({ layer: l, y: PAD, count: arr.length });
      arr.forEach(function (t, i) {
        pos[t.id] = {
          x: x + Math.floor(i / MAX_ROWS) * (CARD_W + GAP_X),
          y: PAD + (i % MAX_ROWS) * (CARD_H + GAP_Y)
        };
      });
      x += Math.ceil(arr.length / MAX_ROWS) * (CARD_W + GAP_X) + BAND_GAP;
    });
    width = Math.max(PAD * 2 + CARD_W, x - GAP_X - BAND_GAP + PAD);
    height = PAD * 2 + maxRows * (CARD_H + GAP_Y) - GAP_Y;
  } else {
    // vertical：**同层不折行** —— 每层始终一行，画布按最宽层展开；
    // 容器比画布窄时由 .dsh-pm-dag-canvas-wrap 的 overflow:auto 横向滚动。
    // 2026-09-29 用户裁定 C（「会话右上角节点没有展开、一行只能放 2 个，把这个限制去掉」）：
    // availW 不再决定列数（原 cols=floor((availW-56)/222) 会让 666px 的面板一行只放 2 个），
    // 只作为画布**最小宽度**，让窄内容也能铺满容器。
    let maxCount = 1;
    layers.forEach(function (arr) { if (arr && arr.length > maxCount) maxCount = arr.length; });
    const cols = Math.max(1, maxCount);
    let y = PAD;
    layers.forEach(function (arr, l) {
      if (!arr || !arr.length) return;
      bands.push({ layer: l, y: y, count: arr.length });
      arr.forEach(function (t, i) {
        pos[t.id] = { x: PAD + GUTTER + i * (CARD_W + GAP_X), y: y };
      });
      y += CARD_H + BAND_GAP;
    });
    const contentW = PAD * 2 + GUTTER + cols * (CARD_W + GAP_X) - GAP_X;
    width = Math.max(contentW, Math.max(PAD * 2 + CARD_W, availW));
    height = Math.max(PAD * 2 + CARD_H, y - BAND_GAP + PAD);
  }

  return { pos: pos, bands: bands, width: width, height: height, dir: dir };
}

/** 命中测试：画布坐标 -> 节点 id（无命中返回 null；inset 为容差） */
export function hitTest(layout: LayoutResult, x: number, y: number, inset: number): string | null {
  const pad = inset || 0;
  for (const id in layout.pos) {
    const p = layout.pos[id];
    if (x >= p.x - pad && x <= p.x + CARD_W + pad && y >= p.y - pad && y <= p.y + CARD_H + pad) {
      return id;
    }
  }
  return null;
}
