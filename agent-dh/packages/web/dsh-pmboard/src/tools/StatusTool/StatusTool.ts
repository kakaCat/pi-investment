/**
 * StatusTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/StatusTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { queryState } from '../../application/query/QueryState.js'
import { STATUS_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { statusSummary } from '../render-summaries.js'

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
          next_actions: {
            type: 'array',
            description: '本窗口可自行推进的目标状态（agent 合法转移；取消/归档为人工闸门不在此列）',
            items: { type: 'string' },
          },
          clause_receive_status: {
            type: 'array',
            description: '本条需求每条功能点的接收状态（FR-3）：done=已完成+证据 / received=已被任务接收 / skipped=本轮裁剪 / **unreceived=未被接收（红）**',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                clause: { type: 'string' },
                state: { type: 'string' },
                by: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          unreceived_clauses: {
            type: 'array',
            description: '未被任何任务接收、也未裁剪的条款（**红**）——存在即为 R9 那类缺口',
            items: { type: 'string' },
          },
          design_docs: {
            type: 'array',
            description: '本条需求设计文档逐份登记态（FR-1）：未登记=on_disk&&!registered / 待确认=registered&&!confirmed / 已落章=confirmed',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                name: { type: 'string', description: '文件名（如 architecture.md）' },
                path: { type: 'string', description: '工作区相对路径' },
                on_disk: { type: 'boolean', description: '磁盘上是否真实存在' },
                registered: { type: 'boolean', description: '产物簿是否有该条（kind=design）' },
                confirmed: { type: 'boolean', description: '是否已落章（confirmedAt !== undefined）' },
                exempted: { type: 'string', description: '有效豁免理由（front-matter design_exempt）' },
                conditional: { type: 'string', description: '条件必交标记：frontend / backend' },
              },
            },
          },
          note: { type: 'string', description: '下一步指引' },
          board_link: { type: 'string', description: '项目看板链接（可在会话中点击跳转）' },
        },
      },
      render: renderSmart(statusSummary),
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => queryState(deps, args, exec),
  } as any)
}
