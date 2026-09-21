/**
 * CreateTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/CreateTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeCreateRequirement } from '../../application/use-cases/CreateRequirement.js'
import { CREATE_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { createSummary } from '../render-summaries.js'
import { ALL_REQ_CATEGORIES, ALL_PROMPT_DIFFICULTIES } from '../../shared/protocol.js'

export function defineCreateTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_create',
    description: CREATE_PROMPT,
    parameters: {
      title: {
        type: 'string',
        description: '需求名称（用户三问弹框确认值，≤120 字符；人工确认时可改）',
        required: true,
      },
      category: {
        type: 'string',
        description: '需求分类：feature / bug / doc / refactor / spike / chore',
        required: true,
        enum: [...ALL_REQ_CATEGORIES],
      },
      summary: {
        type: 'string',
        description: '工作摘要（≤4000 字符；将作为需求描述底稿，留空则用 title 兜底）',
      },
      reason: {
        type: 'string',
        description: '立项依据（≤4000 字符）：为什么值得立项，供人工判断',
      },
      prompt_difficulty: {
        type: 'string',
        description: '提示词难度级别：simple / standard / advanced / expert（默认 standard）',
        enum: [...ALL_PROMPT_DIFFICULTIES],
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean', description: '是否成功' },
          requirement_id: { type: 'string', description: '新需求 id（REQ-xxxxxx）' },
          title: { type: 'string', description: '需求名称' },
          category: { type: 'string', description: '需求分类' },
          status: { type: 'string', description: '需求状态（draft）' },
          note: { type: 'string', description: '后续流程说明' },
          board_link: { type: 'string', description: '项目看板链接（可在会话中点击跳转）' },
        },
      },
      render: renderSmart(createSummary),
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => executeCreateRequirement(deps, args, exec),
  } as any)
}
