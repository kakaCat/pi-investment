/**
 * MoveTask 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineTaskMoveTool / reqboard_task_move 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/MoveTask
 */
import type { UseCaseDeps } from '../ports.js'
import {
  ALL_ARTIFACT_KINDS, ALL_REQ_CATEGORIES, ARTIFACT_CONFIRM_GATES, canReqTransition, ARCHIVE_DOC_RULES,
  assertArchiveMaterials, ALL_REQ_STATUSES, ALL_TASK_PHASES, ALL_TASK_SIDES, ALL_TASK_STATUSES,
  asReqCategory, asReqStatus, asScope, assertDagAcyclic, assertReqTransition, assertTaskTransition,
  HUMAN_ONLY_REQ_TRANSITIONS, agentNextActions, newCommentId, newExecutionId, newRequirementId, newTaskId,
  normalizePlanTasks, normalizeText, normalizeTitle, planApproved, recordStatus,
  type PlanTask, type VerificationSheet, type TaskRecord, type ReqboardLedger,
  type RequirementCategory, type RequirementRecord, type RequirementStatus, type StageArtifact, type TriageRecord,
} from '../../shared/protocol.js'
import { buildSheet } from '../../domain/workflow/AcceptanceSheetSpec.js'
import { checkDoneEvidence, findRecentAgentDoneTask } from '../../domain/workflow/DoneEvidenceSpec.js'
import { checkDecomposeIdempotency } from '../../domain/workflow/DecomposeSpec.js'
import { applyDocSync, clearDocSync, docSyncDownstream, docSyncPendingOf, docSyncSummary } from '../../domain/workflow/DocSyncSpec.js'
import { openRequirementsFor, pendingSuggestionFor } from '../internal/window.js'
import { applyTaskRollup } from '../internal/rollup.js'
import { registerArtifact, assertArtifactGates, artifactNotifyText } from '../internal/artifact-gates.js'
import { applyVerdicts } from '../internal/verdicts.js'
import {
  reject, agentIdFromExec, requireLiveDriver, requireDirectHuman, notifyArtifactRegistered,
  assertDoneEvidence, rollupBlockersOf, workspacePathCandidates, gateQuestionCard, findPending,
  createRequirementDirect, projectRequirement,
} from '../internal/support.js'

export async function executeMoveTask(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { task_id?: unknown; to?: unknown; reason?: unknown }
      const taskId = normalizeText(a.task_id, 'task_id', 64)
      const to = normalizeText(a.to, 'to', 32)
      const reason = normalizeText(a.reason, 'reason', 500)
      if (!(ALL_TASK_STATUSES as readonly string[]).includes(to)) {
        reject('reqboard_task_move 未执行：任务状态必须是 ' + ALL_TASK_STATUSES.join(', '), 'REQBOARD_INVALID_INPUT')
      }
      const snapshot = deps.repo.snapshot()
      const task = snapshot.tasks.find(t => t.id === taskId)
      if (task === undefined) reject('reqboard_task_move 未执行：任务 ' + taskId + ' 不存在', 'REQBOARD_TASK_NOT_FOUND')
      const bound = openRequirementsFor(snapshot, windowKey)
      if (!bound.some(r => r.id === task.requirementId)) {
        reject('reqboard_task_move 未执行：任务 ' + taskId + ' 不属于本窗口绑定的需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      const from = task.status
      try {
        assertTaskTransition(from, to as TaskRecord['status'], 'agent')
      } catch (err) {
        const code = (err as { code?: string }).code ?? 'invalid_transition'
        if (code === 'human_gate') {
          reject('reqboard_task_move 未执行：' + from + ' → ' + to + ' 是人工闸门（仅人可操作）', 'REQBOARD_HUMAN_GATE')
        }
        reject('reqboard_task_move 未执行：' + ((err as Error).message ?? String(err)), code)
      }
      const nowTs = deps.clock.now()
      const result = await deps.repo.mutate('task-moved', (ledger) => {
        const t = ledger.tasks.find(x => x.id === taskId)
        if (t === undefined) return undefined
        assertTaskTransition(t.status, to as TaskRecord['status'], 'agent')
        // done 凭证门（REQ-2e9473 t06）：转移合法还不够，完工要有凭证
        if (to === 'done') assertDoneEvidence(deps, windowKey, t, ledger)
        t.status = to as TaskRecord['status']
        t.version += 1
        t.updatedAt = nowTs
        t.updatedBy = { kind: 'agent', sessionId: windowKey }
        if (to === 'in_progress') {
          t.claimedBy = windowKey
          t.claimedAt = nowTs
          t.executions.push({
            id: deps.ids.execution(),
            sessionId: windowKey,
            trigger: 'manual',
            startedAt: nowTs,
            outcome: 'running',
          })
        } else {
          for (const e of t.executions) {
            if (e.outcome === 'running') {
              e.endedAt = nowTs
              e.outcome = to === 'canceled' || to === 'todo' ? 'cancelled' : 'succeeded'
            }
          }
        }
        if (to === 'todo' || to === 'done' || to === 'canceled') {
          delete t.claimedBy
          delete t.claimedAt
        }
        recordStatus(t, to, nowTs, { kind: 'agent', sessionId: windowKey }, reason || undefined)
        if (reason.length > 0) {
          t.comments.push({
            id: deps.ids.comment(),
            body: '[状态] → ' + to + '：' + reason + '（窗口 ' + windowKey + '）',
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
        }
        const advanced = applyTaskRollup(ledger, { now: nowTs, commentId: () => deps.ids.comment() }, t.requirementId)
        return { tasks: [t], requirements: advanced }
      })
      const changed = result.changed.tasks[0]
      if (changed === undefined) reject('reqboard_task_move 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // rollup 可能未推进需求（如 decomposing 停等人工确认门）——需求状态从台账现读，
      // 不只依赖 changed.requirements（仅含被推进的需求）
      const ledgerAfter = deps.repo.snapshot()
      const reqAfter = ledgerAfter.requirements.find(r => r.id === changed.requirementId)
      // rollup 阻塞显式化（REQ-2e9473 t02）：需求停在 implementing 且有未完成任务 → 显式列出
      const blockers = reqAfter === undefined ? undefined : rollupBlockersOf(ledgerAfter, reqAfter.id, reqAfter.status)
      // 开工说明书送达（REQ-2e9473 t04/W5）：开工即拿到完整任务卡，不凭记忆回读设计文档——
      // REQ-6f39b5 事故 F：薄卡 + 不回读 = 8 处偏离技术设计。
      const taskCard = to === 'in_progress'
        ? {
            title: changed.title,
            description: changed.description,
            acceptance: changed.acceptance,
            implementation: changed.implementation ?? '',
            context: changed.context,
            depends_on: [...changed.dependsOn],
            doc_path: 'docs/requirements/' + changed.requirementId + '/tasks/' + changed.id + '.md',
          }
        : undefined
      return {
        success: true,
        task_id: changed.id,
        requirement_id: changed.requirementId,
        from,
        to: changed.status,
        ...(taskCard !== undefined ? { task_card: taskCard } : {}),
        requirement_status: reqAfter?.status ?? '',
        ...(blockers !== undefined
          ? { blockers, warning: '需求未进验收：' + blockers.length + ' 个任务未完成（' + blockers.map(b => b.id).join('、') + '）' }
          : {}),
        note: changed.status === to ? '已推进：' + from + ' → ' + to : '已推进：' + from + ' → ' + changed.status,
      }
    }
