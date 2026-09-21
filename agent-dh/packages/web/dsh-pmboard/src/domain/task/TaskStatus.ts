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
  | 'todo'        // 待开始（自足任务卡落库）
  | 'in_progress' // 开发中（执行会话绑定）
  | 'integrating' // 联调中（前后端汇合，可跳过）
  | 'testing'     // 测试中（单测输出证据）
  | 'in_review'   // 待复核（等人；2026-09-21 裁定统一为此名，与需求级「验收」区分）
  | 'done'        // 已完成（仅人）
  | 'canceled'    // 已取消

/**
 * 任务状态的**展示顺序**（看板按此排序：待开始 → 开发中 → 待复核 → 已完成）。
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
  // REQ-4842fe t2/FR-15：done 不再是绝对终态——"受新需求描述推翻"的卡可由**人**重开
  // （done→in_progress）或取消（done→canceled）。两条都进 HUMAN_ONLY_TASK_TRANSITIONS，
  // agent/system 一律拒绝（自动链不得推翻已完成结论）。
  done: ['in_progress', 'canceled'],
  canceled: ['todo'],
}

/**
 * 卡片角色（REQ-4842fe t2）：决定用哪张转移表。
 *  - legacy：无 parentId 的存量/普通卡 → 既有五段状态机（行为完全不变）；
 *  - parent：新式父卡（有子卡链）→ 只走 todo→in_progress→done；
 *  - subtask：子卡 → 收紧四态（不进 integrating/testing/in_review，避免递归语义）。
 *
 * 为什么用 role 而不是给 TaskStatus 加字段：状态与角色是两个正交维度，
 * 转移合法性同时取决于二者，把 role 做成入参才能在不改类型的前提下收紧子卡。
 */
export type TaskRole = 'parent' | 'subtask' | 'legacy'

/**
 * 子卡转移表（REQ-4842fe FR-5）：todo → in_progress → done（+ canceled）。
 *  - in_progress → todo = 失败回退（配合 attempt+1 与 revisions(kind=rollback)）；
 *  - done → in_progress / canceled = 人工门（重开/取消受影响的完成卡）；
 *  - integrating/testing/in_review 三个中段状态对子卡**无出边**（落进去即非法）。
 */
export const SUBTASK_TRANSITIONS: Readonly<Record<TaskStatus, readonly TaskStatus[]>> = {
  todo: ['in_progress', 'canceled'],
  in_progress: ['done', 'todo', 'canceled'],
  done: ['in_progress', 'canceled'],
  canceled: ['todo'],
  integrating: [],
  testing: [],
  in_review: [],
}

/**
 * 新式父卡转移表（REQ-4842fe FR-5）：todo → in_progress → done。
 * 中段（integrating/testing/in_review）由子卡链承载，父卡不动——故这三个状态对父卡无出边。
 * 与子卡表当前取值相同，但**语义独立**（将来收紧任一角色不应顺手改另一个）。
 */
export const PARENT_TRANSITIONS: Readonly<Record<TaskStatus, readonly TaskStatus[]>> = {
  todo: ['in_progress', 'canceled'],
  in_progress: ['done', 'todo', 'canceled'],
  done: ['in_progress', 'canceled'],
  canceled: ['todo'],
  integrating: [],
  testing: [],
  in_review: [],
}

/**
 * 角色 → 转移表。
 *  - subtask / parent：收紧三态（中段无出边）；
 *  - legacy：既有五段表（存量卡行为完全不变）。
 */
export function taskTransitionsFor(role: TaskRole): Readonly<Record<TaskStatus, readonly TaskStatus[]>> {
  if (role === 'subtask') return SUBTASK_TRANSITIONS
  if (role === 'parent') return PARENT_TRANSITIONS
  return TASK_TRANSITIONS
}

/**
 * 任务人工闸门（代码级仅人）。
 * 2026-09-13 用户裁定（与需求闸门同一口径）：agent 必须能自己把任务跑完——
 * 此前 in_review>done 仅人可操作，而任务完成又驱动需求 rollup，导致任务卡停在
 * 「待复核」、需求进不了验收，看板再次静止。现仅保留**取消/复活**这类破坏性动作
 * 为人工闸门，正常流水线（含任务完成）由执行窗口自行推进。
 */
export const HUMAN_ONLY_TASK_TRANSITIONS: ReadonlySet<string> = new Set([
  'todo>canceled',
  'in_progress>canceled',
  'integrating>canceled',
  'testing>canceled',
  'in_review>canceled',
  'canceled>todo', // 复活已取消任务：仅人
  // REQ-4842fe t2/FR-15：done 卡的重开与取消同为破坏性人工动作（自动链不得重开 done 卡）。
  'done>in_progress', // 重开（受新需求描述推翻时由人触发）
  'done>canceled',
])

/** system 允许的任务转移（执行结算用）：开始执行与退回。 */
export const SYSTEM_TASK_TRANSITIONS: ReadonlySet<string> = new Set([
  'todo>in_progress',
  'in_progress>todo',
])

/**
 * 工作流执行（workflow run / stage）状态词汇（REQ-f0579a t4）。
 * 此前散在 tools/TaskExecuteTool 与 types.ts 的字面量联合里——layer-boundary 门禁
 * 要求状态词汇单点在 domain，适配层只引用常量/类型。
 */
export const WORKFLOW_RUN_STATUS = { Completed: 'completed', Failed: 'failed' } as const
export type WorkflowRunStatus = typeof WORKFLOW_RUN_STATUS[keyof typeof WORKFLOW_RUN_STATUS]

/**
 * workflow run/stage 是否已完成（REQ-f0579a t4）。
 * 状态**判断**也是状态语义，单点在 domain：tools-dispatch 门禁禁止工具壳出现任何
 * `status ===` 比较（即便右值是 domain 常量），适配层一律改调本函数。
 */
export const isWorkflowRunCompleted = (status: string): boolean => status === WORKFLOW_RUN_STATUS.Completed

/**
 * 任务状态 → 看板进度百分比（reqboard_task_status 的 progress 语义）。
 * 进度是**展示语义**但词汇表是**状态语义**——键必须是合法 TaskStatus，故单点于此。
 */
export const TASK_STATUS_PROGRESS: Readonly<Record<TaskStatus, number>> = {
  todo: 0,
  in_progress: 20,
  integrating: 50,
  testing: 70,
  in_review: 85,
  done: 100,
  canceled: 0,
}

export function canTaskTransition(from: TaskStatus, to: TaskStatus, role: TaskRole = 'legacy'): boolean {
  return taskTransitionsFor(role)[from].includes(to)
}

/**
 * 任务转移闸门校验。role 缺省 'legacy' —— 既有调用点（工具/路由/用例）零改动即保持原行为；
 * 子卡与父卡由新的调用方显式传 role 收紧。
 */
export function assertTaskTransition(
  from: TaskStatus,
  to: TaskStatus,
  actor: ActorKind,
  role: TaskRole = 'legacy',
): void {
  if (!canTaskTransition(from, to, role)) {
    throw Object.assign(new Error(`任务状态不允许从 ${from} 转移到 ${to}`), { code: 'invalid_transition' })
  }
  const key = `${from}>${to}`
  if (HUMAN_ONLY_TASK_TRANSITIONS.has(key) && actor !== 'human') {
    // 2026-09-21：旧文案「任务验收（→ done）仅人可操作」已过时——人工闸门现覆盖取消/复活/重开，
    // 且 in_review 统一叫「待复核」（与需求级「验收」区分），不再用「验收」指任务状态。
    throw Object.assign(new Error('该任务转移为人工闸门，仅人可操作'), { code: 'human_gate' })
  }
  if (actor === 'system' && !SYSTEM_TASK_TRANSITIONS.has(key)) {
    throw Object.assign(new Error(`system 不可发起任务转移 ${from} → ${to}`), { code: 'system_gate' })
  }
}
