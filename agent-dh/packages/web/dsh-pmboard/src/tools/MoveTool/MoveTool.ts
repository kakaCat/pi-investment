/**
 * MoveTool（工具名 reqboard_move）——agent 侧需求阶段推进（REQ-260927100007-b8ba FR-7）。
 * @module dsh-pmboard/tools/MoveTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeMoveRequirement } from '../../application/use-cases/MoveRequirement.js'
import { assertNoPendingConfirm } from '../../application/internal/support.js'
import { renderSmart } from '../shared.js'

const summarize = (v: unknown): string => {
  const o = (v ?? {}) as Record<string, unknown>
  return '需求推进：' + String(o['requirement_id'] ?? '') + ' ' + String(o['from'] ?? '?') + ' → ' + String(o['to'] ?? '?')
}

export function defineMoveTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_move',
    description: '用于：推进需求阶段状态（如 design → decomposing）。五道人工门 agent 一律不可越过（代码级 human_gate）；产物未确认、或计划有卡而台账 0 卡时拒绝并给修复指引。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      to: { type: 'string', description: '目标状态（draft/brainstorming/design/decomposing/implementing/accepting/archived/canceled/done）' },
      reason: { type: 'string', description: '推进理由（进台账留痕）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
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
      return await executeMoveRequirement(deps, args, exec) as Record<string, unknown>
    },
  } as any)
}
