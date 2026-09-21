/**
 * reqboard_capture 工具壳（REQ-e3b6a0 t8 / FR-7）——三段式薄壳：prompt + 元数据/入参/输出
 * + execute 委托 application 用例（CaptureRequirement）。**不含任何领域判定**（规则只在 domain）。
 *
 * 为什么参数是"无（可选补充）"：四问题目由用例内部构造（口径与 schema 同源），
 * 调用方只可补充分类上下文——候选名称（title_options）与摘要/依据，不参与取值判定。
 *
 * @module dsh-pmboard/tools/CaptureTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { captureRequirement } from '../../application/use-cases/CaptureRequirement.js'
import { renderSmart } from '../shared.js'
import { captureSummary } from '../render-summaries.js'
import { CAPTURE_PROMPT } from './prompt.js'

export function defineCaptureTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_capture',
    description: CAPTURE_PROMPT,
    parameters: {
      title_options: {
        type: 'array',
        description: '需求名称候选（可选，最多 3 个；首个 = 推荐项，用户仍可自定义输入）',
        items: { type: 'string' },
      },
      summary: {
        type: 'string',
        description: '工作摘要（可选，≤4000 字符；将作为需求描述底稿，留空则用名称兜底）',
      },
      reason: {
        type: 'string',
        description: '立项依据（可选，≤4000 字符）：为什么值得立项，供人工判断',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean', description: '是否立项成功' },
          requirement_id: { type: 'string', description: '创建成功时的 REQ id；未立项为空串' },
          status: { type: 'string', description: '创建成功后的需求状态（brainstorming）' },
          answers: {
            type: 'object',
            additionalProperties: false,
            properties: {
              title: { type: 'string', description: '用户确认的需求名称' },
              category: { type: 'string', description: '用户确认的需求类型' },
              difficulty: { type: 'string', description: '用户确认的提示词难度' },
              docLocation: { type: 'string', description: '用户确认的文档位置' },
            },
          },
          defaults_used: {
            type: 'array',
            description: '走了默认值的问项 id 清单（缺失回落时不静默猜）',
            items: { type: 'string' },
          },
          doc_location: { type: 'string', description: '需求文档存放位置（如 docs/requirements/<REQ>/）' },
          fallback: { type: 'string', description: 'board = 弹框通道不可用（不伪造立项）' },
          note: { type: 'string', description: '结果说明' },
          board_link: { type: 'string', description: '项目看板链接（可在会话中点击跳转）' },
        },
      },
      render: renderSmart(captureSummary),
    },
    timeoutMs: LIMITS.timeoutInteractiveMs,
    execute: async (args: unknown, exec: ToolRunContext) => captureRequirement(deps, args, exec),
  } as any)
}