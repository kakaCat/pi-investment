/**
 * reqboard_ask_confirm 工具壳（REQ-47939a t8）——**confirm_artifact 并入 ask_confirm**。
 *
 * 三条路径与现状逐一对应：① evidence 非空 → ConfirmArtifact（文字证据核验）；
 * ② evidence 为空 + 弹框可用 → AskConfirm（弹框落章+推进）；
 * ③ 弹框不可用 → AskConfirm 内部返回 fallback=board。返回键为两个用例的并集。
 *
 * @module dsh-pmboard/tools/AskConfirmTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { askConfirm } from '../../application/use-cases/AskConfirm.js'
import { confirmArtifact } from '../../application/use-cases/ConfirmArtifact.js'
import { normalizeText } from '../../shared/protocol.js'
import { renderSmart } from '../shared.js'
import { askConfirmSummary } from '../render-summaries.js'
import { ASK_CONFIRM_PROMPT } from './prompt.js'

export function defineAskConfirmTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_ask_confirm',
    description: ASK_CONFIRM_PROMPT,
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      target: { type: 'string', description: 'artifact（确认产物）| plan（批准拆分计划）', required: true },
      kind: { type: 'string', description: '产物类型（target=artifact 时必填）：requirement/design/plan/decomposition/verification/archive' },
      question: { type: 'string', description: '弹框问题（写清确认什么、确认后会发生什么；弹框路径必填）' },
      options: {
        type: 'array',
        description: '选项标签列表（第一个 = 肯定项，确认后落章+推进；缺省：确认推进/需要修改/暂停）',
        items: { type: 'string' },
      },
      advance: { type: 'boolean', description: '确认后是否自动推进到下一阶段（默认 true）' },
      evidence: { type: 'string', description: '文字证据路径：用户在 ask_user_question 中的确认答复原文（必填于该路径，须命中真实用户消息）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          confirmed: { type: 'boolean', description: '弹框路径：用户是否选肯定项' },
          advanced: { type: 'boolean', description: '弹框路径：是否已自动推进' },
          from: { type: 'string', description: '弹框路径：推进前状态' },
          to: { type: 'string', description: '弹框路径：推进后状态' },
          requirement_id: { type: 'string', description: '被确认的需求 id' },
          fallback: { type: 'string', description: 'board = 弹框不可用，请走看板确认按钮' },
          target: { type: 'string', description: '文字证据路径：artifact | plan' },
          kind: { type: 'string', description: '文字证据路径：产物类型' },
          via: { type: 'string', description: '文字证据路径：确认来源（session）' },
          evidence_verified: { type: 'boolean', description: '文字确认是否通过 capture-hook 核验（命中真实用户消息）' },
          user_choice: { type: 'string', description: '弹框路径（非肯定项）：用户选择的选项文本' },
          user_feedback: { type: 'string', description: '弹框路径（非肯定项）：用户输入的修改意见或反馈' },
          gate_failure: {
            type: 'object',
            description: 'REQ-2d1c74 FR-2：G2 文档集完整性闸门未过（落章保留、推进被拦）时的结构化缺口（code/gaps/message）',
            additionalProperties: true,
          },
          note: { type: 'string' },
        },
      },
      render: renderSmart(askConfirmSummary),
    },
    timeoutMs: LIMITS.timeoutInteractiveMs,
    execute: async (args: unknown, exec: ToolRunContext) => {
      const evidence = normalizeText(((args ?? {}) as { evidence?: unknown }).evidence, 'evidence', 2000)
      return evidence.length > 0 ? confirmArtifact(deps, args, exec) : askConfirm(deps, args, exec)
    },
  } as any)
}
