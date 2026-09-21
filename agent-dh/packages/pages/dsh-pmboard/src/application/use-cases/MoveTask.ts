/**
 * MoveTask 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineTaskMoveTool / reqboard_task_move 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/MoveTask
 */
import type { UseCaseDeps } from '../ports.js'
import {
  ALL_TASK_STATUSES,
  assertTaskTransition,
  normalizeText,
  recordStatus,
  taskRoleIn,
  type TaskRecord,
} from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'
import { LIMITS } from '../../domain/limits.js'
import { expandSubtasks } from '../internal/lazy-expand.js'
import { appendRevision } from '../internal/failure-handling.js'
import { openRequirementsFor } from '../internal/window.js'
import { applyTaskRollup } from '../internal/rollup.js'
import { beginExecutionToken, captureSnapshot, endExecutionToken } from '../internal/token-usage.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
  assertDoneEvidence,
  rollupBlockersOf,
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
      // 角色决定转移表：子卡/父卡收紧三态；存量卡沿用五段（REQ-4842fe t6）。
      const role = taskRoleIn(snapshot.tasks, task)
      try {
        assertTaskTransition(from, to as TaskRecord['status'], 'agent', role)
      } catch (err) {
        const code = (err as { code?: string }).code ?? 'invalid_transition'
        if (code === 'human_gate') {
          reject('reqboard_task_move 未执行：' + from + ' → ' + to + ' 是人工闸门（仅人可操作）', 'REQBOARD_HUMAN_GATE')
        }
        reject('reqboard_task_move 未执行：' + ((err as Error).message ?? String(err)), code)
      }
      const nowTs = deps.clock.now()
      let createdSubtasks: TaskRecord[] = []
      const result = await deps.repo.mutate('task-moved', (ledger) => {
        const t = ledger.tasks.find(x => x.id === taskId)
        if (t === undefined) return undefined
        assertTaskTransition(t.status, to as TaskRecord['status'], 'agent', taskRoleIn(ledger.tasks, t))
        // done 凭证门（REQ-2e9473 t06）：转移合法还不够，完工要有凭证
        if (to === 'done') assertDoneEvidence(deps, windowKey, t, ledger)
        t.status = to as TaskRecord['status']
        t.version += 1
        t.updatedAt = nowTs
        t.updatedBy = { kind: 'agent', sessionId: windowKey }
        // REQ-a33899：任务执行开工/完工各记一次会话快照，消耗 = 两次快照之差（同会话才相减）。
        const snap = captureSnapshot(deps, windowKey)
        if (to === 'in_progress') {
          t.claimedBy = windowKey
          t.claimedAt = nowTs
          const execution = {
            id: deps.ids.execution(),
            sessionId: windowKey,
            trigger: 'manual' as const,
            startedAt: nowTs,
            outcome: 'running' as const,
          }
          beginExecutionToken(execution, snap)
          t.executions.push(execution)
        } else {
          for (const e of t.executions) {
            if (e.outcome === 'running') {
              e.endedAt = nowTs
              e.outcome = to === 'canceled' || to === 'todo' ? 'cancelled' : 'succeeded'
              endExecutionToken(e, snap)
            }
          }
        }
        // REQ-4842fe t6/FR-3：父卡开工**同事务**懒展开子卡链（幂等：已有子卡即跳过）。
        // 只在需求开启自动链（autoRun=true）时展开——手动/存量流程保持既有五段状态机，
        // 这正是 design/data-model §7「双模共存」的开关点（无子卡的卡 = legacy）。
        if (to === 'in_progress' && t.parentId === undefined) {
          const requirement = ledger.requirements.find(x => x.id === t.requirementId)
          if (requirement?.autoRun === true) {
            // REQ-4842fe t9/FR-9：同需求同时 in_progress 父卡 ≤ 上限（拒绝发生在开工动作）。
            const active = ledger.tasks.filter(x => x.requirementId === t.requirementId && x.parentId === undefined && x.status === 'in_progress' && x.id !== t.id).length
            if (active >= LIMITS.advanceMaxParallelParents) {
              reject(
                fmt('reqboard_task_move 未执行：同需求同时开工的父卡已达上限 {max}（已在跑：{ids}）。先完成已在跑的父卡', {
                  max: LIMITS.advanceMaxParallelParents,
                  ids: ledger.tasks.filter(x => x.requirementId === t.requirementId && x.parentId === undefined && x.status === 'in_progress' && x.id !== t.id).map(x => x.id).join('、'),
                }),
                'REQBOARD_PARENT_LIMIT',
              )
            }
            createdSubtasks = expandSubtasks(ledger, t, requirement, nowTs, deps.ids)
          }
          if (createdSubtasks.length > 0) {
            t.comments.push({
              id: deps.ids.comment(),
              body: fmt('[懒展开] 落子卡 {n} 张：{kinds}', {
                n: createdSubtasks.length,
                kinds: createdSubtasks.map(x => String(x.stageKind ?? '')).join(' → '),
              }),
              createdAt: nowTs,
              createdBy: { kind: 'agent', sessionId: windowKey },
            })
          }
        }
        // REQ-4842fe t8/FR-15：done 卡被人工重开 → 写 revisions(reopen)（自动链不产生该转移）。
        if (from === 'done' && to === 'in_progress') {
          appendRevision(t, nowTs, 'reopen', reason.length > 0 ? reason : '人工重开受影响的完成卡', ['status: done→in_progress'])
        }
        if (to === 'todo' || to === 'done' || to === 'canceled') {
          delete t.claimedBy
          delete t.claimedAt
        }
        recordStatus(t, to, nowTs, { kind: 'agent', sessionId: windowKey }, reason || undefined, snap)
        if (reason.length > 0) {
          t.comments.push({
            id: deps.ids.comment(),
            body: '[状态] → ' + to + '：' + reason + '（窗口 ' + windowKey + '）',
            createdAt: nowTs,
            createdBy: { kind: 'agent', sessionId: windowKey },
          })
        }
        const advanced = applyTaskRollup(
          ledger,
          { now: nowTs, commentId: () => deps.ids.comment(), snapshot: () => captureSnapshot(deps, windowKey) },
          t.requirementId,
        )
        return { tasks: [t, ...createdSubtasks], requirements: advanced }
      })
      const changed = (result.changed.tasks ?? [])[0]
      if (changed === undefined) reject('reqboard_task_move 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // rollup 可能未推进需求（如 decomposing 停等人工确认门）——需求状态从台账现读，
      // 不只依赖 changed.requirements（仅含被推进的需求）
      const ledgerAfter = deps.repo.snapshot()
      const reqAfter = ledgerAfter.requirements.find(r => r.id === changed.requirementId)
      // rollup 阻塞显式化（REQ-2e9473 t02）：需求停在 implementing 且有未完成任务 → 显式列出
      const blockers = reqAfter === undefined ? undefined : rollupBlockersOf(ledgerAfter, reqAfter.id, reqAfter.status)
      // 开工说明书送达（REQ-2e9473 t04/W5）：开工即拿到完整任务卡，不凭记忆回读设计文档——
      // REQ-6f39b5 事故 F：薄卡 + 不回读 = 8 处偏离设计。
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
