/**
 * AcceptSheetTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/AcceptSheetTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { acceptSheet } from '../../application/use-cases/AcceptSheet.js'
import { ACCEPT_SHEET_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { acceptSheetSummary } from '../render-summaries.js'

export function defineAcceptSheetTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_accept_sheet',
    description: ACCEPT_SHEET_PROMPT,
    parameters: {
      requirement_id: { type: 'string', description: '需求 id；不传默认本窗口绑定的需求' },
      batch_size: { type: 'number', description: '本批弹出的最大项数（默认 5，上限 10）' },
      version: { type: 'number', description: '验收单版本（不传取当前 sheet 版本）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          sheet_version: { type: 'number' },
          recorded: { type: 'number', description: '本批记录的裁决数' },
          pending: { type: 'number', description: '剩余待验项数（挂起继续）' },
          passed: { type: 'number' },
          failed: { type: 'number' },
          rework_tasks: { type: 'array', items: { type: 'string' } },
          archived: { type: 'boolean', description: 'true = 全通过并已验收通过归档' },
          status: { type: 'string', description: '确认后的需求状态（archived 等）' },
          fallback: { type: 'string', description: 'board = 弹框不可用，请走看板勾选' },
          note: { type: 'string' },
        },
      },
      render: renderSmart(acceptSheetSummary),
    },
    timeoutMs: LIMITS.timeoutSheetMs,
    execute: async (args: unknown, exec: ToolRunContext) => acceptSheet(deps, args, exec),
  } as any)
}
