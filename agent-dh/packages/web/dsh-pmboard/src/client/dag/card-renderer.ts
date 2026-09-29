/**
 * 卡片渲染器（REQ-260928001915-f978 · t-2ad263 · FR-2）
 *
 * 一张卡 208×72px，七个视觉元素：
 *   ① ID（等宽灰字，左上）        ② 类型徽标（phase，彩底）
 *   ③ 端侧徽标（side）            ④ 标题（粗体，最多两行）
 *   ⑤ 状态底色（整卡背景）        ⑥ 父卡子卡链进度（底部 4 段）
 *   ⑦ ready 绿点（右上角）
 * 2026-09-29 用户裁定 D：父卡**左侧 3px 蓝条已删除**（DAG 卡片外观与泳道卡片一致）。
 *
 * 两个后端共用同一份配色（card-types.ts 为唯一真源）：
 * - renderCard(ctx, ...)  Canvas 2D（大图性能好）
 * - cardHtml(task, ...)   DOM 字符串（pmboard 泳道卡片，见 design/interfaces.md）
 */
import type { CardData } from './card-types';
import {
  Role,
  PHASE_LABEL,
  STATUS_LABEL,
  getPhaseColor,
  getSideColor,
  getStatusBackgroundColor
} from './card-types';
import { CARD_W, CARD_H } from './dag-layout';
import { renderProgressBar, chainHtml, esc, STAGE_LABEL, type KidLike } from './progress-bar';

/** 卡片渲染选项 */
export interface RenderCardOptions {
  /** 父卡的子卡链（父卡专属） */
  kids?: KidLike[];
  /** 是否标记 ready 绿点 */
  ready?: boolean;
  /** 是否在关键路径上（虚线轮廓） */
  critical?: boolean;
  /** 是否被 dimming（未高亮，整体压暗） */
  dimmed?: boolean;
  /** 高亮角色：self=黑框 / up=橙框 / down=蓝框 */
  highlight?: 'self' | 'up' | 'down' | null;
  /** DOM 后端专用：彩色徽标变体（类型标本墙的对照） */
  vc?: boolean;
}

/* ---------------- Canvas 绘制原语 ---------------- */

/** 圆角矩形路径（不依赖 ctx.roundRect，兼容旧浏览器） */
export function roundRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
): void {
  const rr = Math.max(0, Math.min(r, w / 2, h / 2));
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.lineTo(x + w - rr, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
  ctx.lineTo(x + w, y + h - rr);
  ctx.quadraticCurveTo(x + w, y + h, x + w - rr, y + h);
  ctx.lineTo(x + rr, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - rr);
  ctx.lineTo(x, y + rr);
  ctx.quadraticCurveTo(x, y, x + rr, y);
  ctx.closePath();
}

/** 按字符折行（中英文混排都按单字符宽度累加），最多 maxLines 行，超出加省略号 */
export function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxW: number,
  maxLines: number
): string[] {
  const chars = String(text || '').split('');
  const lines: string[] = [];
  let cur = '';
  for (let i = 0; i < chars.length; i++) {
    const next = cur + chars[i];
    if (ctx.measureText(next).width > maxW && cur) {
      lines.push(cur);
      cur = chars[i];
      if (lines.length === maxLines) break;
    } else {
      cur = next;
    }
  }
  if (lines.length < maxLines && cur) lines.push(cur);
  if (lines.length === maxLines) {
    let last = lines[maxLines - 1];
    while (last.length > 1 && ctx.measureText(last + '…').width > maxW) {
      last = last.slice(0, -1);
    }
    lines[maxLines - 1] = last + '…';
  }
  return lines;
}

/** 画一个胶囊徽标，返回其右边缘 x（用于并排排布第二个徽标） */
export function drawChip(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  color: string
): number {
  ctx.save();
  ctx.font = '10px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  const w = Math.round(ctx.measureText(text).width) + 14;
  const h = 16;
  ctx.globalAlpha = ctx.globalAlpha * 0.16;
  ctx.fillStyle = color;
  roundRectPath(ctx, x, y, w, h, 8);
  ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.fillStyle = color;
  ctx.font = '10px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x + w / 2, y + h / 2 + 0.5);
  ctx.restore();
  return x + w;
}

/* ---------------- Canvas 后端 ---------------- */

/**
 * 在画布上绘制一张卡片。
 * @param x,y 卡片左上角坐标
 */
export function renderCard(
  ctx: CanvasRenderingContext2D,
  task: CardData,
  x: number,
  y: number,
  opts?: RenderCardOptions
): void {
  const o = opts || {};
  ctx.save();
  // dimming：未高亮元素整体压暗
  ctx.globalAlpha = o.dimmed ? 0.18 : 1;
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';

  // ⑤ 状态底色（整卡背景）
  ctx.fillStyle = getStatusBackgroundColor(task.status);
  roundRectPath(ctx, x, y, CARD_W, CARD_H, 8);
  ctx.fill();

  // 轮廓：关键路径=蓝色虚线；普通=浅灰实线
  ctx.setLineDash(o.critical ? [5, 3] : []);
  ctx.lineWidth = o.critical ? 1.5 : 1;
  ctx.strokeStyle = o.critical ? 'rgba(0,113,227,.55)' : 'rgba(0,0,0,.10)';
  ctx.stroke();
  ctx.setLineDash([]);

  // 内容裁剪到卡片边界内（对齐原型 .card { overflow: hidden }）：
  // ID 较长 + 类型/端侧/阶段徽标并排、或标题超宽时，防止内容溢出 208×72 卡片之外
  ctx.save();
  roundRectPath(ctx, x, y, CARD_W, CARD_H, 8);
  ctx.clip();

  // ① ID（等宽灰字）
  ctx.fillStyle = '#8e8e93';
  ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.fillText(task.id, x + 12, y + 16);
  const idW = ctx.measureText(task.id).width;

  // ② 类型徽标（phase）
  let bx = drawChip(ctx, x + 12 + idW + 8, y + 8, PHASE_LABEL[task.phase] || String(task.phase), getPhaseColor(task.phase));

  // ③ 端侧徽标（side）
  bx = drawChip(ctx, bx + 4, y + 8, String(task.side), getSideColor(task.side));

  // 子卡阶段徽标（仅子卡）
  if (task.stageKind) {
    drawChip(ctx, bx + 4, y + 8, STAGE_LABEL[task.stageKind] || String(task.stageKind), 'rgba(0,0,0,.45)');
  }

  // ④ 标题（粗体，最多两行）
  ctx.fillStyle = '#1f2733';
  ctx.font = '600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
  const lines = wrapText(ctx, task.title, CARD_W - 26, 2);
  lines.forEach(function (line, i) {
    ctx.fillText(line, x + 12, y + 34 + i * 15);
  });

  // ⑥ 父卡子卡链进度（底部 4 段 + n/total）
  if (task.role === Role.PARENT && o.kids && o.kids.length) {
    renderProgressBar(ctx, o.kids, x + 12, y + CARD_H - 13, CARD_W - 24);
  }

  // ⑦ ready 绿点（右上角 + 光晕）
  if (o.ready) {
    ctx.beginPath();
    ctx.arc(x + CARD_W - 12, y + 12, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#34c759';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(x + CARD_W - 12, y + 12, 7, 0, Math.PI * 2);
    ctx.lineWidth = 2;
    ctx.strokeStyle = 'rgba(52,199,89,.25)';
    ctx.stroke();
  }

  ctx.restore(); // 结束内容裁剪

  // 悬停高亮描边：self=黑 / up=橙 / down=蓝（画在卡片外沿，刻意不受内容裁剪影响）
  if (o.highlight) {
    ctx.lineWidth = 2;
    ctx.strokeStyle = o.highlight === 'self' ? '#1f2733' : (o.highlight === 'up' ? '#ff9500' : '#0071e3');
    roundRectPath(ctx, x - 1, y - 1, CARD_W + 2, CARD_H + 2, 9);
    ctx.stroke();
  }

  ctx.restore();
}

/* ---------------- DOM 后端（design/interfaces.md 契约）---------------- */

/**
 * 卡片 HTML 字符串。class / data-* 与 node-panel 样式表一一对应，
 * 供 pmboard 泳道与类型标本墙使用。
 */
export function cardHtml(task: CardData, opts?: RenderCardOptions): string {
  const o = opts || {};
  const cls = 'card' + (o.vc ? ' vc' : '');
  let attrs = ' data-status="' + esc(task.status) + '"';
  if (task.role) attrs += ' data-role="' + esc(task.role) + '"';

  let s = '<div class="' + cls + '"' + attrs + '>';
  s += '<div class="card-top"><span class="card-id">' + esc(task.id) + '</span>';
  s += '<span class="chip chip-type" data-phase="' + esc(task.phase) + '">' + esc(PHASE_LABEL[task.phase] || task.phase) + '</span>';
  s += '<span class="chip chip-side" data-side="' + esc(task.side) + '">' + esc(task.side) + '</span>';
  if (task.stageKind) s += '<span class="chip chip-kind">' + esc(STAGE_LABEL[task.stageKind] || task.stageKind) + '</span>';
  s += '</div><div class="card-title">' + esc(task.title) + '</div>';
  if (o.kids && o.kids.length) s += chainHtml(o.kids);
  if (o.ready) s += '<span class="ready-dot" title="可开工（队列 ready[]）"></span>';
  s += '</div>';
  return s;
}

/** 状态中文名（供模板与报告复用） */
export function statusLabel(status: string): string {
  return STATUS_LABEL[status] || status;
}
