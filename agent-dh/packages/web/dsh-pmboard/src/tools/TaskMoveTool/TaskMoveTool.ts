/**
 * TaskMoveTool 工具壳（REQ-47939a t8）——三段式薄壳：prompt（prompt.ts）+ 元数据/入参/输出（本文件）
 * + execute 委托 application 用例。**不含任何领域判定**（状态判断只在 domain）。
 *
 * 返回体与拒绝条件与搬迁前的 host/agent-tools.ts 逐一对应（零行为变更）。
 *
 * @module dsh-pmboard/tools/TaskMoveTool
 */
import { defineTool, type ToolRunContext } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeMoveTask } from '../../application/use-cases/MoveTask.js'
import { amendTaskAcceptanceIfRequested } from '../../application/use-cases/AmendTaskAcceptance.js'
import { syncRequirementMarks } from '../../application/use-cases/SyncRequirementMarks.js'
import { doneEvidenceAnchorFailure } from '../../application/internal/content-gate-wiring.js'
import { taskCardTriadFailure } from '../../application/internal/content-gate-triad.js'
import { openRequirementsFor } from '../../application/internal/window.js'
import { fmt } from '../../domain/text/fmt.js'
import { reject, agentIdFromExec } from '../../application/internal/support.js'
import { TASK_MOVE_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { taskMoveSummary } from '../render-summaries.js'
import { ALL_TASK_STATUSES } from '../../shared/protocol.js'

/**
 * 卡的状态变了 → 需求文档同步一次逐条接收状态。找不到卡/需求 → 不动（不是错误）。
 * 幂等由用例保证：内容未变不写盘；写盘异常在此吞掉并返回空（调用方无需区分）。
 */
async function syncMarksAfterMove(deps: UseCaseDeps, taskId: string): Promise<Record<string, unknown>> {
  const latest = deps.repo.snapshot()
  const task = latest.tasks.find(t => t.id === taskId)
  if (task === undefined) return {}
  const req = latest.requirements.find(r => r.id === task.requirementId)
  if (req === undefined) return {}
  try {
    const r = await syncRequirementMarks(deps, req, latest.tasks)
    return r.synced ? { marks_synced: true } : {}
  } catch {
    return {}
  }
}

export function defineTaskMoveTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_move',
    description: TASK_MOVE_PROMPT,
    parameters: {
      task_id: { type: 'string', description: '任务 id（t-xxxxxx）', required: true },
      to: {
        type: 'string',
        description: '目标状态：todo / in_progress / integrating / testing / in_review / done / canceled',
        required: true,
        enum: [...ALL_TASK_STATUSES],
      },
      reason: { type: 'string', description: '推进理由（≤500 字符；写入任务留痕）' },
      acceptance: {
        type: 'string',
        description: '可选：修订本卡的验收标准（REQ-d3e61a T-9 修订通道）。开工读到卡、发现"怎么验"不可操作时先改卡再干活；修订文本仍须可证伪（空话/无锚点会被拒）',
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          requirement_id: { type: 'string' },
          from: { type: 'string' },
          to: { type: 'string' },
          requirement_status: { type: 'string' },
          task_card: {
            type: 'object',
            additionalProperties: false,
            description: '开工说明书：task_move→in_progress 时返回任务卡全文',
            properties: {
              title: { type: 'string' },
              description: { type: 'string' },
              acceptance: { type: 'string' },
              implementation: { type: 'string' },
              context: { type: 'string' },
              depends_on: { type: 'array', items: { type: 'string' } },
              doc_path: { type: 'string' },
            },
          },
          blockers: {
            type: 'array',
            description: '未完成任务清单（需求未进验收的原因）',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
              },
            },
          },
          warning: { type: 'string' },
          note: { type: 'string' },
          acceptance_amended: {
            type: 'string',
            description: '本次一并修订后的验收标准（仅当传了 acceptance 时返回）',
          },
          marks_synced: {
            type: 'boolean',
            description: '本次是否把逐条接收状态写回了需求文档（内容未变 → 不返回该键）',
          },
        },
      },
      render: renderSmart(taskMoveSummary),
    },
    timeoutMs: LIMITS.timeoutReadMs,
    execute: async (args: unknown, exec: ToolRunContext) => {
      // 可选修订（T-9 通道）：先改卡再推进——拒绝时不会产生任何状态副作用。
      const amended = await amendTaskAcceptanceIfRequested(deps, args, exec)

      // ── 结单证据锚定（REQ-d3e61a T-6 / FR-4）：done 之前校验证据可定位 ──────────────
      // 走薄壳而不是 support.ts 的 assertDoneEvidence——后者正被另一窗口占用。
      // 读文件是异步的，而真正改台账在 executeMoveTask 的同步回调里，故必须在此先算。
      // 状态判定与取数都在 application 层（工具壳不许出现状态字面量）；壳只负责调用与拒绝。
      const a = (args ?? {}) as Record<string, unknown>
      const snap = deps.repo.snapshot()
      const gap = await doneEvidenceAnchorFailure(deps.docs, {
        taskId: typeof a.task_id === 'string' ? a.task_id : '',
        to: typeof a.to === 'string' ? a.to : '',
        tasks: snap.tasks,
        boundRequirementIds: openRequirementsFor(snap, agentIdFromExec(deps, exec)).map(r => r.id),
      })
      if (gap !== undefined) {
        reject(fmt('reqboard_task_move 未执行：{gap}。请用 reqboard_task_report 补可定位的证据后再结单', { gap }), 'REQBOARD_NO_EVIDENCE')
      }

      // ── 三要素门禁（REQ-640a55 t-fb5e66 / FR-1）：结单前再核一次，防卡在拆分后被改坏 ──
      const triadGap = await taskCardTriadFailure(deps.docs, {
        taskId: typeof a.task_id === 'string' ? a.task_id : '',
        to: typeof a.to === 'string' ? a.to : '',
        tasks: snap.tasks,
        boundRequirementIds: openRequirementsFor(snap, agentIdFromExec(deps, exec)).map(r => r.id),
      })
      if (triadGap !== undefined) {
        reject(
          fmt('reqboard_task_move 未执行：本卡缺业务三要素（在做什么 / 解决什么问题 / 得到什么结果）——{gap}。请补齐卡上三节后再结单（code=task_card_incomplete）', { gap: triadGap }),
          'task_card_incomplete',
        )
      }
      const result = (await executeMoveTask(deps, args, exec)) as Record<string, unknown>

      // ── 需求文档同步逐条接收状态（REQ-d3e61a T-5 / FR-3「随卡的生命周期自动更新」）──────
      // 取消一张卡的交付 → 同一次调用里需求文档对应条回落为「🔴 未被接收」。
      // 回写失败只降级不阻断：文档是留痕面，不为它回滚已经落库的推进。
      const marks = await syncMarksAfterMove(deps, typeof a.task_id === 'string' ? a.task_id : '')
      const withAmend = amended === undefined ? result : { ...result, acceptance_amended: amended }
      return { ...withAmend, ...marks }
    },
  } as any)
}
