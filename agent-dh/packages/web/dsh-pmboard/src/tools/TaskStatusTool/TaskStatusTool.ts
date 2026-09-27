/**
 * TaskStatusTool 工具壳（REQ-260927144541-0481 FR-4/FR-6 / design I-4）——reqboard_task_status。
 *
 * 单卡执行状态：**读台账**的 lastRun / lastReport（workflow run 证据的持久化载体）。
 * 此前读任务卡里那个早已死掉的 workflow 段落（标题 = 两个井号 + Workflow）——**全仓无写入方**（grep 只命中本文件的读取端），
 * 于是"状态查询"永远查不到东西；且用 fs 直连相对 cwd 的路径绕过端口（P5/P6）。
 *
 * 向后兼容：workflow 键名保留（既有消费者契约），内容换为真实 run 摘要。
 * 纪律：不写状态字面量（layer-boundary 门禁）——状态→进度映射单点在 domain/task/TaskStatus。
 *
 * @module dsh-pmboard/tools/TaskStatusTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { TASK_STATUS_PROGRESS } from '../../domain/task/TaskStatus.js'
import { fmt } from '../../domain/text/fmt.js'
import { renderSmart } from '../shared.js'
import { taskStatusSummary } from '../render-summaries.js'

interface TaskStatusParams {
  task_id: string
}

export function defineTaskStatusTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_status',
    description: [
      '用于：查询单张任务的执行状态与最近一次 run/汇报（读台账 lastRun/lastReport，不读卡文档）。',
      '入参 task_id；返回 status/progress 与真实 run 摘要（workflow 键保留，内容已换为 run 摘要）。',
    ].join(''),
    parameters: {
      task_id: {
        type: 'string',
        description: '任务 id（t-xxxxxx）',
        required: true
      }
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          status: { type: 'string' },
          progress: { type: 'number' },
          run: {
            type: 'object',
            additionalProperties: false,
            properties: {
              ok: { type: 'boolean' },
              stopReason: { type: 'string' },
              valueNonEmpty: { type: 'boolean' },
              reason: { type: 'string' },
            },
          },
          report: {
            type: 'object',
            additionalProperties: false,
            properties: {
              summary: { type: 'string' },
              completedCount: { type: 'number' },
              filesChangedCount: { type: 'number' },
            },
          },
          workflow: {
            type: 'object',
            additionalProperties: true,
            description: '键保留（既有消费者契约）：内容换为真实 run 摘要'
          },
          error: { type: 'string' },
        }
      },
      render: renderSmart(taskStatusSummary)
    },
    timeoutMs: LIMITS.timeoutReadMs,
    async execute(args: TaskStatusParams): Promise<Record<string, unknown>> {
      // 任务来自队列（REQ-260927202051-f6df）：v9 台账已无 tasks。
      const store = deps.taskStore
      if (store === undefined) {
        return {
          success: false,
          task_id: args.task_id,
          status: 'error',
          progress: 0,
          // 未装配 = 组合根配置错误：显式失败，不谎报"任务不存在"
          error: '任务存储（TaskStore）未装配，无法读取任务',
        }
      }
      const task = await store.get(args.task_id)
      if (task === undefined) {
        return {
          success: false,
          task_id: args.task_id,
          status: 'not_found',
          progress: 0,
          error: fmt('任务不存在：{id}', { id: args.task_id }),
        }
      }
      const progress = (TASK_STATUS_PROGRESS as Record<string, number>)[task.status] ?? 0
      const run = task.lastRun
      const report = task.lastReport
      return {
        success: true,
        task_id: task.id,
        status: task.status,
        progress: Math.min(100, Math.max(0, progress)),
        ...(run !== undefined ? {
          run: {
            ok: run.ok,
            stopReason: run.stopReason,
            valueNonEmpty: run.valueNonEmpty,
            ...(run.reason !== undefined ? { reason: run.reason } : {}),
          },
        } : {}),
        ...(report !== undefined ? {
          report: {
            summary: report.completed.length > 0 ? report.completed.join('；') : '无完成项',
            completedCount: report.completed.length,
            filesChangedCount: report.filesChanged.length,
          },
        } : {}),
        ...(run !== undefined ? {
          workflow: { at: run.at, ok: run.ok, stopReason: run.stopReason, valueNonEmpty: run.valueNonEmpty },
        } : {}),
      }
    }
  } as any)
}
