/**
 * Verdicts 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * REQ-a8d582 起本文件承载两处语义变更：
 *   - FR-2：逐项裁决**只记录**，不再自动打回实施、不再自动建返工任务；
 *   - FR-3/FR-4：验收通过不再要求"已交材料"，但不合规通过（有不合格项 / 无材料）必须显式覆盖并留痕。
 *
 * @module dsh-pmboard/http/routers/Verdicts
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  assertReqTransition,
  normalizeText,
  recordStatus,
  type VerificationItem,
} from '../../shared/protocol.js'
import {
  countFailedItems, countPassedItems, countPendingItems, isAccepting, isAcceptingStage,
  isDecidableItemStatus, isEveryItemPassed, isFailedItem, isVerifiableStage,
} from '../../domain/status/Predicates.js'
import { ACCEPTED_REQ_STATUS, REWORK_REQ_STATUS } from '../../domain/requirement/RequirementStatus.js'
import { materializeReworkFromSheet } from '../../application/internal/verdicts.js'
import type { RouterCtx } from './shared.js'

export function createVerdictsRouter(ctx: RouterCtx) {
  const { store, now, ids, ok, readBody, badInput, notFound } = ctx

  /**
   * 验收人工审核（仅人）：pass → archived（验收通过即归档），rework → implementing（必须写意见）。
   *
   * REQ-a8d582 FR-3/FR-4：按钮在验收态就可见（不再以"已交材料"为前置），所以"没有材料"也能点进来；
   * 它与"有不合格项"一样属于**不合规通过**——必须带 confirm_override（覆盖说明），否则拒绝。
   * 覆盖会写进台账 acceptanceOverride + 评论 + 状态事件，三处可查。
   */
  async function handleVerifyDecision(req: IncomingMessage, res: ServerResponse, pass: boolean): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const note = normalizeText(body.note, 'note', 1000)
    const confirmOverride = normalizeText(body.confirm_override, 'confirm_override', 1000)
    if (!pass && note.length === 0) badInput('退回返工必须写清意见（note）')
    const result = await store.mutate('requirement-moved', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound("需求 " + id)
      if (!isAccepting(r)) badInput("需求 " + id + " 当前处于 " + r.status + "，不在验收态（先提交验收）")
      
      // ── 强制跳过检查（二次确认覆盖）──
      // REQ-327bdf 需求：当传入 confirm_override 时，完全跳过验收材料检查，直接通过
      if (pass && confirmOverride.length > 0) {
        // 用户已二次确认，直接允许通过
        const to = ACCEPTED_REQ_STATUS
        assertReqTransition(r.status, to, 'human')
        
        // 创建简化的验收材料记录（标注为覆盖通过）
        if (r.verification === undefined) {
          r.verification = {
            summary: '人工覆盖通过（未提交验收材料）',
            evidence: [confirmOverride],
            submittedAt: now(),
            submittedBy: { kind: 'human' },
            reviewedAt: now(),
            reviewedBy: { kind: 'human' },
            sheet: {
              version: 1,
              items: [],
              generatedAt: now(),
              generatedBy: { kind: 'human' }
            },
            sheetHistory: []
          }
        }
        
        r.status = to
        r.version += 1
        r.updatedAt = now()
        r.updatedBy = { kind: 'human' }
        recordStatus(r, to, r.updatedAt, { kind: 'human' }, 
          '人工验收通过（带覆盖：' + confirmOverride + '）')
        r.comments.push({
          id: ids.comment(),
          body: '[验收] 人工审核通过（带覆盖）：' + confirmOverride + '｜尚无验收材料',
          createdAt: now(),
          createdBy: { kind: 'human' },
        })
        return { requirements: [r], tasks: [] }
      }
      
      const v = r.verification
      const items = v?.sheet?.items ?? []
      const failed = countFailedItems(items)
      const pending = countPendingItems(items)
      const noMaterials = v === undefined
      const unqualified = noMaterials || failed + pending > 0
      if (pass && unqualified && confirmOverride.length === 0) {
        throw Object.assign(
          new Error('需求 ' + r.id + ' 未执行验收通过：'
            + (noMaterials
                ? '尚无验收材料（本次通过没有任何验收证据）'
                : '验收单里不通过 ' + failed + ' 项 / 未裁决 ' + pending + ' 项')
            + '。这属于不合规通过，须由人显式覆盖（带 confirm_override 重发）——覆盖会写入台账留痕'),
          { code: 'verify_override_required' },
        )
      }
      // REQ-9f4a44：验收通过 → 直接归档（无 done 中转）；退回仍回 implementing
      const to = pass ? ACCEPTED_REQ_STATUS : REWORK_REQ_STATUS
      assertReqTransition(r.status, to, 'human')
      // ── 分类感知产物闸门（REQ-31e11f t4）──
      // 覆盖路径跳过：无材料时本就没有 verification 产物可登记，而人已显式确认"知道没有证据仍要通过"。
      if (pass && !unqualified) {
        const artifacts = r.artifacts
        const isLegacy = artifacts === undefined || artifacts.length === 0
        if (!isLegacy) {
          const verArtifact = artifacts.find(a => isAcceptingStage(a.stage) && a.kind === 'verification')
          if (verArtifact === undefined) {
            throw Object.assign(new Error('节点产物缺失：accepting 阶段须先完成产物（kind=verification）并登记'), { code: 'missing_artifact' })
          }
        }
      }
      // REQ-a8d582 FR-2：返工任务跟着"退回返工"这个**人的动作**走（原先在裁决时就自动生成）。
      const reworkTasks = pass ? [] : materializeReworkFromSheet(ledger, r.id, { kind: 'human' }, now())
      if (v !== undefined) {
        v.reviewedAt = now()
        v.reviewedBy = { kind: 'human' }
        v.decision = pass ? 'pass' : 'rework'
        if (note.length > 0) v.reviewNote = note
      }
      if (pass && unqualified) {
        r.acceptanceOverride = {
          at: now(),
          by: { kind: 'human' },
          detail: confirmOverride,
          failed,
          pending,
          noMaterials,
        }
      }
      r.status = to
      r.version += 1
      r.updatedAt = now()
      r.updatedBy = { kind: 'human' }
      recordStatus(r, to, r.updatedAt, { kind: 'human' }, pass
        ? (unqualified ? '人工验收通过（带覆盖：' + confirmOverride + '）' : '人工验收通过')
        : '人工验收退回返工：' + note)
      r.comments.push({
        id: ids.comment(),
        body: pass
          ? (unqualified
              ? '[验收] 人工审核通过（带覆盖）：' + confirmOverride
                + (v !== undefined ? '｜材料结论：' + v.summary : '｜尚无验收材料')
              : '[验收] 人工审核通过（人）：' + (v?.summary ?? ''))
          : '[验收] 人工审核退回返工（人）：' + note
            + (reworkTasks.length > 0 ? '（按未过项生成 ' + reworkTasks.length + ' 个返工任务）' : ''),
        createdAt: now(),
        createdBy: { kind: 'human' },
      })
      return { requirements: [r], tasks: reworkTasks }
    })
    ok(res, result.changed.requirements[0])
  }

  /**
   * POST /dashboard/api/reqboard/req/verdicts
   * 验收单逐项裁决（REQ-2e9473 t14/W6）：人逐项打勾（passed/failed + 意见）。
   *  - 全部通过 → 提示人点「验收通过」归档（不自动归档：验收通过是人工门）；
   *  - 有不通过 → **只记录**（REQ-a8d582 FR-2）：需求留在验收态，由人点「退回返工」生成返工任务；
   *  - 仍有待验项 → 挂起（验收单状态持久化，稍后从断点续验）。
   */
  async function handleVerdicts(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const version = typeof body.version === 'number' ? body.version : NaN
    if (!Number.isFinite(version)) badInput('version 必须是数字（验收单版本）')
    const rawVerdicts = Array.isArray(body.verdicts) ? body.verdicts : []
    if (rawVerdicts.length === 0) badInput('verdicts 不能为空（逐项裁决：itemId/status/opinion）')
    const verdicts = rawVerdicts.map((v: unknown) => {
      const o = (typeof v === 'object' && v !== null ? v : {}) as Record<string, unknown>
      const itemId = normalizeText(o.itemId, 'verdicts[].itemId', 64)
      const status = normalizeText(o.status, 'verdicts[].status', 16)
      if (itemId.length === 0) badInput('verdicts[].itemId 不能为空')
      if (!isDecidableItemStatus(status)) badInput('verdicts[].status 只能是 passed 或 failed')
      const opinion = normalizeText(o.opinion, 'verdicts[].opinion', 1000)
      if (isFailedItem(status) && opinion.length === 0) badInput('不通过的验收项必须写意见（opinion）')
      return { itemId, status: status as VerificationItem['status'], opinion }
    })
    const nowTs = now()
    const result = await store.mutate('requirement-updated', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound('需求 ' + id)
      if (!isVerifiableStage(r)) {
        badInput('需求 ' + id + ' 当前处于 ' + r.status + '，不在验收/返工态（先提交验收单）')
      }
      const v = r.verification
      if (v === undefined || v.sheet === undefined) ctx.badInput('需求 ' + id + ' 还没有验收单（先 reqboard_verify_submit）')
      const sheet = v.sheet
      if (sheet.version !== version) badInput('验收单版本不匹配：当前 v' + sheet.version + '，收到 v' + version + '（防并发错版）')
      for (const verdict of verdicts) {
        const item = sheet.items.find(i => i.id === verdict.itemId) ?? notFound('验收项 ' + verdict.itemId + ' 不存在')
        item.status = verdict.status
        if (verdict.opinion.length > 0) item.opinion = verdict.opinion
        item.decidedAt = nowTs
        item.decidedBy = { kind: 'human' }
      }
      // REQ-a8d582 FR-2：这里**不再**改需求状态、**不再**建返工任务。
      // 理由：那两条都是"退回"这个决定的后果，而决定权在人——系统替他决定的结果是按钮消失、
      // 且返工卡在人还没表态时就已建好。现在退回与通过各有自己的入口（见文件头注释）。
      const pendingCount = countPendingItems(sheet.items)
      const failedCount = countFailedItems(sheet.items)
      r.version += 1
      r.updatedAt = nowTs
      r.updatedBy = { kind: 'human' }
      r.comments.push({
        id: ids.comment(),
        body: '[验收单] v' + sheet.version + ' 逐项裁决：通过 ' + countPassedItems(sheet.items) + ' 项，不通过 ' + failedCount + ' 项，待验 ' + pendingCount + ' 项'
          + (failedCount > 0
              ? '（需求仍在验收态：由人点「退回返工」生成返工任务，或点「验收通过」带覆盖归档）'
              : (pendingCount === 0 ? '（全部通过 → 可点「验收通过」归档）' : '（挂起，稍后从断点续验）')),
        createdAt: nowTs,
        createdBy: { kind: 'human' },
      })
      return { requirements: [r] }
    })
    const r = result.changed.requirements[0]
    const sheet = r.verification?.sheet
    const failed = sheet === undefined ? 0 : countFailedItems(sheet.items)
    const pending = sheet === undefined ? 0 : countPendingItems(sheet.items)
    return ok(res, {
      requirement_id: r.id,
      status: r.status,
      sheet_version: sheet?.version ?? 0,
      pending,
      passed: sheet === undefined ? 0 : countPassedItems(sheet.items),
      failed,
      // 保留字段（调用方契约）：REQ-a8d582 FR-2 起裁决不再建任务，恒为空数组。
      rework_tasks: [],
      note: failed > 0
        ? '有 ' + failed + ' 项不通过：需求仍在验收态——请点「退回返工」（按未过项生成返工卡）或「验收通过」（会要求覆盖确认）'
        : ((sheet !== undefined && isEveryItemPassed(sheet.items))
            ? '全部通过 → 请点「验收通过」归档（人工门）'
            : '裁决已记录（挂起中，可稍后从断点续验）'),
    })
  }

  return { handleVerifyDecision, handleVerdicts }
}
