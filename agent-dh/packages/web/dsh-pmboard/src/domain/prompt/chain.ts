/**
 * 节点链声明（REQ-422af1 t5，INV-4/G3）—— "本节点结束后交棒给谁、用什么工具"。
 *
 * P0 的硬性约束是**零行为变更**（解析结果与 t1 冻结快照逐字一致），故当时本表承载链声明；
 * **P1（t7）起按 design/fragments.md §9 把 label 逐字物化进各节点 light/heavy 分片末尾**，
 * gate 5 的"文本内声明"断言随之生效——本表与分片文本必须一致（改其一即须同步改另一）。
 *
 * next 的合法性取自状态机单一事实源 REQ_TRANSITIONS（domain/requirement/RequirementStatus），
 * 本文件不新写状态字面量表。archived 是终态（无后继）→ next=null。
 *
 * @module dsh-pmboard/domain/prompt/chain
 */
import { REQ_TRANSITIONS } from '../requirement/RequirementStatus.js'
import type { PromptStage } from './types.js'

export interface StageChainStep {
  /** 下一节点；null = 终态（状态机无后继） */
  readonly next: PromptStage | null
  /** 交棒工具（必须是已注册的 reqboard_* 工具；由门禁 2 校验） */
  readonly tool: string
  /** 固定形式的链声明行（P1 起已逐字物化进各节点 light/heavy 分片末尾；本表为校验源） */
  readonly label: string
  /**
   * 进入本阶段的**第一个动作**（kickoff 开工令）。
   *
   * 与 label 配对：label 管"什么时候走、用什么工具走"（出口），entry 管"进来先干什么"（入口）。
   * 为什么必须单独有它：闸门唤醒消息此前只有「状态通报 + 阶段纪律清单」，纪律清单讲的是
   * **该交什么**（甚至直接跳到"写文档/提产物"），于是 agent 被叫醒后不知道该先做什么。
   * 消费方两处、同源于本表：H4 唤醒消息、节点输入包「下一步」节。
   */
  readonly entry: string
}

/** 六节点的链声明（顺序 = 流水线）。 */
export const STAGE_CHAIN: Readonly<Record<PromptStage, StageChainStep>> = {
  brainstorming: {
    next: 'design',
    tool: 'reqboard_ask_confirm',
    label: '下一步：design —— 用 reqboard_ask_confirm(target=artifact, kind=requirement) 交棒；未获批准不得进入。',
    entry: '现在开始需求讨论（本阶段第一步）：与用户逐项确认 ① 边界（做什么 / 明确不做什么）② 一句话产品定义 ③ 用户与角色 ④ 功能点（FR-1, FR-2, …）。讨论清楚之前不要写 requirement.md，也不要调 reqboard_submit。',
  },
  design: {
    // 2026-09-21 用户裁定：设计阶段只写设计文档——交棒 = 确认设计文档（不再是提交计划）
    next: 'decomposing',
    tool: 'reqboard_ask_confirm',
    label: '下一步：decomposing —— 用 reqboard_ask_confirm(target=artifact, kind=design) 交棒；未获批准不得进入。',
    entry: '现在开始设计（本阶段第一步）：按已确认的功能点逐条写设计文档（architecture / data-model / interfaces / test-cases），每个章节标注 serves: FR-x。',
  },
  decomposing: {
    // 2026-09-21 用户裁定：拆分计划在拆分阶段写——交棒 = 批准拆分计划（批准即自动拆分+开跑）
    next: 'implementing',
    tool: 'reqboard_ask_confirm',
    label: '下一步：implementing —— 用 reqboard_ask_confirm(target=plan) 交棒；未获批准不得进入。',
    entry: '现在开始拆分（本阶段第一步）：把设计章节落成任务表（key / title / phase / side / depends_on / acceptance），再用 reqboard_submit(kind=plan) 提交待批准。',
  },
  implementing: {
    next: 'accepting',
    tool: 'reqboard_submit',
    label: '下一步：accepting —— 用 reqboard_submit(kind=verification) 交棒；未获批准不得进入。',
    entry: '现在开始实施（本阶段第一步）：按任务卡顺序开工（依赖未满足的先跳过），每完成一张调 reqboard_task_report 汇报。',
  },
  accepting: {
    next: 'archived',
    tool: 'reqboard_accept_sheet',
    label: '下一步：archived —— 用 reqboard_accept_sheet 交棒；验收通过为人工闸门。',
    entry: '现在开始验收（本阶段第一步）：补齐测试证据（在测试文档标 covers: t-xxx）与验收材料，再用 reqboard_submit(kind=verification) 提交。',
  },
  archived: {
    next: null,
    tool: 'reqboard_submit',
    label: '下一步：无（归档是终态）—— 材料补齐用 reqboard_submit(kind=archive)。',
    entry: '归档：用 reqboard_submit(kind=archive) 提交归档材料（需求目录 / 目录内文档清单 / 合并去向）。',
  },
}

/** 该节点的合法后继（状态机单一事实源）。 */
export function legalSuccessors(stage: PromptStage): readonly string[] {
  return REQ_TRANSITIONS[stage]
}

/** next 是否为该节点的合法后继（终态必须是真正的"无后继"）。 */
export function isLegalNext(stage: PromptStage, next: PromptStage | null): boolean {
  const successors = REQ_TRANSITIONS[stage]
  if (next === null) return successors.length === 0
  return successors.includes(next)
}
