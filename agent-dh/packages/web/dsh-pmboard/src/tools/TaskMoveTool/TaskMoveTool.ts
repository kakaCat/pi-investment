/**
 * TaskMoveTool（工具名 reqboard_task_move）——agent 侧任务流转（REQ-260927100007-b8ba FR-7/FR-8）。
 * @module dsh-pmboard/tools/TaskMoveTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeMoveTask } from '../../application/use-cases/MoveTask.js'
import { assertNoPendingConfirm } from '../../application/internal/support.js'
import { renderSmart } from '../shared.js'

const summarize = (v: unknown): string => {
  const o = (v ?? {}) as Record<string, unknown>
  return '任务推进：' + String(o['task_id'] ?? '') + ' ' + String(o['from'] ?? '?') + ' → ' + String(o['to'] ?? '?')
}

export function defineTaskMoveTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_move',
    description: '用于：推进任务状态（todo → in_progress → integrating → testing → in_review → done）。非法转移与人工门越权（取消/复活/重开 done 卡）代码级拒绝；任务必须属于本窗口绑定的需求。',
    parameters: {
      task_id: { type: 'string', description: '任务 id（t-xxxxxx）' },
      to: { type: 'string', description: '目标状态（todo/in_progress/integrating/testing/in_review/done/canceled）' },
      reason: { type: 'string', description: '理由（进台账留痕）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          from: { type: 'string' },
          to: { type: 'string' },
          status: { type: 'string' },
        },
      },
      render: renderSmart(summarize),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    async execute(args: unknown, exec: unknown): Promise<Record<string, unknown>> {
      assertNoPendingConfirm(deps, deps.session.windowKey(exec))
      return await executeMoveTask(deps, args, exec) as Record<string, unknown>
    },
  } as any)
}
