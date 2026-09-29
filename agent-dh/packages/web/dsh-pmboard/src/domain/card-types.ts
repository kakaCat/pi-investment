/**
 * 卡片四轴类型系统（REQ-260927182328-6e7d t-4d579e）——定义 Phase/Side/Role/Status 四维枚举与颜色映射。
 *
 * 设计依据：
 *  - Phase（阶段）：对应 SubtaskTemplate.ts 的 StageKind（16种），此处映射为7种颜色族；
 *  - Side（端别）：frontend/backend/fullstack/doc 四种；
 *  - Role（角色）：parent/subtask/legacy 三种（来自 TaskStatus.ts 的 TaskRole）；
 *  - Status（状态）：todo/in_progress/integrating/testing/in_review/done/canceled 七种（来自 TaskStatus.ts）。
 *
 * 颜色口径（7+4+6）：
 *  - Phase：7色族（研发/复核/测试族/调研族/数据族/运维族/逃生舱）；
 *  - Side：4色（蓝/绿/紫/灰）；
 *  - Status：6色底（灰/蓝/黄/橙/绿/红）。
 *
 * 本文件是纯数据 + 纯函数：不 import node:/@deepseek-ai/，不碰时间与随机数（沿用 domain 层纪律）。
 */

import type { StageKind } from './task/SubtaskTemplate.js'
import type { TaskRole, TaskStatus } from './task/TaskStatus.js'

// ============ Phase（阶段）类型系统 ============

/**
 * Phase 颜色族（7种）：将 16 种 StageKind 映射为 7 个颜色族。
 * 顺序即语义分组（与 SubtaskTemplate.STAGE_KINDS 对齐）。
 */
export const PHASE_COLOR_FAMILIES = [
  'dev-family',      // 研发族：dev, integrate
  'review-family',   // 复核族：review
  'test-family',     // 测试族：test, regress
  'debug-family',    // 调试族：repro, fix
  'research-family', // 调研族：probe, collect, analyze
  'data-family',     // 数据族：prepare, run, verify
  'ops-family',      // 运维族：change, dryrun, apply
] as const

export type PhaseColorFamily = (typeof PHASE_COLOR_FAMILIES)[number]

/**
 * StageKind → Phase 颜色族映射表。
 * 未映射的逃生舱 StageKind 回退 'dev-family'（保守默认）。
 */
export const STAGE_TO_PHASE_COLOR: Readonly<Record<StageKind, PhaseColorFamily>> = {
  dev: 'dev-family',
  integrate: 'dev-family',
  review: 'review-family',
  test: 'test-family',
  repro: 'debug-family',
  fix: 'debug-family',
  regress: 'test-family',
  probe: 'research-family',
  collect: 'research-family',
  analyze: 'research-family',
  prepare: 'data-family',
  run: 'data-family',
  verify: 'data-family',
  change: 'ops-family',
  dryrun: 'ops-family',
  apply: 'ops-family',
}

/**
 * Phase 颜色族 → 颜色值映射（UI 样式用）。
 * 颜色值为 CSS 类名或 hex 色值（由前端决定）。
 */
export const PHASE_COLOR_MAP: Readonly<Record<PhaseColorFamily, string>> = {
  'dev-family': '#3b82f6',      // 蓝色（开发）
  'review-family': '#8b5cf6',   // 紫色（审核）
  'test-family': '#10b981',     // 绿色（测试）
  'debug-family': '#f59e0b',    // 橙色（调试）
  'research-family': '#06b6d4', // 青色（调研）
  'data-family': '#6366f1',     // 靛蓝（数据）
  'ops-family': '#ef4444',      // 红色（运维）
}

// ============ Side（端别）类型系统 ============

/**
 * Side 枚举（4种）：前端/后端/全栈/文档。
 */
export const SIDES = ['frontend', 'backend', 'fullstack', 'doc'] as const

export type Side = (typeof SIDES)[number]

/**
 * Side 中文标签。
 */
export const SIDE_LABELS: Readonly<Record<Side, string>> = {
  frontend: '前端',
  backend: '后端',
  fullstack: '全栈',
  doc: '文档',
}

/**
 * Side → 颜色值映射（4色）。
 */
export const SIDE_COLOR_MAP: Readonly<Record<Side, string>> = {
  frontend: '#3b82f6',  // 蓝色
  backend: '#10b981',   // 绿色
  fullstack: '#8b5cf6', // 紫色
  doc: '#6b7280',       // 灰色
}

// ============ Role（角色）类型系统 ============

/**
 * 重导出 TaskRole（parent/subtask/legacy），避免外部直接依赖 TaskStatus.ts。
 */
export type { TaskRole }

/**
 * Role 中文标签（来自 TaskStatus.TASK_ROLE_LABELS）。
 */
export const ROLE_LABELS: Readonly<Record<TaskRole, string>> = {
  parent: '父卡',
  subtask: '子卡',
  legacy: '存量卡',
}

// ============ Status（状态）类型系统 ============

/**
 * 重导出 TaskStatus，避免外部直接依赖 TaskStatus.ts。
 */
export type { TaskStatus }

/**
 * Status 底色映射（6种颜色，canceled 与 todo 共用灰色）。
 */
export const STATUS_COLOR_MAP: Readonly<Record<TaskStatus, string>> = {
  todo: '#e5e7eb',        // 灰色（待开始）
  in_progress: '#3b82f6', // 蓝色（进行中）
  integrating: '#f59e0b', // 橙色（联调）
  testing: '#eab308',     // 黄色（测试）
  in_review: '#8b5cf6',   // 紫色（复核）
  done: '#10b981',        // 绿色（完成）
  canceled: '#6b7280',    // 灰色（取消）
}

/**
 * Status 中文标签（看板展示用）。
 */
export const STATUS_LABELS: Readonly<Record<TaskStatus, string>> = {
  todo: '待开始',
  in_progress: '进行中',
  integrating: '联调中',
  testing: '测试中',
  in_review: '待复核',
  done: '已完成',
  canceled: '已取消',
}

// ============ 工具函数 ============

/**
 * 获取 StageKind 的颜色（Phase 维度）。
 */
export function getPhaseColor(stage: StageKind): string {
  const family = STAGE_TO_PHASE_COLOR[stage]
  return PHASE_COLOR_MAP[family]
}

/**
 * 获取 Side 的颜色。
 */
export function getSideColor(side: Side): string {
  return SIDE_COLOR_MAP[side]
}

/**
 * 获取 Status 的底色。
 */
export function getStatusColor(status: TaskStatus): string {
  return STATUS_COLOR_MAP[status]
}
