/**
 * TaskExecuteTool 薄壳（REQ-4842fe t10）：原「6 阶段 workflow 工具」路径已**下线**。
 *
 * 为什么下线：它依赖被禁用的 ctx.tools.workflow，且生成的脚本用了引擎不存在的 ctx.subagent
 * （design/workflow-engine-contract §4 两条真实踩坑）。唯一执行入口现在是 reqboard_task_run
 * （AdvanceTool → AdvanceChain → ctx.workflowEngine）。
 *
 * 本工具保留为**兼容别名**：语义等价于 reqboard_task_run，不再依赖任何被禁工具、不再生成脚本。
 *
 * @module dsh-pmboard/tools/TaskExecuteTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { advanceRequirement } from '../../application/use-cases/AdvanceChain.js'
import { openRequirementsFor } from '../../application/internal/window.js'
import { renderSmart } from '../shared.js'
import { taskExecuteSummary } from '../render-summaries.js'

export function defineTaskExecuteTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_execute',
    description: '【兼容别名，等价 reqboard_task_run】推进任务的自动实施链（父卡开工/子卡执行/收尾/rollup）。',
    parameters: {
      task_id: { type: 'string', description: '父卡 id（t-xxxxxx）', required: true },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          status: { type: 'string' },
          stopped: { type: 'string' },
          error: { type: 'string' },
        },
      },
      render: renderSmart(taskExecuteSummary),
    },
    timeoutMs: LIMITS.timeoutInteractiveMs,
    async execute(args: { task_id: string }, exec: unknown): Promise<Record<string, unknown>> {
      const windowKey = deps.session.windowKey(exec)
      const snap = deps.repo.snapshot()
      const task = snap.tasks.find((t) => t.id === args.task_id)
      if (task === undefined) return { success: false, task_id: args.task_id, status: 'error', error: '任务不存在：' + args.task_id }
      const bound = openRequirementsFor(snap, windowKey)
      if (!bound.some((r) => r.id === task.requirementId)) {
        return { success: false, task_id: task.id, status: 'error', error: '任务不属于本窗口绑定的需求' }
      }
      const out = await advanceRequirement(deps, task.requirementId)
      return { success: true, task_id: task.id, status: out.stopped, stopped: out.stopped }
    },
  } as any)
}
