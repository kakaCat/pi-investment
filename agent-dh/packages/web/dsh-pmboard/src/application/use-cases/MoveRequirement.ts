/**
 * MoveRequirement 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineMoveTool / reqboard_move 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/MoveRequirement
 */
import type { UseCaseDeps } from '../ports.js'
import {
  ARTIFACT_CONFIRM_GATES,
  canReqTransition,
  asReqStatus,
  assertReqTransition,
  HUMAN_ONLY_REQ_TRANSITIONS,
  normalizeText,
} from '../../shared/protocol.js'
import { captureSnapshot, transitionRequirement } from '../internal/token-usage.js'
import { docSyncPendingOf, docSyncSummary } from '../../domain/workflow/DocSyncSpec.js'
import { openRequirementsFor } from '../internal/window.js'
import { applyTaskRollup } from '../internal/rollup.js'
import { assertArtifactGates } from '../internal/artifact-gates.js'
import { checkDesignCompletenessGate } from '../internal/content-gate-wiring.js'
import { gateForTransition } from '../../domain/gate/GateCatalog.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
  gateQuestionCard,
} from '../internal/support.js'

export async function executeMoveRequirement(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { to?: unknown; requirement_id?: unknown; reason?: unknown }
      const to = asReqStatus(a.to)
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const reason = normalizeText(a.reason, 'reason', 500)

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) {
        reject('reqboard_move 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      }
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject(
          `reqboard_move 未执行：需求 ${explicitId} 不是本窗口绑定的进行中需求（只能推进自己的需求）`,
          'REQBOARD_NOT_BOUND_TO_WINDOW',
        )
      }

      const from = target.status
      // ── REQ-ff20ca t3：产物确认型人工门的判定，从"谁调用"改为"产物是否已确认" ──
      // 语义内核不变（仍须人确认），但确认来源不限：看板一键确认 或 会话经
      // ask_user_question 落章（reqboard_confirm_artifact）——后者此前无法让门开启。
      const gateKind = ARTIFACT_CONFIRM_GATES[`${from}>${to}`]
      const gateConfirmed = gateKind !== undefined
        && (target.artifacts ?? []).some(x => x.kind === gateKind && x.confirmedAt !== undefined)
      if (gateConfirmed && HUMAN_ONLY_REQ_TRANSITIONS.has(`${from}>${to}`)) {
        // 门已开启（确认动作已由人完成）：只校验转移合法性，不再受 human_gate 限制
        if (!canReqTransition(from, to)) {
          reject(`reqboard_move 未执行：需求状态不允许从 ${from} 转移到 ${to}`, 'REQBOARD_INVALID_TRANSITION')
        }
      } else {
        try {
          assertReqTransition(from, to, 'agent')
        } catch (err) {
          const code = (err as { code?: string }).code ?? 'invalid_transition'
          if (code === 'human_gate') {
            const need = gateKind !== undefined ? `（kind=${gateKind}）` : ''
            reject(
              `reqboard_move 未执行：${from} → ${to} 需要人确认产物${need}。`
              + '首选：调 reqboard_ask_confirm 弹框请人确认（肯定答复自动落章+推进）；'
              + '兜底：用户在项目看板一键确认。'
              + '（取消/验收通过/归档类决定仍只能由人操作）'
              + gateQuestionCard(gateKind, from, to),
              'REQBOARD_HUMAN_GATE',
            )
          }
          reject(`reqboard_move 未执行：${(err as Error).message}`, code)
        }
      }
      // ── 产物闸门（存在 + 已确认）：agent 侧此前缺失，本次补齐（与看板 API 同源）──
      const gateFailure = assertArtifactGates(target, from, to)
      if (gateFailure !== undefined) {
        const hint = gateFailure.code === 'artifact_not_confirmed'
          ? '；首选调 reqboard_ask_confirm 弹框请人确认（自动落章+推进），兜底用户看板一键确认'
            + gateQuestionCard(gateFailure.kind, from, to)
          : ''
        reject(
          `reqboard_move 未执行：${gateFailure.message}${hint}`,
          gateFailure.code === 'artifact_not_confirmed' ? 'REQBOARD_ARTIFACT_NOT_CONFIRMED' : 'REQBOARD_MISSING_ARTIFACT',
        )
      }

      // ── REQ-2d1c74 FR-2：G2 文档集完整性闸门（design→decomposing 四条转移路径之一）──
      if (gateForTransition(from, to)?.id === 'G2') {
        const completeness = await checkDesignCompletenessGate(deps.docs, target)
        if (completeness !== undefined) {
          reject('reqboard_move 未执行：' + completeness.message, completeness.code)
        }
      }

      const result = await deps.repo.mutate('requirement-moved', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        // 与外部同款判定（并发下 req.status 可能与外部快照不同）
        const innerKey = `${req.status}>${to}`
        const innerKind = ARTIFACT_CONFIRM_GATES[innerKey]
        const innerConfirmed = innerKind !== undefined
          && (req.artifacts ?? []).some(x => x.kind === innerKind && x.confirmedAt !== undefined)
        if (innerConfirmed && HUMAN_ONLY_REQ_TRANSITIONS.has(innerKey)) {
          if (!canReqTransition(req.status, to)) {
            throw Object.assign(new Error(`需求状态不允许从 ${req.status} 转移到 ${to}`), { code: 'invalid_transition' })
          }
        } else {
          assertReqTransition(req.status, to, 'agent')
        }
        // REQ-b545fe t2：使用唯一迁移助手（结算离开节点+迁移状态+记录事件带快照）
        transitionRequirement(req, to, {
          at: deps.clock.now(),
          actor: { kind: 'agent', sessionId: windowKey },
          reason: reason || undefined,
          snap: captureSnapshot(deps, windowKey),
        })
        req.comments.push({
          id: deps.ids.comment(),
          body: `[窗口推进] ${from} → ${to}${reason ? `：${reason}` : ''}（窗口 ${windowKey}）`,
          createdAt: deps.clock.now(),
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        // 推进到 implementing 时顺带重算（任务可能已全部完成）
        const advanced = applyTaskRollup(
          ledger,
          { now: deps.clock.now(), commentId: () => deps.ids.comment(), snapshot: () => captureSnapshot(deps, windowKey) },
          req.id,
        )
        return { requirements: [req, ...advanced] }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) {
        reject('reqboard_move 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      }
      // 文档待同步警告（REQ-2e9473 t19/W8）：未销标时推进给出可见提示
      const pendingReq = deps.repo.snapshot().requirements.find(r => r.id === changed.id)
      const pendingSync = docSyncPendingOf(pendingReq ?? {})
      return {
        success: true,
        requirement_id: changed.id,
        from,
        to: changed.status,
        ...(pendingSync.length > 0
          ? {
              doc_sync_pending: pendingSync,
              doc_sync_warning: docSyncSummary(pendingReq ?? {}) + '（重交下游文档后销标）',
            }
          : {}),
        note:
          changed.status === to
            ? `已推进：${from} → ${to}`
            : `已推进：${from} → ${changed.status}（派生规则顺带推进）`,
      }
    }
