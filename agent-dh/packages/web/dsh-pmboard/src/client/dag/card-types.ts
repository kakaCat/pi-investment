/**
 * 队列 DAG 卡片四轴类型系统
 * 
 * 四根正交的轴决定卡片上的信息层次：
 * - Phase（任务类型，7 类）：决定类型徽标的颜色
 * - Side（端侧，4 类）：决定端侧徽标
 * - Role（角色，3 类）：决定是否显示父卡标识和子卡链进度
 * - Status（状态，6 类）：决定卡片背景色
 */

// ============ 枚举定义 ============

/**
 * Phase - 任务类型（7 类）
 * 决定类型徽标的颜色
 */
export enum Phase {
  /** 实施 - 主要开发任务 */
  IMPLEMENT = 'implement',
  /** 测试 - 测试任务 */
  TEST = 'test',
  /** 文档 - 文档编写 */
  DOC = 'doc',
  /** 评审 - 代码评审 */
  REVIEW = 'review',
  /** UI - 界面设计/实现 */
  UI = 'ui',
  /** 分析 - 需求分析/技术调研 */
  ANALYSIS = 'analysis',
  /** 合并 - 代码合并 */
  MERGE = 'merge'
}

/**
 * Side - 端侧（4 类）
 * 决定端侧徽标
 */
export enum Side {
  /** 后端 */
  BACKEND = 'backend',
  /** 前端 */
  FRONTEND = 'frontend',
  /** 全栈 */
  FULLSTACK = 'fullstack',
  /** 文档 */
  DOC = 'doc'
}

/**
 * Role - 角色（3 类）
 * 决定子卡链进度等派生语义（2026-09-29 裁定 D 后**不再有「左侧蓝条」这一视觉标识**）
 */
export enum Role {
  /** 父卡（名下可有子卡链；卡底进度由调用方 showKidChains 控制） */
  PARENT = 'parent',
  /** 子卡（不显示父卡标识） */
  CHILD = 'child',
  /** 独立卡 - 既非父卡也非子卡 */
  SOLO = 'solo'
}

/**
 * Status - 状态（6 类）
 * 决定卡片背景色
 */
export enum Status {
  /** 待开始 */
  TODO = 'todo',
  /** 开发中 */
  IN_PROGRESS = 'in_progress',
  /** 联调中 */
  INTEGRATING = 'integrating',
  /** 测试中 */
  TESTING = 'testing',
  /** 待复核 */
  IN_REVIEW = 'in_review',
  /** 已完成 */
  DONE = 'done'
}

// ============ 颜色映射表 ============

/**
 * Phase 类型徽标颜色映射（7 种彩色）
 */
export const PHASE_COLORS: Record<Phase, string> = {
  [Phase.IMPLEMENT]: '#0071e3',    // 蓝色 - 实施
  [Phase.TEST]: '#34c759',         // 绿色 - 测试
  [Phase.DOC]: '#ff9500',          // 橙色 - 文档
  [Phase.REVIEW]: '#af52de',       // 紫色 - 评审
  [Phase.UI]: '#ff2d55',           // 粉色 - UI
  [Phase.ANALYSIS]: '#5ac8fa',     // 青色 - 分析
  [Phase.MERGE]: '#ffcc00'         // 黄色 - 合并
};

/**
 * Side 端侧徽标颜色映射（4 种次要颜色）
 */
export const SIDE_COLORS: Record<Side, string> = {
  [Side.BACKEND]: '#8e8e93',       // 灰色
  [Side.FRONTEND]: '#007aff',      // 亮蓝
  [Side.FULLSTACK]: '#5856d6',     // 靛蓝
  [Side.DOC]: '#ff9500'            // 橙色
};

/**
 * Status 状态底色映射（6 种浅色背景）
 */
export const STATUS_BACKGROUND_COLORS: Record<Status, string> = {
  [Status.TODO]: '#f2f2f7',            // 浅灰 - 待开始
  [Status.IN_PROGRESS]: '#e5f1ff',     // 浅蓝 - 开发中
  [Status.INTEGRATING]: '#fff4e5',     // 浅橙 - 联调中
  [Status.TESTING]: '#e8f9ed',         // 浅绿 - 测试中
  [Status.IN_REVIEW]: '#f3e5ff',       // 浅紫 - 待复核
  [Status.DONE]: '#e8f5e9'             // 浅绿（偏深）- 已完成
};

/**
 * Status 状态文本颜色映射（深色文字）
 */
export const STATUS_TEXT_COLORS: Record<Status, string> = {
  [Status.TODO]: '#8e8e93',
  [Status.IN_PROGRESS]: '#0071e3',
  [Status.INTEGRATING]: '#ff9500',
  [Status.TESTING]: '#34c759',
  [Status.IN_REVIEW]: '#af52de',
  [Status.DONE]: '#2e7d32'
};

// ============ 类型定义 ============

/**
 * 卡片数据接口
 */
export interface CardData {
  /** 任务 ID */
  id: string;
  /** 任务标题 */
  title: string;
  /** 任务类型 */
  phase: Phase;
  /** 端侧 */
  side: Side;
  /** 角色 */
  role: Role;
  /** 状态 */
  status: Status;
  /** 依赖的任务 ID 列表（源数据；edges 是其展开结果） */
  dependsOn?: string[];
  /** 所在层级（用于布局；前驱 layer < 后继 layer） */
  layer?: number;
  /** 父卡 id（子卡专属；有值即为子卡） */
  parentId?: string;
  /** 子卡所属阶段（子卡专属；固定链是 dev/integrate/review/test，另有 repro/fix 等） */
  stageKind?: StageKind | string;
  /** 自足任务卡文档路径（有值 = 单击卡片可打开；2026-09-29 裁定 F 恢复旧分层列表的点击开文档） */
  cardDoc?: string;
  /** 父卡的子卡链（父卡专属，由 parentId 反查得到） */
  kids?: Array<{
    id?: string;
    stageKind?: StageKind | string;
    status: Status;
    title?: string;
  }>;
}

/**
 * 队列数据接口
 */
export interface QueueData {
  /** 任务列表 */
  tasks: CardData[];
  /** 分层结果（用于布局） */
  layers: string[][];
  /** 边线 */
  edges: Array<{
    from: string;
    to: string;
  }>;
}

// ============ 辅助函数 ============

/**
 * 获取类型徽标颜色
 */
export function getPhaseColor(phase: Phase): string {
  return PHASE_COLORS[phase] || '#8e8e93';
}

/**
 * 获取端侧徽标颜色
 */
export function getSideColor(side: Side): string {
  return SIDE_COLORS[side] || '#8e8e93';
}

/**
 * 获取状态背景色
 */
export function getStatusBackgroundColor(status: Status): string {
  return STATUS_BACKGROUND_COLORS[status] || '#f2f2f7';
}

/**
 * 获取状态文本颜色
 */
export function getStatusTextColor(status: Status): string {
  return STATUS_TEXT_COLORS[status] || '#8e8e93';
}

/**
 * 判断是否为父卡
 */
export function isParentCard(card: CardData): boolean {
  return card.role === Role.PARENT;
}

/**
 * 判断是否为子卡
 */
export function isChildCard(card: CardData): boolean {
  return card.role === Role.CHILD;
}


// ============ 阶段（子卡链）============

/**
 * StageKind - 子卡所属阶段
 * 父卡的固定子卡链顺序：dev（研发）→ integrate（联调）→ review（复核）→ test（测试）
 */
export type StageKind = 'dev' | 'integrate' | 'review' | 'test';

// ============ 四轴标签表 ============

/** phase 中文名（7 类） */
export const PHASE_LABEL: Record<string, string> = {
  implement: '实施',
  test: '测试',
  doc: '文档',
  review: '评审',
  ui: 'UI',
  analysis: '分析',
  merge: '合并'
};

/** side 中文名（4 类） */
export const SIDE_LABEL: Record<string, string> = {
  backend: '后端',
  frontend: '前端',
  fullstack: '全栈',
  doc: '文档'
};

/** status 中文名（6 类） */
export const STATUS_LABEL: Record<string, string> = {
  todo: '待开始',
  in_progress: '开发中',
  integrating: '联调中',
  testing: '测试中',
  in_review: '待复核',
  done: '已完成'
};

// ============ 派生字段 ============

/** 从 parentId / 子卡反查推断出的角色信息（内存计算，不写回 queue.json） */
export interface DerivedTaskFields {
  /** 角色：父卡（有子卡）/ 子卡（有 parentId）/ 独立卡 */
  role: Role;
  /** 父卡的子卡链（按 dev → integrate → review → test 排序） */
  kids?: Array<{ id: string; stageKind: StageKind | string; status: Status; title: string }>;
}

/**
 * 派生角色与子卡链。
 *
 * 规则（对齐设计 docs/design/data-model.md §派生字段）：
 * 1. 有 parentId → 子卡
 * 2. 否则反查 allTasks 里 parentId === task.id 的任务 → 有则父卡
 * 3. 都没有 → 独立卡
 */
export function deriveTaskFields(task: CardData, allTasks: CardData[]): DerivedTaskFields {
  if (task.parentId) return { role: Role.CHILD };

  const order = ['dev', 'integrate', 'review', 'test'];
  const kids = allTasks
    .filter(function (t) { return t.parentId === task.id; })
    .sort(function (a, b) {
      const ia = order.indexOf(String(a.stageKind));
      const ib = order.indexOf(String(b.stageKind));
      return (ia < 0 ? 9 : ia) - (ib < 0 ? 9 : ib);
    })
    .map(function (t) {
      return {
        id: t.id,
        stageKind: (t.stageKind || '') as StageKind,
        status: t.status,
        title: t.title
      };
    });

  if (kids.length) return { role: Role.PARENT, kids: kids };
  return { role: Role.SOLO };
}
