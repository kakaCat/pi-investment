/**
 * MoveTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/MoveTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeMoveRequirement } from '../../application/use-cases/MoveRequirement.js'
import { MOVE_PROMPT } from './prompt.js'
import { renderJson } from '../shared.js'
import { ALL_REQ_CATEGORIES, ALL_REQ_STATUSES, ALL_TASK_PHASES, ALL_TASK_SIDES, ALL_TASK_STATUSES } from '../../shared/protocol.js'

export function defineMoveTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_move',
    description: MOVE_PROMPT,
    parameters: {
      to: {
        type: 'string',
        description: '目标状态：draft / brainstorming / decomposing / implementing / accepting / done / archived / canceled',
        required: true,
        enum: [...ALL_REQ_STATUSES],
      },
      requirement_id: {
        type: 'string',
        description: '需求 id（REQ-xxxxxx）；不传则默认本窗口绑定的那条 open 需求',
      },
      reason: {
        type: 'string',
        description: '推进理由（≤500 字符，写入需求评论供复盘）',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          from: { type: 'string', description: '推进前状态' },
          to: { type: 'string', description: '推进后状态' },
          doc_sync_pending: {
            type: 'array',
            description: '待同步的下游文档（重交下游产物后销标）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                source: { type: 'string' },
                downstream: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          doc_sync_warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => executeMoveRequirement(deps, args, exec),
  } as any)
}
