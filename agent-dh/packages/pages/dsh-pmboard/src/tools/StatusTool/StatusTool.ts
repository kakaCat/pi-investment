/**
 * StatusTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/StatusTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import type { UseCaseDeps } from '../../application/ports.js'
import { queryState } from '../../application/query/QueryState.js'
import { STATUS_PROMPT } from './prompt.js'
import { renderJson } from '../shared.js'
import { ALL_REQ_CATEGORIES, ALL_REQ_STATUSES, ALL_TASK_PHASES, ALL_TASK_SIDES, ALL_TASK_STATUSES } from '../../shared/protocol.js'

export function defineStatusTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_status',
    description: STATUS_PROMPT,
    parameters: {},
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          window_key: { type: 'string', description: '本窗口标识' },
          open_count: { type: 'number', description: '本窗口进行中需求数' },
          bound: { type: 'boolean', description: '本窗口是否已绑定进行中需求（bound 时不再立项）' },
          open_requirements: {
            type: 'array',
            description: '本窗口进行中需求简要列表',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
                category: { type: 'string' },
              },
            },
          },
          has_pending: { type: 'boolean', description: '本窗口是否已有遗留待确认建议卡（旧流程 triage）' },
          pending_triage_id: { type: 'string', description: '最近遗留 pending triage id（无则空串）' },
          next_actions: {
            type: 'array',
            description: '本窗口可自行推进的目标状态（agent 合法转移；取消/归档为人工闸门不在此列）',
            items: { type: 'string' },
          },
          note: { type: 'string', description: '下一步指引' },
        },
      },
      render: renderJson,
    },
    timeoutMs: 15000,
    execute: async (args: unknown, exec: ToolRunContext) => queryState(deps, args, exec),
  } as any)
}
