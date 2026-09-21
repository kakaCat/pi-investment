/**
 * DecomposeTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/DecomposeTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeDecompose } from '../../application/use-cases/Decompose.js'
import { DECOMPOSE_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { decomposeSummary } from '../render-summaries.js'
import { ALL_TASK_PHASES, ALL_TASK_SIDES } from '../../shared/protocol.js'

export function defineDecomposeTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_decompose',
    description: DECOMPOSE_PROMPT,
    parameters: {
      requirement_id: {
        type: 'string',
        description: '需求 id（REQ-xxxxxx）；不传则默认本窗口绑定的那条需求',
      },
      tasks: {
        type: 'array',
        description: '任务清单。W7 边界：计划未含任务表时必传（本工具即任务卡创作口，每卡须含 implementation+可证伪 acceptance）；计划已含任务表时可不传（落库批准的计划）或传（key 须与计划一致）',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            key: { type: 'string', description: '批次内引用键（如 t1；depends_on 用它引用）' },
            title: { type: 'string', description: '任务标题（≤120 字符，动词开头）' },
            description: { type: 'string', description: '任务说明' },
            phase: {
              type: 'string',
              description: '流水线阶段：doc / ui / analysis / implement / test / review / merge',
              enum: [...ALL_TASK_PHASES],
            },
            side: {
              type: 'string',
              description: '端侧：frontend / backend / fullstack / doc',
              enum: [...ALL_TASK_SIDES],
            },
            depends_on: {
              type: 'array',
              description: '依赖：同批任务的 key 或已存在任务 id（无依赖不传）',
              items: { type: 'string' },
            },
            acceptance: { type: 'string', description: '验收标准（可证伪：跑什么、看到什么算过）' },
            implementation: { type: 'string', description: '实施方案（W7 任务卡创作必填：改哪些文件、步骤、验证方式）' },
            context: { type: 'string', description: '需求背景摘要（自足执行用）' },
            requirement_refs: {
              type: 'array',
              description: '本卡交付的需求条款根编号（如 ["FR-1","FR-4"]）。覆盖门禁用它核对「需求每条都有落点」；不填视为未覆盖任何条款',
              items: { type: 'string' },
            },
            skip_integration: { type: 'boolean', description: '是否跳过联调（默认按 side 推导）' },
          },
        },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          requirement_status: { type: 'string', description: '拆分后需求状态（rollup 可能已推进）' },
          created: {
            type: 'array',
            description: '落库的任务（key → 真实任务 id）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                key: { type: 'string' },
                id: { type: 'string' },
                title: { type: 'string' },
                depends_on: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          thin_cards: { type: 'array', items: { type: 'string' }, description: '缺实施方案的薄卡（历史批准计划）' },
          warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderSmart(decomposeSummary),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    execute: async (args: unknown, exec: ToolRunContext) => executeDecompose(deps, args, exec),
  } as any)
}
