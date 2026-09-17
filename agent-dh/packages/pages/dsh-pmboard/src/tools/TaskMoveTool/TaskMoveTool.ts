/**
 * TaskMoveTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/TaskMoveTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeMoveTask } from '../../application/use-cases/MoveTask.js'
import { TASK_MOVE_PROMPT } from './prompt.js'
import { renderJson } from '../shared.js'
import { ALL_REQ_CATEGORIES, ALL_REQ_STATUSES, ALL_TASK_PHASES, ALL_TASK_SIDES, ALL_TASK_STATUSES } from '../../shared/protocol.js'

export function defineTaskMoveTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_move',
    description: TASK_MOVE_PROMPT,
    parameters: {
      task_id: { type: 'string', description: '任务 id（t-xxxxxx）', required: true },
      to: {
        type: 'string',
        description: '目标状态：todo / in_progress / integrating / testing / in_review / done / canceled',
        required: true,
        enum: [...ALL_TASK_STATUSES],
      },
      reason: { type: 'string', description: '推进理由（≤500 字符；写入任务留痕）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          requirement_id: { type: 'string' },
          from: { type: 'string' },
          to: { type: 'string' },
          requirement_status: { type: 'string' },
          task_card: {
            type: 'object',
            additionalProperties: false,
            description: '开工说明书：task_move→in_progress 时返回任务卡全文',
            properties: {
              title: { type: 'string' },
              description: { type: 'string' },
              acceptance: { type: 'string' },
              implementation: { type: 'string' },
              context: { type: 'string' },
              depends_on: { type: 'array', items: { type: 'string' } },
              doc_path: { type: 'string' },
            },
          },
          blockers: {
            type: 'array',
            description: '未完成任务清单（需求未进验收的原因）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
              },
            },
          },
          warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderJson,
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => executeMoveTask(deps, args, exec),
  } as any)
}
