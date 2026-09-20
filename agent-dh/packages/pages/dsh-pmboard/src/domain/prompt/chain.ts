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
}

/** 六节点的链声明（顺序 = 流水线）。 */
export const STAGE_CHAIN: Readonly<Record<PromptStage, StageChainStep>> = {
  brainstorming: {
    next: 'design',
    tool: 'reqboard_ask_confirm',
    label: '下一步：design —— 用 reqboard_ask_confirm(target=artifact, kind=requirement) 交棒；未获批准不得进入。',
  },
  design: {
    // 2026-09-21 用户裁定：设计阶段只写设计文档——交棒 = 确认设计文档（不再是提交计划）
    next: 'decomposing',
    tool: 'reqboard_ask_confirm',
    label: '下一步：decomposing —— 用 reqboard_ask_confirm(target=artifact, kind=design) 交棒；未获批准不得进入。',
  },
  decomposing: {
    // 2026-09-21 用户裁定：拆分计划在拆分阶段写——交棒 = 批准拆分计划（批准即自动拆分+开跑）
    next: 'implementing',
    tool: 'reqboard_ask_confirm',
    label: '下一步：implementing —— 用 reqboard_ask_confirm(target=plan) 交棒；未获批准不得进入。',
  },
  implementing: {
    next: 'accepting',
    tool: 'reqboard_submit',
    label: '下一步：accepting —— 用 reqboard_submit(kind=verification) 交棒；未获批准不得进入。',
  },
  accepting: {
    next: 'archived',
    tool: 'reqboard_accept_sheet',
    label: '下一步：archived —— 用 reqboard_accept_sheet 交棒；验收通过为人工闸门。',
  },
  archived: {
    next: null,
    tool: 'reqboard_submit',
    label: '下一步：无（归档是终态）—— 材料补齐用 reqboard_submit(kind=archive)。',
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
