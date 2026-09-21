/**
 * MoveTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/MoveTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeMoveRequirement } from '../../application/use-cases/MoveRequirement.js'
import { requirementTaskCardTriadFailure } from '../../application/internal/content-gate-triad.js'
import { openRequirementsFor } from '../../application/internal/window.js'
import { fmt } from '../../domain/text/fmt.js'
import { reject, agentIdFromExec } from '../../application/internal/support.js'
import { MOVE_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { moveSummary } from '../render-summaries.js'
import { ALL_REQ_STATUSES } from '../../shared/protocol.js'

export function defineMoveTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_move',
    description: MOVE_PROMPT,
    parameters: {
      to: {
        type: 'string',
        description: '目标状态：draft / brainstorming / design / decomposing / implementing / accepting / done / archived / canceled',
        required: true,
        enum: [...ALL_REQ_STATUSES],
      },
      requirement_id: {
        type: 'string',
        description: '需求 id（REQ-xxxxxx）；不传则默认本窗口绑定的那条 open 需求',
      },
      reason: {
        type: 'string',
        description: '推进理由（≤500 字符，写入需求评论供复盘）',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          from: { type: 'string', description: '推进前状态' },
          to: { type: 'string', description: '推进后状态' },
          doc_sync_pending: {
            type: 'array',
            description: '待同步的下游文档（重交下游产物后销标）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                source: { type: 'string' },
                downstream: { type: 'array', items: { type: 'string' } },
              },
            },
          },
          doc_sync_warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderSmart(moveSummary),
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => {
      // ── 三要素门禁（REQ-640a55 t-fb5e66 / FR-1）：离开拆分态之前，卡必须让人读得懂 ─────
      // 与 TaskMoveTool 同款薄壳：读卡是异步的，而改台账在 executeMoveRequirement 的同步回调里，
      // 故必须在此先算。状态判定与取数都在 application 层；壳只负责调用与拒绝。
      const a = (args ?? {}) as Record<string, unknown>
      const snap = deps.repo.snapshot()
      const bound = openRequirementsFor(snap, agentIdFromExec(deps, exec))
      const explicitId = typeof a.requirement_id === 'string' ? a.requirement_id : ''
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      // 没有绑定需求时不判——让用例照常给出它自己的拒绝文案（REQBOARD_NO_BOUND_REQ / NOT_BOUND）。
      const gap = target === undefined ? undefined : await requirementTaskCardTriadFailure(deps.docs, {
        requirementId: target.id,
        to: typeof a.to === 'string' ? a.to : '',
        tasks: snap.tasks,
      })
      if (gap !== undefined) {
        reject(
          fmt('reqboard_move 未执行：以下任务卡缺业务三要素（在做什么 / 解决什么问题 / 得到什么结果）——{gap}。请补齐卡上三节后再进入实施（code=task_card_incomplete）', { gap }),
          'task_card_incomplete',
        )
      }
      return executeMoveRequirement(deps, args, exec)
    },
  } as any)
}
