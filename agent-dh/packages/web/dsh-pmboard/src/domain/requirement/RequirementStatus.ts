/**
 * 需求状态机（REQ-47939a t2）——状态枚举 + 合法转移表 + 两个查询函数。
 *
 * 为什么单独成文件：状态与人工闸门此前散在 protocol.ts / agent-tools.ts / routes.ts /
 * rollup.ts 四处各判一遍（D2）。搬到这里后，**同一条状态机规则全仓只有一处实现**，
 * 路由、工具、客户端渲染都引用同一份表（INV-1 / INV-2）。
 *
 * 本文件是纯数据 + 纯函数：不 import node:/@deepseek-ai/，不碰时间与随机数
 * （domain 层硬约束，由 tests/layer-boundary.test.ts 机械检查）。
 *
 * 注释随代码搬（REQ-47939a 硬约束：不重写、不删"为什么/事故出处"型注释）。
 */

import type { ActorKind } from '../actor.js'

/**
 * 需求流水线 = superpowers 的三段式落成状态（2026-09-13 用户要求「需求从创建开始就有流程」）：
 *   立项（draft）→ 需求分析（brainstorming）→ 设计（design）→ 拆分（decomposing）
 *        → 实施（implementing）→ 验收（accepting）→ 归档（archived）
 * 「拆分计划待批」不是独立状态：它是 design 的子状态（plan.approvedAt 未写入），看板用
 * 卡面 chip 表达——批准是拆分的前置闸门，不额外占一条泳道。
 */
export type RequirementStatus =
  | 'draft'         // 立项（draft）：想法落成需求卡
  | 'brainstorming' // 需求分析（brainstorming）：探索意图/边界/方案（原 reviewing）
  | 'design'      // 设计（design）：编写设计文档（design/*.md）
  | 'decomposing'   // 拆分（decomposing）：编写拆分计划（decomposition.md + 任务表）
  | 'implementing'  // 实施（implementing）：按任务卡逐项执行（原 executing-plans）
  | 'accepting'     // 验收（accepting）：提交交付物、人工验收
  | 'done'          // 【legacy】历史"完成"态：REQ-9f4a44 起不再进入，仅用于老台账兼容读取
  | 'archived'      // 归档（archived）：归档文档、合并知识库
  | 'canceled'

/** 流水线节点键 = 需求主状态（除 canceled）。会话框进度条、节点详情、产物闸门共用。 */
export type StageKey = Exclude<RequirementStatus, 'canceled'>

/**
 * 流水线主节点键（7 个）= MAIN 状态：不含 legacy done 与 canceled。
 *
 * 为什么需要它：done 只作老台账兼容（见 RequirementStatus.done 注释），
 * 不在流程图节点（MAIN_REQ_STATUSES / ALL_STAGE_KEYS）里；节点标签表与渲染
 * 注册表按主节点为键，用 MainStageKey 才能如实表达「done 没有渲染器/标签」。
 */
export type MainStageKey = Exclude<StageKey, 'done'>

/**
 * 领域状态常量（REQ-47939a t7 收口）：适配层不得写状态字面量，一律引用这些常量。
 * 它们表达的是**领域知识**——"新需求从哪开始""验收通过去哪""返工回哪"——不该由路由决定。
 */
export const INITIAL_REQ_STATUS: RequirementStatus = 'draft'
export const REWORK_REQ_STATUS: RequirementStatus = 'implementing'
export const ACCEPTED_REQ_STATUS: RequirementStatus = 'archived'
export const CANCELED_REQ_STATUS: RequirementStatus = 'canceled'

/** 需求状态合法转移表。 */
export const REQ_TRANSITIONS: Readonly<Record<RequirementStatus, readonly RequirementStatus[]>> = {
  draft: ['brainstorming', 'canceled'],
  brainstorming: ['design', 'draft', 'canceled'],
  design: ['decomposing', 'brainstorming', 'canceled'],
  decomposing: ['implementing', 'design', 'canceled'],
  // REQ-4842fe t2/FR-14：实施中发现"需求描述不对"时，必须能退回上游重新描述——
  // 现状缺口是 implementing 没有回退路径（只能硬着头皮验收或取消）。implementing→design
  // 是**人工闸门**（破坏性：会触发卡片修订），退回后重走 design→批准计划→拆分→实施。
  implementing: ['accepting', 'design', 'canceled'],
  // REQ-9f4a44：验收通过 → 直接归档（无 done 中转）
  accepting: ['archived', 'implementing', 'canceled'],
  done: [], // 【legacy】不再进入，也不允许从它转出（历史记录保持原样）
  canceled: ['draft', 'archived'],
  archived: [],
}

/**
 * 人工闸门转移（代码级仅人）：方案确认 / 拆分确认 / 人工验收 / 归档。
 * 键格式 'from>to'。agent 与 system 对这些转移一律拒绝。
 */
export const HUMAN_ONLY_REQ_TRANSITIONS: ReadonlySet<string> = new Set([
  // 2026-09-11 用户裁定：agent 必须能自己推进在途需求（此前「确认方案/确认拆分/
  // 验收通过」都是人工闸门 → 每个需求都要人点两三次，看板实质静止）。
  // 2026-09-14 用户裁定（REQ-31e11f，部分回调 09-11）：**五道人工确认门**——
  // 产物存在 ≠ 人已审阅，关键节点产物必须人确认后才放行（看板一键确认+登记即通知
  // 保流速）。新增两道在途硬门：需求文档（brainstorming>design）、
  // 拆分清单（decomposing>implementing）。
  'brainstorming>design', // 需求文档人工确认（五门之一）
  'decomposing>implementing', // 拆分清单人工确认（五门之一）
  'draft>canceled',
  'brainstorming>canceled',
  'decomposing>canceled',
  'implementing>canceled',
  'accepting>canceled', // 取消需求（破坏性）
  // REQ-4842fe t2/FR-14：返工回上游（实施→设计，重新描述需求）——仅人可发起。
  'implementing>design',
  // REQ-9f4a44：验收通过（人工审核）——agent 可提交验收材料，但"过"必须是人点的；
  // 通过即直接归档（原先拆成 accepting>done + done>archived 两道，现合并为一道）。
  'accepting>archived',
  'canceled>archived', // 取消后归档
])

/**
 * system（rollup）允许自动推进的转移白名单：其余转移 system 一律不可发起。
 *  - draft>brainstorming       需求被窗口接手开工（有直接人类消息）的接手推进；
 *  - implementing>accepting 全部实施任务 done 的 rollup。
 * 人工闸门永不在本白名单内 —— 自动推进不可能越过人工闸门。
 * 2026-09-14：decomposing>implementing 已入人工门（五门裁定），从本白名单移除。
 */
export const SYSTEM_REQ_TRANSITIONS: ReadonlySet<string> = new Set([
  'draft>brainstorming', // 窗口接手开工 → 进入需求分析（方案共创）
  'design>decomposing', // 计划已批准并落库任务 → 自动进入拆分态
  'implementing>accepting', // 全部实施任务 done 的 rollup
])

export function canReqTransition(from: RequirementStatus, to: RequirementStatus): boolean {
  return REQ_TRANSITIONS[from].includes(to)
}

/**
 * 需求转移闸门校验。抛出带 code 的 Error：invalid_transition / human_gate / system_gate。
 */
export function assertReqTransition(from: RequirementStatus, to: RequirementStatus, actor: ActorKind): void {
  if (!canReqTransition(from, to)) {
    throw Object.assign(new Error(`需求状态不允许从 ${from} 转移到 ${to}`), { code: 'invalid_transition' })
  }
  const key = `${from}>${to}`
  if (HUMAN_ONLY_REQ_TRANSITIONS.has(key) && actor !== 'human') {
    throw Object.assign(new Error(`转移 ${from} → ${to} 是人工闸门，仅人可操作`), { code: 'human_gate' })
  }
  if (actor === 'system' && !SYSTEM_REQ_TRANSITIONS.has(key)) {
    throw Object.assign(new Error(`system 不可发起转移 ${from} → ${to}`), { code: 'system_gate' })
  }
}

/** agent 从当前状态可自行推进的目标（排除人工闸门：取消/归档）。 */
export function agentNextActions(status: RequirementStatus): RequirementStatus[] {
  return [...REQ_TRANSITIONS[status]].filter((to) => !HUMAN_ONLY_REQ_TRANSITIONS.has(`${status}>${to}`))
}
