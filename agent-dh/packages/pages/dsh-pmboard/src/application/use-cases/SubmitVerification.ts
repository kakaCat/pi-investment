/**
 * SubmitVerification 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineVerifySubmitTool / reqboard_verify_submit 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/SubmitVerification
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

export async function submitVerification(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; summary?: unknown; evidence?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const summary = normalizeText(a.summary, 'summary', 2000)
      if (summary.length === 0) reject('reqboard_verify_submit 未执行：summary 不能为空', 'REQBOARD_INVALID_INPUT')
      if (!Array.isArray(a.evidence)) reject('reqboard_verify_submit 未执行：evidence 必须是数组', 'REQBOARD_INVALID_INPUT')
      const evidence = (a.evidence as unknown[])
        .map(e => normalizeText(e, 'evidence[]', 1000))
        .filter(e => e.length > 0)
        .slice(0, 20)
      if (evidence.length === 0) {
        reject('reqboard_verify_submit 未执行：至少要有一条可复核的证据（命令+输出摘要 / 报告路径 / 截图路径）', 'REQBOARD_INVALID_INPUT')
      }
      // evidence 存在性校验（REQ-2e9473 t12）：evidence 里引用的工作区文件路径必须真实存在，
      // 防"编造证据路径"（事故 E 变体：文档/产物路径不存在也算证据）。
      const citedPaths = workspacePathCandidates(evidence)
      const docs = deps.docs
      const missingPaths = citedPaths.filter(p => !docs.exists(p))
      if (missingPaths.length > 0) {
        reject(
          'reqboard_verify_submit 未执行：evidence 引用的文件不存在（疑似编造）：'
          + missingPaths.join('、') + '。请引用真实存在的产物/报告路径，或改用命令+输出摘要',
          'REQBOARD_EVIDENCE_MISSING',
        )
      }

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_verify_submit 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const target = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (target === undefined) {
        reject('reqboard_verify_submit 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      if (target.status !== 'implementing' && target.status !== 'accepting') {
        reject('reqboard_verify_submit 未执行：需求处于 ' + target.status + '，只有执行/验收阶段的交付才能提交验收', 'REQBOARD_BAD_STATUS')
      }

      const nowTs = deps.clock.now()
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === target.id)
        if (req === undefined) return undefined
        // ── 逐项验收单生成（REQ-2e9473 t13/W6；规则在 domain/workflow/AcceptanceSheetSpec.ts，t4）──
        // items = 每任务验收标准 + 需求级标准；返工时（上一版有未过项）只含未过项。
        const allTasks = ledger.tasks.filter(t => t.requirementId === req.id && t.status !== 'canceled')
        const prevSheet = req.verification?.sheet
        const built = buildSheet({
          sheetHistoryLength: req.verification?.sheetHistory?.length ?? 0,
          ...(prevSheet !== undefined ? { prevSheet } : {}),
          tasks: allTasks.map(t => ({ id: t.id, title: t.title, acceptance: t.acceptance })),
          evidence,
          generatedAt: nowTs,
          generatedBy: { kind: 'agent', sessionId: windowKey },
        })
        const sheet: VerificationSheet = built.sheet as VerificationSheet
        req.verification = {
          summary,
          evidence,
          submittedAt: nowTs,
          submittedBy: { kind: 'agent', sessionId: windowKey },
          sheet,
          sheetHistory: [
            ...(req.verification?.sheetHistory ?? []),
            ...(prevSheet !== undefined ? [prevSheet] : []),
          ],
        }
        req.comments.push({
          id: deps.ids.comment(),
          body: '[验收] 提交验收材料（待人工审核）：' + summary
            + '\n证据：\n' + evidence.map(e => '- ' + e).join('\n'),
          createdAt: nowTs,
          createdBy: { kind: 'agent', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'agent', sessionId: windowKey }
        // 任务全完成时顺带推进到验收态（人来了就有东西可审）
        const advanced = applyTaskRollup(ledger, { now: nowTs, commentId: () => deps.ids.comment() }, req.id)
        return { requirements: [req, ...advanced] }
      })
      const changed = result.changed.requirements[0]
      if (changed === undefined) reject('reqboard_verify_submit 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // ── 产物登记（REQ-31e11f t4）：verification 产物 ─────────────────────
      const verPath = 'docs/requirements/' + target.id + '/verification.md'
      if (!docs.exists(verPath)) {
        const verContent = [
          '# ' + target.id + ' 验收（verification）',
          '',
          '> 自动生成于 reqboard_verify_submit',
          '',
          '## 验收结论',
          summary,
          '',
          '## 证据清单',
          ...evidence.map(e => '- ' + e),
          '',
        ].join('\n')
        await docs.write(verPath, verContent)
      }
      await deps.repo.mutate('requirement-updated', (ledger) => {
        const r = ledger.requirements.find(x => x.id === changed.id)
        if (r === undefined) return undefined
        registerArtifact(r, {
          stage: 'accepting', kind: 'verification', path: verPath,
          registeredAt: nowTs, registeredBy: { kind: 'agent', sessionId: windowKey },
        })
        return { requirements: [r] }
      })
      const ledgerNow = deps.repo.snapshot()
      const tasks = ledgerNow.tasks.filter(t => t.requirementId === target.id && t.status !== 'canceled')
      const reqNow = ledgerNow.requirements.find(r => r.id === changed.id)
      // rollup 阻塞显式化（REQ-2e9473 t02）：有未完成任务时验收材料虽收，但需求进不了 accepting
      const blockers = reqNow === undefined ? undefined : rollupBlockersOf(ledgerNow, reqNow.id, reqNow.status)
      return {
        success: true,
        requirement_id: changed.id,
        status: reqNow?.status ?? changed.status,
        tasks_done: tasks.filter(t => t.status === 'done').length,
        tasks_total: tasks.length,
        sheet_version: reqNow?.verification?.sheet?.version ?? 0,
        sheet_items: reqNow?.verification?.sheet?.items.length ?? 0,
        ...(reqNow?.verification?.sheet?.reworkOnly === true ? { rework_only: true } : {}),
        ...(reqNow !== undefined && (reqNow.docSyncPending ?? []).length > 0
          ? { doc_sync_pending: reqNow.docSyncPending, doc_sync_warning: docSyncSummary(reqNow) }
          : {}),
        ...(blockers !== undefined
          ? {
              blockers,
              warning: '⚠️ 需求未进验收（rollup 阻塞）：' + blockers.length + ' 个任务未完成——'
                + blockers.map(b => b.id + ' ' + b.title + '（' + b.status + '）').join('；')
                + '。若为重复拆分产生的幽灵任务，请人工取消后重新提交',
            }
          : {}),
        note: blockers !== undefined
          ? '验收材料已提交，但需求因 ' + blockers.length + ' 个未完成任务停在 implementing——见 warning/blockers'
          : '验收材料已提交。下一步：调 reqboard_ask_confirm（target=artifact, kind=verification）弹框请人逐项审核（看板「验收通过/退回」同样是有效通道）',
      }
    }
