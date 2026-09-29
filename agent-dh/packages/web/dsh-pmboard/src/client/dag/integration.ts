/**
 * 集成入口（REQ-260928001915-f978 · t-144707 · FR-1…FR-7）
 *
 * 把布局 / 卡片 / 进度条 / 边线 / 交互五个模块串成一条主渲染流程：
 *
 *   queue.json ──► validateQueueFile ──► findCriticalPath ──► calculateLayout
 *                     │                                           │
 *                     └──► renderEdges（边线）◄───────────────────┤
 *                          renderCard（卡片 + 进度条 + 绿点）◄────┤
 *                          setupInteraction（悬停/钉住）◄────────┘
 *
 * 两个对外形态：
 * - createDagViewer(canvas, data, state)  Canvas 交互式视图（本需求 demo 用）
 * - renderDagHtml(data, state)            DOM/SVG 字符串（pmboard 泳道用，见 interfaces.md）
 */
import type { CardData } from './card-types';
import { deriveTaskFields } from './card-types';
import {
  calculateLayout,
  hitTest,
  PAD,
  CARD_W,
  CARD_H,
  type LayoutResult,
  type LayoutDir
} from './dag-layout';
import { findCriticalPath, detectCycle, branchCounts } from './critical-path';
import { renderCard, cardHtml } from './card-renderer';
import { renderEdges, edgeSvg, type Edge } from './edge-renderer';
import {
  setupInteraction,
  resolveHighlight,
  DIM_NODE_ALPHA,
  type InteractionController,
  type Highlight
} from './interaction';

/** 渲染输入：任务 + 依赖边 + 可开工集合（对应 queue.json 的 tasks/edges/ready） */
export interface DagData {
  /** 要画的节点（卡片层折叠后 = 顶层卡） */
  tasks: CardData[];
  edges: Edge[];
  ready: string[];
  /**
   * 角色派生用的**全量卡片池**（缺省 = tasks）。
   *
   * 卡片层契约（2026-09-28）：画布只画顶层卡，子卡折进父卡卡底的进度条，
   * 但「谁是父卡 / 它的链上有哪几段」必须按**全量**（含子卡）反查——只给顶层卡时
   * deriveTaskFields 查不到子卡，父卡会被判成 solo（蓝条与进度条一起消失）。
   * 故折叠调用方须把含子卡的全量传进来。
   */
  pool?: CardData[];
  /**
   * 是否在父卡卡底画「子卡链进度」（4 段色条 + n/N）。缺省 true（demo 行为）。
   *
   * 看板传 false——用户 2026-09-29 裁定 A：「DAG 只渲染父卡片，不用管子卡片」。
   * 父卡身份（左侧蓝条）仍由 `pool` 派生的 role 保住，只是不再画那条进度：
   * 子卡在 DAG 里既不单独成节点，也不再占卡底一行。
   */
  showKidChains?: boolean;
}

/** 渲染状态（前端内存，不写回 queue.json） */
export interface DagState {
  /** 布局方向 */
  dir: LayoutDir;
  /** 是否高亮关键路径 */
  crit: boolean;
  /** 是否只看主线（折叠支线） */
  focus: boolean;
  /** 当前高亮的节点 id（悬停或钉住） */
  pinned: string | null;
}

export interface DagRenderResult {
  layout: LayoutResult;
  critSet: Set<string>;
  visibleIds: string[];
  /** 主线模式下每个关键节点的支线边数 */
  branchCount: Record<string, number>;
  /** 有环时返回环上节点，否则 null */
  cycle: string[] | null;
}

export interface DagViewer {
  /** 重绘当前状态 */
  render(): DagRenderResult;
  /** 合并更新状态并重绘 */
  patch(patch: Partial<DagState>): DagRenderResult;
  /** 当前状态（只读快照） */
  state(): DagState;
  /** 当前布局（命中测试用） */
  layout(): LayoutResult | null;
  destroy(): void;
}

/** 判断某节点在本次高亮中的角色 */
function roleOf(id: string, hl: Highlight | null): { highlight: 'self' | 'up' | 'down' | null; dimmed: boolean } {
  if (!hl || !hl.self) return { highlight: null, dimmed: false };
  if (hl.self === id) return { highlight: 'self', dimmed: false };
  if (hl.up.has(id)) return { highlight: 'up', dimmed: false };
  if (hl.down.has(id)) return { highlight: 'down', dimmed: false };
  return { highlight: null, dimmed: true };
}

/**
 * 渲染前统一补齐派生字段：role（父卡/子卡/独立卡）与 kids（父卡的子卡链）。
 *
 * 队列原始数据的 role 并不是持久化字段，而是由 parentId / 子卡反查得到；
 * 卡片渲染器只认 `task.role`，所以必须先在这里补齐，否则父卡的蓝条与子卡链会缺失。
 */
export function resolveTasks(tasks: CardData[], pool?: CardData[]): CardData[] {
  const all = pool && pool.length ? pool : tasks;
  return tasks.map(function (t) {
    const d = deriveTaskFields(t, all);
    const copy: CardData = Object.assign({}, t);
    copy.role = d.role;
    if (d.kids && d.kids.length) copy.kids = d.kids;
    return copy;
  });
}

/**
 * 创建 Canvas 交互式 DAG 视图。
 * 返回的 viewer 同时绑好了悬停/点击（setupInteraction）。
 */
export function createDagViewer(
  canvas: HTMLCanvasElement,
  data: DagData,
  initial: Partial<DagState>
): DagViewer {
  const state: DagState = {
    dir: (initial.dir as LayoutDir) || 'vertical',
    crit: !!initial.crit,
    focus: !!initial.focus,
    pinned: initial.pinned || null
  };

  let lastLayout: LayoutResult | null = null;
  let controller: InteractionController | null = null;

  const paint = function (): DagRenderResult {
    const ctx = canvas.getContext('2d');
    const availW = (canvas.parentElement && canvas.parentElement.clientWidth) || 900;

    const tasks = resolveTasks(data.tasks, data.pool);
    const cycle = detectCycle(tasks);
    const critSet = findCriticalPath(tasks);

    if (cycle || !tasks.length) {
      // 降级：空图 / 有环 —— 画一行说明，不抛异常
      canvas.width = availW;
      canvas.height = 90;
      canvas.style.width = availW + 'px';
      canvas.style.height = '90px';
      if (ctx) {
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, availW, 90);
        ctx.fillStyle = cycle ? '#c2185b' : '#8e8e93';
        ctx.font = '13px -apple-system, BlinkMacSystemFont, sans-serif';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(cycle ? ('DAG 存在循环依赖：' + cycle.join(' → ')) : '暂无任务', PAD, 40);
      }
      lastLayout = null;
      return { layout: { pos: {}, bands: [], width: availW, height: 90, dir: state.dir }, critSet: critSet, visibleIds: [], branchCount: {}, cycle: cycle };
    }

    const visibleTasks = state.focus ? tasks.filter(function (t) { return critSet.has(t.id); }) : tasks;
    const visible = new Set<string>();
    visibleTasks.forEach(function (t) { visible.add(t.id); });
    const edges = data.edges.filter(function (e) { return visible.has(e.from) && visible.has(e.to); });

    const layout = calculateLayout(visibleTasks, state.dir, availW);
    lastLayout = layout;

    const dpr = (typeof devicePixelRatio === 'number' && devicePixelRatio > 0 ? devicePixelRatio : 1);
    canvas.width = Math.round(layout.width * dpr);
    canvas.height = Math.round(layout.height * dpr);
    canvas.style.width = layout.width + 'px';
    canvas.style.height = layout.height + 'px';

    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, layout.width, layout.height);

      const hl = resolveHighlight(tasks, state.pinned);
      const hasHl = !!hl.self;
      const branch = state.focus ? branchCounts(data.edges, critSet) : {};
      const ready = new Set<string>(data.ready || []);

      // 1) 边线（在卡片下层）
      renderEdges(ctx, edges, layout, visibleTasks, {
        critSet: critSet,
        highlight: hasHl ? hl : null,
        dimmed: hasHl,
        dir: state.dir
      });

      // 2) 层带标签（纵向布局时画在左侧）
      if (state.dir !== 'horizontal') {
        layout.bands.forEach(function (b) {
          ctx.save();
          ctx.fillStyle = 'rgba(0,0,0,.32)';
          ctx.font = '10px ui-monospace, SFMono-Regular, Menlo, monospace';
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillText('L' + b.layer, PAD, b.y + 14);
          ctx.restore();
        });
      }

      // 3) 卡片
      visibleTasks.forEach(function (t) {
        const p = layout.pos[t.id];
        if (!p) return;
        const flag = roleOf(t.id, hasHl ? hl : null);
        renderCard(ctx, t, p.x, p.y, {
          kids: data.showKidChains === false ? [] : t.kids,
          ready: ready.has(t.id),
          critical: state.crit && critSet.has(t.id),
          dimmed: flag.dimmed,
          highlight: flag.highlight
        });

        // 4) 主线模式的 '+N 支线' 徽标
        if (state.focus && branch[t.id]) {
          ctx.save();
          ctx.globalAlpha = flag.dimmed ? DIM_NODE_ALPHA : 1;
          ctx.fillStyle = 'rgba(0,0,0,.55)';
          ctx.font = '10px -apple-system, BlinkMacSystemFont, sans-serif';
          ctx.textAlign = 'right';
          ctx.textBaseline = 'bottom';
          ctx.fillText('+' + branch[t.id] + ' 支线', p.x + CARD_W - 8, p.y + CARD_H - 4);
          ctx.restore();
        }
      });
    }

    return {
      layout: layout,
      critSet: critSet,
      visibleIds: visibleTasks.map(function (t) { return t.id; }),
      branchCount: state.focus ? branchCounts(data.edges, critSet) : {},
      cycle: null
    };
  };

  const viewer: DagViewer = {
    render: paint,
    patch: function (patch) {
      if (patch.dir !== undefined) state.dir = patch.dir;
      if (patch.crit !== undefined) state.crit = patch.crit;
      if (patch.focus !== undefined) state.focus = patch.focus;
      if (patch.pinned !== undefined) state.pinned = patch.pinned;
      return paint();
    },
    state: function () { return { dir: state.dir, crit: state.crit, focus: state.focus, pinned: state.pinned }; },
    layout: function () { return lastLayout; },
    destroy: function () { if (controller) controller.destroy(); }
  };

  controller = setupInteraction(canvas, {
    hitTest: function (x, y) { return lastLayout ? hitTest(lastLayout, x, y, 0) : null; },
    onChange: function (id) {
      state.pinned = id;
      paint();
    }
  });

  paint();
  return viewer;
}

/* ---------------- 数据校验（design/interfaces.md §validateQueueFile）---------------- */

export interface ValidationIssue {
  /** 规则编号（见 design/data-model.md §数据约束） */
  rule: string;
  message: string;
  path?: string;
}

export interface ValidationResult {
  passed: boolean;
  issues: ValidationIssue[];
}

/** V-1…V-6：队列文件在渲染前的结构与一致性校验 */
export function validateQueueFile(queue: {
  requirement_id?: string;
  tasks?: CardData[];
  edges?: Edge[];
  ready?: string[];
}): ValidationResult {
  const issues: ValidationIssue[] = [];
  const tasks = queue.tasks || [];
  const edges = queue.edges || [];
  const ready = queue.ready || [];

  if (!tasks.length) issues.push({ rule: 'V-1', message: 'tasks 为空，没有可渲染的任务' });

  const ids = new Set<string>();
  tasks.forEach(function (t) { ids.add(t.id); });

  edges.forEach(function (e, i) {
    if (!ids.has(e.from)) issues.push({ rule: 'V-2', message: '边引用了不存在的任务 ' + e.from, path: 'edges[' + i + '].from' });
    if (!ids.has(e.to)) issues.push({ rule: 'V-2', message: '边引用了不存在的任务 ' + e.to, path: 'edges[' + i + '].to' });
  });

  const req = queue.requirement_id;
  if (req) {
    tasks.forEach(function (t: any, i) {
      if (t.requirementId && t.requirementId !== req) {
        issues.push({ rule: 'V-3', message: '任务 ' + t.id + ' 的 requirementId 与队列不一致', path: 'tasks[' + i + ']' });
      }
    });
  }

  const cycle = detectCycle(tasks);
  if (cycle) issues.push({ rule: 'V-4', message: 'dependsOn 存在循环依赖：' + cycle.join(' → ') });

  tasks.forEach(function (t, i) {
    (t.dependsOn || []).forEach(function (d, j) {
      const dep = tasks.filter(function (x) { return x.id === d; })[0];
      if (dep && typeof t.layer === 'number' && typeof dep.layer === 'number' && dep.layer >= t.layer) {
        issues.push({ rule: 'V-5', message: '前驱 ' + d + ' 的 layer(' + dep.layer + ') 不小于后继 ' + t.id + '(' + t.layer + ')', path: 'tasks[' + i + '].dependsOn[' + j + ']' });
      }
    });
  });

  ready.forEach(function (id, i) {
    const t = tasks.filter(function (x) { return x.id === id; })[0];
    if (!t) issues.push({ rule: 'V-6', message: 'ready 含不存在的任务 ' + id, path: 'ready[' + i + ']' });
    else if (t.status !== 'todo') issues.push({ rule: 'V-6', message: 'ready 含非待开始状态的任务 ' + id, path: 'ready[' + i + ']' });
  });

  return { passed: issues.length === 0, issues: issues };
}

/* ---------------- DOM 后端（interfaces.md 的 renderDag 契约）---------------- */

/** 返回 DAG 的 HTML 字符串（节点绝对定位 + SVG 边线），供 pmboard 泳道直接插入 */
export function renderDagHtml(data: DagData, state: DagState): string {
  if (!data.tasks.length) return '<div class="dsh-pm-np-empty">暂无任务</div>';
  const resolved = resolveTasks(data.tasks, data.pool);
  const cycle = detectCycle(resolved);
  if (cycle) return '<div class="dsh-pm-np-error">DAG 存在循环依赖：' + cycle.join(' → ') + '</div>';

  const critSet = findCriticalPath(resolved);
  const visibleTasks = state.focus ? resolved.filter(function (t) { return critSet.has(t.id); }) : resolved;
  const visible = new Set<string>();
  visibleTasks.forEach(function (t) { visible.add(t.id); });
  const edges = data.edges.filter(function (e) { return visible.has(e.from) && visible.has(e.to); });
  const layout = calculateLayout(visibleTasks, state.dir, 690);
  const ready = new Set<string>(data.ready || []);

  let nodes = '';
  visibleTasks.forEach(function (t) {
    const p = layout.pos[t.id];
    if (!p) return;
    nodes += '<div class="node' + (critSet.has(t.id) ? ' crit' : '') + '" data-id="' + t.id +
      '" style="left:' + p.x + 'px;top:' + p.y + 'px">' +
      cardHtml(t, { kids: data.showKidChains === false ? [] : t.kids, ready: ready.has(t.id) }) + '</div>';
  });

  return '<div class="dsh-pm-np-dag" data-direction="' + state.dir + '" data-focus="' + state.focus + '">' +
    edgeSvg(edges, layout, visibleTasks, critSet, state.dir) + nodes + '</div>';
}

/* ---------------- 浏览器全局导出（build-demo.py 用 esbuild 打成 IIFE）---------------- */
export * from './card-types';
export * from './dag-layout';
export * from './critical-path';
export * from './card-renderer';
export * from './progress-bar';
export * from './edge-renderer';
export * from './interaction';
