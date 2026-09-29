/**
 * 悬停交互处理器（REQ-260928001915-f978 · t-73c392 · FR-5）
 *
 * 职责：
 * - 命中测试：把鼠标坐标换算成节点 id
 * - 悬停高亮：上游橙 / 下游蓝，当前卡黑框
 * - dimming：未高亮节点/边线整体压暗（globalAlpha）
 * - 点击钉住：再点同一卡或点空白取消
 *
 * 两个后端：
 * - setupInteraction(canvas, ...)  Canvas 元素（鼠标坐标 -> hitTest）
 * - bindDomInteraction(root, ...)  DOM 容器（closest('.node')，见 design/interfaces.md）
 */
import type { CardData } from './card-types';
import { computeNeighbors } from './critical-path';

/** 未高亮节点的透明度 */
export const DIM_NODE_ALPHA = 0.18;
/** 未高亮边线的透明度 */
export const DIM_EDGE_ALPHA = 0.05;

/** 把未高亮元素统一压暗（Canvas globalAlpha） */
export function paintDim(ctx: CanvasRenderingContext2D, alpha: number): void {
  ctx.globalAlpha = alpha;
}

export interface Highlight {
  /** 当前卡（黑框） */
  self: string | null;
  /** 上游可达前驱（橙框/橙线） */
  up: Set<string>;
  /** 下游可达后继（蓝框/蓝线） */
  down: Set<string>;
}

export const EMPTY_HIGHLIGHT: Highlight = { self: null, up: new Set<string>(), down: new Set<string>() };

/** 由任务列表算出某节点的高亮集合（id 为 null 时返回空集） */
export function resolveHighlight(tasks: CardData[], id: string | null): Highlight {
  if (!id) return EMPTY_HIGHLIGHT;
  const nb = computeNeighbors(tasks, id);
  return { self: id, up: nb.up, down: nb.down };
}

export interface InteractionOptions {
  /** 命中测试：画布内坐标 -> 节点 id（无命中返回 null） */
  hitTest: (x: number, y: number) => string | null;
  /** 高亮变化回调；id=null 表示清除高亮 */
  onChange: (id: string | null) => void;
}

export interface InteractionController {
  readonly pinned: string | null;
  readonly hover: string | null;
  /** 清空钉住状态并触发一次 onChange(null) */
  reset(): void;
  destroy(): void;
}

/** Canvas 后端：绑定 mousemove / click / mouseleave */
export function setupInteraction(canvas: HTMLCanvasElement, opts: InteractionOptions): InteractionController {
  let pinned: string | null = null;
  let hover: string | null = null;

  const at = function (ev: MouseEvent): string | null {
    const r = canvas.getBoundingClientRect();
    return opts.hitTest(ev.clientX - r.left, ev.clientY - r.top);
  };

  const onMouseMove = function (ev: MouseEvent): void {
    const id = at(ev);
    if (id === hover) return;
    hover = id;
    if (pinned) return;             // 钉住时悬停不改高亮
    opts.onChange(id);
  };

  const onClick = function (ev: MouseEvent): void {
    const id = at(ev);
    // 点空白 / 再点同一卡 = 取消；点别的卡 = 改钉住
    pinned = (!id || pinned === id) ? null : id;
    // 取消时显式回传 null：不能回落到 hover——否则鼠标还停在同一张卡上时，
    // "再点一次取消"会被 hover 高亮立即顶回，看起来像没反应（TC-11）。
    opts.onChange(pinned);
  };

  const onMouseLeave = function (): void {
    hover = null;
    if (!pinned) opts.onChange(null);
  };

  canvas.addEventListener('mousemove', onMouseMove);
  canvas.addEventListener('click', onClick);
  canvas.addEventListener('mouseleave', onMouseLeave);

  return {
    get pinned() { return pinned; },
    get hover() { return hover; },
    reset: function () {
      pinned = null;
      hover = null;
      opts.onChange(null);
    },
    destroy: function () {
      canvas.removeEventListener('mousemove', onMouseMove);
      canvas.removeEventListener('click', onClick);
      canvas.removeEventListener('mouseleave', onMouseLeave);
    }
  };
}

/** DOM 后端：在容器上做事件委托（节点元素需带 data-id） */
export function bindDomInteraction(root: HTMLElement, opts: InteractionOptions): InteractionController {
  let pinned: string | null = null;

  const nodeOf = function (ev: Event): HTMLElement | null {
    const target = ev.target as HTMLElement | null;
    if (!target || !target.closest) return null;
    return target.closest('[data-id]') as HTMLElement | null;
  };

  const onMouseOver = function (ev: Event): void {
    const n = nodeOf(ev);
    if (!n || pinned) return;
    opts.onChange(n.getAttribute('data-id'));
  };
  const onMouseOut = function (ev: Event): void {
    const n = nodeOf(ev);
    if (!n || pinned) return;
    opts.onChange(null);
  };
  const onClick = function (ev: Event): void {
    const n = nodeOf(ev);
    const id = n ? n.getAttribute('data-id') : null;
    pinned = (!id || pinned === id) ? null : id;
    opts.onChange(pinned);
  };

  root.addEventListener('mouseover', onMouseOver);
  root.addEventListener('mouseout', onMouseOut);
  root.addEventListener('click', onClick);

  return {
    get pinned() { return pinned; },
    get hover() { return null; },
    reset: function () { pinned = null; opts.onChange(null); },
    destroy: function () {
      root.removeEventListener('mouseover', onMouseOver);
      root.removeEventListener('mouseout', onMouseOut);
      root.removeEventListener('click', onClick);
    }
  };
}
