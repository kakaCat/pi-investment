/**
 * TaskReportTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/TaskReportTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeReportTask } from '../../application/use-cases/ReportTask.js'
import { TASK_REPORT_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { taskReportSummary } from '../render-summaries.js'

export function defineTaskReportTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_report',
    description: TASK_REPORT_PROMPT,
    parameters: {
      task_id: { type: 'string', description: '任务 id（t-xxxxxx）', required: true },
      summary: { type: 'string', description: '一句话汇报：做了什么（≤2000 字符）', required: true },
      completed: {
        type: 'array',
        description: '完成项列表（1-50 条）',
        items: { type: 'string' },
      },
      files_changed: {
        type: 'array',
        description: '改动文件列表（工作区相对路径，0-50 条）',
        items: { type: 'string' },
      },
      next_step: { type: 'string', description: '下一步（≤1000 字符；无则空串）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          requirement_id: { type: 'string' },
          doc_path: { type: 'string', description: '任务卡文档路径（工作区相对）' },
          artifact_registered: { type: 'boolean', description: '本次是否新登记产物（false=已存在，幂等跳过重登）' },
          report_index: { type: 'number', description: '本次汇报是第几段（从 1 起）' },
          note: { type: 'string' },
        },
      },
      render: renderSmart(taskReportSummary),
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => executeReportTask(deps, args, exec),
  } as any)
}
