/**
 * 任务状态机（REQ-47939a t2）——任务状态枚举 + 合法转移表 + 两个查询函数。
 *
 * 与需求状态机同款：规则从 protocol.ts 搬到 domain，成为唯一实现处（INV-1 / INV-2）。
 * 注释随代码搬（硬约束：不重写、不删"为什么/事故出处"型注释）。
 *
 * 本文件是纯数据 + 纯函数：不 import node:/@deepseek-ai/，不碰时间与随机数。
 */

import type { ActorKind } from '../actor.js'

export type TaskStatus =
  | 'todo'        // 待办（自足任务卡落库）
  | 'in_progress' // 进行中（执行会话绑定）
  | 'integrating' // 联调（前后端汇合，可跳过）
  | 'testing'     // 测试（单测输出证据）
  | 'in_review'   // 验收（等人）
  | 'done'        // 完成（仅人）
  | 'canceled'

/**
 * 任务状态的**展示顺序**（看板按此排序：未开始 → 进行中 → 待复核 → 完成）。
 * 适配层此前直接引用一个不存在的 `TASK_ORDER`（运行时 ReferenceError → 500），
 * 现单点于此并带类型。
 */
export const TASK_STATUS_ORDER: readonly TaskStatus[] = [
  'todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done', 'canceled',
]

/** 任务初始状态（新任务一律从此开始——领域常量，适配层不得写字面量）。 */
export const INITIAL_TASK_STATUS: TaskStatus = 'todo'

export const TASK_TRANSITIONS: Readonly<Record<TaskStatus, readonly TaskStatus[]>> = {
  todo: ['in_progress', 'canceled'],
  // in_progress→testing 直通 = 跳过联调（skipIntegration 或人工跳过，均留痕）
  in_progress: ['integrating', 'testing', 'todo', 'canceled'],
  integrating: ['testing', 'in_progress', 'canceled'],
  testing: ['in_review', 'in_progress', 'canceled'],
  in_review: ['done', 'in_progress', 'canceled'],
  done: [],
  canceled: ['todo'],
}

/**
 * 任务人工闸门（代码级仅人）。
 * 2026-09-13 用户裁定（与需求闸门同一口径）：agent 必须能自己把任务跑完——
 * 此前 in_review>done 仅人可操作，而任务完成又驱动需求 rollup，导致任务卡停在
 * 「验收」、需求进不了验收，看板再次静止。现仅保留**取消/复活**这类破坏性动作
 * 为人工闸门，正常流水线（含任务完成）由执行窗口自行推进。
 */
export const HUMAN_ONLY_TASK_TRANSITIONS: ReadonlySet<string> = new Set([
  'todo>canceled',
  'in_progress>canceled',
  'integrating>canceled',
  'testing>canceled',
  'in_review>canceled',
  'canceled>todo', // 复活已取消任务：仅人
])

/** system 允许的任务转移（执行结算用）：开始执行与退回。 */
export const SYSTEM_TASK_TRANSITIONS: ReadonlySet<string> = new Set([
  'todo>in_progress',
  'in_progress>todo',
])

export function canTaskTransition(from: TaskStatus, to: TaskStatus): boolean {
  return TASK_TRANSITIONS[from].includes(to)
}

export function assertTaskTransition(from: TaskStatus, to: TaskStatus, actor: ActorKind): void {
  if (!canTaskTransition(from, to)) {
    throw Object.assign(new Error(`任务状态不允许从 ${from} 转移到 ${to}`), { code: 'invalid_transition' })
  }
  const key = `${from}>${to}`
  if (HUMAN_ONLY_TASK_TRANSITIONS.has(key) && actor !== 'human') {
    throw Object.assign(new Error('任务验收（→ done）仅人可操作'), { code: 'human_gate' })
  }
  if (actor === 'system' && !SYSTEM_TASK_TRANSITIONS.has(key)) {
    throw Object.assign(new Error(`system 不可发起任务转移 ${from} → ${to}`), { code: 'system_gate' })
  }
}
