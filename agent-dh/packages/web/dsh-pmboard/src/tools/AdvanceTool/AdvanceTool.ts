/**
 * AdvanceTool（REQ-4842fe t10）——工具名 `reqboard_task_run`。
 *
 * 事件链的**对外入口**：一次调用推进当前 ready 的一张子卡（一次独立 workflow run），
 * 并在链尾自动收尾 / rollup。工具壳只做协议转换与窗口绑定校验，编排全在 AdvanceChain 用例。
 *
 * 纪律：工具壳不得出现状态字面量比较（tools-dispatch 门禁）——状态判断一律走 application。
 *
 * @module dsh-pmboard/tools/AdvanceTool/AdvanceTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { advanceRequirement, progressOf } from '../../application/use-cases/AdvanceChain.js'
import { selectAdvanceEvent } from '../../application/internal/advance-select.js'
import { openRequirementsFor } from '../../application/internal/window.js'
import { ADVANCE_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { moveSummary } from '../render-summaries.js'

interface AdvanceParams {
  task_id: string
}

export function defineAdvanceTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_run',
    description: ADVANCE_PROMPT,
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
          subtask_executed: { type: 'object', additionalProperties: true },
          next_ready: { type: 'object', additionalProperties: true },
          chain: { type: 'object', additionalProperties: true },
          blocked: { type: 'object', additionalProperties: true },
          parent_status: { type: 'string' },
          stopped: { type: 'string' },
          error: { type: 'string' },
        },
      },
      render: renderSmart(moveSummary),
    },
    timeoutMs: LIMITS.timeoutInteractiveMs,
    async execute(args: AdvanceParams, exec: unknown): Promise<Record<string, unknown>> {
      const windowKey = deps.session.windowKey(exec)
      const snap = deps.repo.snapshot()
      const task = snap.tasks.find((t) => t.id === args.task_id)
      if (task === undefined) {
        return { success: false, task_id: args.task_id, error: '任务不存在：' + args.task_id }
      }
      const bound = openRequirementsFor(snap, windowKey)
      if (!bound.some((r) => r.id === task.requirementId)) {
        return { success: false, task_id: task.id, error: '任务不属于本窗口绑定的需求' }
      }
      // 显式触发 = 开启自动链（等价于"推倒第一张骨牌"）；已开启则保持不变。
      if (snap.requirements.find((r) => r.id === task.requirementId)?.autoRun !== true) {
        await deps.repo.mutate('task-run-autorun', (ledger) => {
          const req = ledger.requirements.find((r) => r.id === task.requirementId)
          if (req === undefined) return undefined
          req.autoRun = true
          return { requirements: [req] }
        })
      }
      // exec 一路透传到叶子（引擎 parent=exec.agent）；缺了它 workflow-ptc 读 parent.session 会抛错。
      const out = await advanceRequirement(deps, task.requirementId, exec)
      const after = deps.repo.snapshot()
      const executed = [...out.steps].reverse().find((s) => s.subtaskId !== undefined)
      const progress = progressOf(after, task.requirementId)
      const sel = selectAdvanceEvent({ tasks: after.tasks }, task.requirementId, LIMITS.advanceMaxParallelParents)
      const nextReady = sel !== undefined && sel.event === 'RUN_SUBTASK'
        ? { id: sel.subtaskId, stageKind: after.tasks.find((t) => t.id === sel.subtaskId)?.stageKind ?? '' }
        : null
      const subtaskExecuted = executed === undefined
        ? null
        : {
            id: executed.subtaskId,
            stageKind: after.tasks.find((t) => t.id === executed.subtaskId)?.stageKind ?? '',
            status: after.tasks.find((t) => t.id === executed.subtaskId)?.status ?? '',
          }
      return {
        success: true,
        task_id: task.id,
        subtask_executed: subtaskExecuted,
        next_ready: nextReady,
        chain: { done: progress.subtasksDone, total: progress.subtasksTotal },
        blocked: out.stopped === 'paused' ? { subtaskId: executed?.subtaskId ?? '', reason: executed?.detail ?? '' } : null,
        parent_status: after.tasks.find((t) => t.id === task.id)?.status ?? '',
        stopped: out.stopped,
      }
    },
  } as any)
}
