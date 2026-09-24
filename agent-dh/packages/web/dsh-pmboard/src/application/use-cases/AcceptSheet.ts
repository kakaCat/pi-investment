/**
 * AcceptSheet 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineAcceptSheetTool / reqboard_accept_sheet 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/AcceptSheet
 */
import { deliverWorktreeNotice } from '../internal/worktree-notice.js'
import type { UseCaseDeps } from '../ports.js'
import {
  normalizeText,
} from '../../shared/protocol.js'
import { ACCEPT_ITEM_OPTIONS, FINAL_DECLINE_LABEL, FINAL_PASS_LABEL } from '../../domain/text/labels.js'
import { clip, fmt } from '../../domain/text/fmt.js'
import { LIMITS } from '../../domain/limits.js'
import { openRequirementsFor } from '../internal/window.js'
import { applyVerdicts } from '../internal/verdicts.js'
import { captureSnapshot, transitionRequirement } from '../internal/token-usage.js'
import { rewriteVerificationDoc } from '../internal/verification-doc-writer.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
} from '../internal/support.js'

export async function acceptSheet(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as { requirement_id?: unknown; batch_size?: unknown; version?: unknown }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const batchSize = Math.min(Math.max(Number(a.batch_size ?? LIMITS.sheetBatchDefault) || LIMITS.sheetBatchDefault, 1), LIMITS.sheetBatchMax)

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_accept_sheet 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const targetReq = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (targetReq === undefined) {
        reject('reqboard_accept_sheet 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }
      const sheet = targetReq.verification?.sheet
      if (sheet === undefined) reject('reqboard_accept_sheet 未执行：该需求还没有验收单（先 reqboard_verify_submit）', 'REQBOARD_NO_SHEET')
      if (a.version !== undefined && Number(a.version) !== sheet.version) {
        reject('reqboard_accept_sheet 未执行：验收单版本不匹配（当前 v' + sheet.version + '）', 'REQBOARD_VERSION_MISMATCH')
      }

      /**
       * 全部通过 → 直接弹「验收通过并归档」确认（REQ-2e9473 W6 闭环，用户指出）：
       * 逐项全过后不再要求人去点看板——同一次会话里接着弹最终确认，确认即归档。
       */
      const finalizeIfAllPassed = async (passed: number, failed: number): Promise<Record<string, unknown> | undefined> => {
        if (failed > 0) return undefined
        const cur = deps.repo.snapshot().requirements.find(r => r.id === targetReq.id)
        if (cur === undefined || cur.status !== 'accepting') return undefined
        const curSheet = cur.verification?.sheet
        // REQ-308b9a FR-9 / AC-9.3：放行判据 = 无 pending（not_verifiable 算已裁决）。
        if (curSheet !== undefined && curSheet.items.some(i => i.status === 'pending')) return undefined
        if (!deps.questions.available()) {
          return { success: false, fallback: 'board', note: '全部 ' + passed + ' 项通过，但弹框通道不可用：请在看板点「验收通过」归档' }
        }
        const FINAL_YES = FINAL_PASS_LABEL
        let ans: { answers?: { id?: string; selected?: string[] }[] } | undefined
        try {
          ans = { answers: [...await deps.questions.ask([{
              id: 'final-pass',
              header: '验收通过',
              question: '全部 ' + passed + ' 项验收通过——是否验收通过并归档？',
              options: [
                { label: FINAL_YES, description: '需求进入归档态，随后补归档材料' },
                { label: FINAL_DECLINE_LABEL, description: '保持验收态，稍后再定' },
              ],
            }], {
              ...(exec.agent !== undefined ? { agent: exec.agent } : {}),
              signal: (exec as { signal?: unknown }).signal,
              // 闸门声明（REQ-e3b6a0 t7）：验收最终归档确认属 G4
              gate: 'G4',
            })] }
        } catch (err) {
          const code = (err as { code?: string }).code ?? ''
          if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
            return { success: false, fallback: 'board', note: '全部通过，但当前调用方无弹框权限：请在看板点「验收通过」' }
          }
          return { success: false, passed, failed: 0, note: '用户未作答最终确认：需求保持验收态（可重新调用本工具或看板确认）' }
        }
        if ((ans?.answers?.[0]?.selected?.[0] ?? '') !== FINAL_YES) {
          return { success: true, recorded: 0, pending: 0, passed, failed: 0, note: '用户选择暂不归档：需求保持验收态' }
        }
        const nowTs2 = deps.clock.now()
        const moved = await deps.repo.mutate('requirement-moved', (ledger) => {
          const r = ledger.requirements.find(x => x.id === targetReq.id)
          if (r === undefined) return undefined
          if (r.status !== 'accepting') {
            throw Object.assign(new Error('需求当前处于 ' + r.status + '，不在验收态'), { code: 'bad_status' })
          }
          const v = r.verification
          if (v !== undefined) {
            v.reviewedAt = nowTs2
            v.reviewedBy = { kind: 'human', sessionId: windowKey }
            v.decision = 'pass'
          }
          // REQ-b545fe t5：使用唯一迁移助手
          transitionRequirement(r, 'archived', {
            at: nowTs2,
            actor: { kind: 'human', sessionId: windowKey },
            reason: '验收通过（弹框逐项全通过 → 会话确认）',
            snap: captureSnapshot(deps, windowKey),
          })
          r.comments.push({
            id: deps.ids.comment(),
            body: '[验收] 人工审核通过（弹框确认，' + passed + ' 项全通过）→ 自动归档',
            createdAt: nowTs2,
            createdBy: { kind: 'human', sessionId: windowKey },
          })
          return { requirements: [r] }
        }).catch((err: unknown) => {
          reject('reqboard_accept_sheet 归档失败：' + ((err as Error).message ?? String(err)), (err as { code?: string }).code ?? 'REQBOARD_STORE_INCONSISTENT')
        })
        const movedReq = (moved.changed.requirements ?? [])[0]
        // REQ-260923222557-d3b0 FR-3：归档 → worktree 合并清理提示（事件型注入，失败不阻断）
        if (movedReq !== undefined) {
          deliverWorktreeNotice(deps, windowKey, 'archived', { requirementId: movedReq.id })
        }
        return {
          success: true, recorded: 0, pending: 0, passed, failed: 0,
          archived: true, status: movedReq?.status ?? 'archived',
          note: '✅ 验收通过 → 已归档：请调 reqboard_archive_submit 补归档材料（目录/清单/合并去向/索引）',
        }
      }

      const pendingItems = sheet.items.filter(i => i.status === 'pending').slice(0, batchSize)
      if (pendingItems.length === 0) {
        const passedN = sheet.items.filter(i => i.status === 'passed').length
        const failedN = sheet.items.filter(i => i.status === 'failed').length
        const fin = await finalizeIfAllPassed(passedN, failedN)
        if (fin !== undefined) return fin as never
        return {
          success: true, requirement_id: targetReq.id, sheet_version: sheet.version,
          recorded: 0, pending: 0, passed: passedN, failed: failedN,
          note: failedN > 0
            ? '有 ' + failedN + ' 项不通过：已自动回退实施并生成返工卡（REQ-308b9a FR-8）'
            : '全部已裁决（含不可验收项）→ 可点「验收通过」归档',
        } as never
      }

      if (!deps.questions.available()) {
        return {
          success: false, fallback: 'board',
          note: '弹框通道不可用（userQuestions 服务缺失）：请用户到项目看板验收面板逐项勾选（看板通道等效）',
        } as never
      }
      // 文案单点（REQ-47939a 返工）：与 client 徽章同源，不再各写一份
      const OPT_PASS = ACCEPT_ITEM_OPTIONS.pass
      const OPT_FIX = ACCEPT_ITEM_OPTIONS.fix
      const OPT_OTHER = ACCEPT_ITEM_OPTIONS.other
      let answers: { id?: string; selected?: string[]; custom?: string }[] = []
      try {
        answers = [...await deps.questions.ask(pendingItems.map(it => ({
            id: it.id,
            header: it.source.kind === 'requirement'
              ? '需求级验收'
              : fmt('验收项 {taskId}', { taskId: it.source.taskId }),
            // 题干长度纪律（LIMITS.popupCriterionMax/EvidenceMax）：宁可少给证据，也不能把选项挤出可视区
            question: clip(it.criterion, LIMITS.popupCriterionMax) + (it.evidence.length > 0
              ? fmt('\n（证据：{evidence}）', { evidence: clip(it.evidence[0] ?? '', LIMITS.popupEvidenceMax) })
              : ''),
            options: [
              { label: OPT_PASS, description: '该验收项通过' },
              { label: OPT_FIX, description: '需修改——请在自定义输入写意见' },
              { label: OPT_OTHER, description: '其他结论——请在自定义输入说明' },
            ],
          })), {
          ...(exec.agent !== undefined ? { agent: exec.agent } : {}),
          signal: (exec as { signal?: unknown }).signal,
          // 闸门声明（REQ-e3b6a0 t7）：验收逐项裁决属 G4
          gate: 'G4',
        })]
      } catch (err) {
        const code = (err as { code?: string }).code ?? ''
        if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
          return { success: false, fallback: 'board', note: '当前调用方无弹框权限：请用户到项目看板验收面板逐项勾选' } as never
        }
        return { success: false, note: '用户未作答（取消/暂离）：未记录任何裁决，稍后可重新调用' } as never
      }

      const byId = new Map(answers.map(ans => [ans.id ?? '', ans]))
      const verdicts: { itemId: string; status: 'passed' | 'failed'; opinion?: string }[] = []
      for (const it of pendingItems) {
        const ans = byId.get(it.id)
        if (ans === undefined) continue // 未作答 → 保持 pending（挂起点）
        const picked = ans.selected?.[0] ?? ''
        const custom = (ans.custom ?? '').trim()
        if (picked === OPT_PASS) {
          verdicts.push({ itemId: it.id, status: 'passed' })
        } else {
          const opinion = custom.length > 0 ? custom : (picked.replace(/^[^\w\u4e00-\u9fa5]+/, '') || '需修改')
          verdicts.push({ itemId: it.id, status: 'failed', opinion })
        }
      }
      if (verdicts.length === 0) {
        return { success: false, note: '用户未选择任何项：未记录裁决（挂起）' } as never
      }

      const nowTs = deps.clock.now()
      const result = await deps.repo.mutate('requirement-updated', (ledger) => {
        try {
          const applied = applyVerdicts(
            ledger, targetReq.id, sheet.version, verdicts,
            { kind: 'human', sessionId: windowKey }, nowTs, () => deps.ids.comment(),
            captureSnapshot(deps, windowKey), // REQ-b545fe t5: 传快照供打回路径结算
          )
          return { requirements: [applied.requirement], tasks: applied.reworkTasks }
        } catch (err) {
          reject('reqboard_accept_sheet 记录失败：' + ((err as Error).message ?? String(err)), (err as { code?: string }).code ?? 'REQBOARD_INVALID_INPUT')
        }
      })
      const changed = (result.changed.requirements ?? [])[0]
      if (changed === undefined) reject('reqboard_accept_sheet 写入失败：台账状态异常', 'REQBOARD_STORE_INCONSISTENT')
      // REQ-308b9a FR-7 / AC-7.7：裁决落库后回填 verification.md 的验收结果表。
      await rewriteVerificationDoc({ repo: deps.repo, docs: deps.docs }, targetReq.id)
      const after = deps.repo.snapshot().requirements.find(r => r.id === targetReq.id)
      const s = after?.verification?.sheet
      const pending = s?.items.filter(i => i.status === 'pending').length ?? 0
      const failed = s?.items.filter(i => i.status === 'failed').length ?? 0
      const reworkIds = (result.changed.tasks ?? []).map(t => t.id)
      // 本批记录后若已全过 → 直接接着弹最终「验收通过并归档」确认（闭环）
      if (pending === 0 && failed === 0 && reworkIds.length === 0) {
        const fin2 = await finalizeIfAllPassed(s?.items.filter(i => i.status === 'passed').length ?? 0, 0)
        if (fin2 !== undefined) return fin2 as never
      }
      return {
        success: true,
        requirement_id: targetReq.id,
        sheet_version: sheet.version,
        recorded: verdicts.length,
        pending,
        passed: s?.items.filter(i => i.status === 'passed').length ?? 0,
        failed,
        // REQ-308b9a FR-8：裁决含 failed 时返回真实生成的返工卡 id 列表。
        rework_tasks: reworkIds,
        note: failed > 0
          ? '有 ' + failed + ' 项不通过：已自动回退实施并生成 ' + reworkIds.length + ' 张返工卡（REQ-308b9a FR-8）'
          : (pending > 0
              ? '本批已记录（剩 ' + pending + ' 项待验）：再次调 reqboard_accept_sheet 从断点继续'
              : '全部已裁决 → 请点「验收通过」归档（人工门）'),
      } as never
    }