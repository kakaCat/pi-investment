/**
 * reqboard_confirm_receipt 工具壳（REQ-260924213231-b1c4 T-6 · serves: FR-3 / I-4）——挂起确认回执。
 *
 * 只读：命中 ticket → 读回执/台账（幂等）；未知或过期 ticket → 抛 \`REQBOARD_UNKNOWN_TICKET\`（E-5）。
 * 响应字段与 interfaces.md I-4 字段明细一一对应（success/confirmed/advanced/from/to/requirement_id/note）。
 *
 * @module dsh-pmboard/tools/ConfirmReceiptTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { confirmReceipt } from '../../application/use-cases/ConfirmReceipt.js'
import { renderSmart } from '../shared.js'
import { confirmReceiptSummary } from '../render-summaries.js'
import { CONFIRM_RECEIPT_PROMPT } from './prompt.js'

export function defineConfirmReceiptTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_confirm_receipt',
    description: CONFIRM_RECEIPT_PROMPT,
    parameters: {
      ticket: {
        type: 'string',
        description: 'reqboard_ask_confirm 返回 pending=true 时的 ticket（pc-…）；必填',
        required: true,
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          confirmed: { type: 'boolean', description: '以台账为准：目标产物 confirmedAt / 计划 approvedAt 已写 → true' },
          advanced: { type: 'boolean', description: '是否已推进（同 ask_confirm 语义）' },
          from: { type: 'string', description: '推进前状态' },
          to: { type: 'string', description: '推进后状态' },
          requirement_id: { type: 'string', description: '被确认的需求 id' },
          user_choice: { type: 'string', description: '非肯定作答时用户选中的选项文本' },
          user_feedback: { type: 'string', description: '非肯定作答时用户输入的修改意见' },
          note: { type: 'string', description: '回执结论一句话（人话）' },
        },
      },
      render: renderSmart(confirmReceiptSummary),
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => confirmReceipt(deps, args, exec),
  } as any)
}
