/**
 * Verdicts 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * @module dsh-pmboard/http/routers/Verdicts
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  assertArchiveMaterials, assertDagAcyclic, assertReqTransition, assertTaskTransition,
  asActor, asDependsOn, asReqStatus, asStageKey, asScope, asTaskPhase, asTaskSide, asTaskStatus,
  newCommentId, newExecutionId, newRequirementId, newTaskId,
  normalizeText, normalizeTitle, readyTasks, recordStatus, windowCodeFromSessionId,
  type ActorRef, type CommentRecord, type RequirementRecord, type TaskRecord, type TriageRecord,
} from '../../shared/protocol.js'
import {
  countFailedItems, countPassedItems, countPendingItems, isAccepting, isAcceptingStage,
  isDecidableItemStatus, isEveryItemPassed, isFailedItem, isVerifiableStage,
} from '../../domain/status/Predicates.js'
import { ACCEPTED_REQ_STATUS, REWORK_REQ_STATUS } from '../../domain/requirement/RequirementStatus.js'
import { INITIAL_TASK_STATUS } from '../../domain/task/TaskStatus.js'
import type { RouterCtx } from './shared.js'

export function createVerdictsRouter(ctx: RouterCtx) {
  const { store, now, ids, mintId, ok, fail, json, readBody, badInput, notFound, deps } = ctx

  /**
   * 验收人工审核（仅人）：pass → done（完成），rework → implementing（退回返工，必须写意见）。
   * 前置：需求处于 accepting，且 agent 已提交验收材料（证据）——"过"必须有据可查。
   */
  async function handleVerifyDecision(req: IncomingMessage, res: ServerResponse, pass: boolean): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const note = normalizeText(body.note, 'note', 1000)
    if (!pass && note.length === 0) badInput('退回返工必须写清意见（note）')
    const result = await store.mutate('requirement-moved', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound("需求 " + id)
      if (!isAccepting(r)) badInput("需求 " + id + " 当前处于 " + r.status + "，不在验收态（先提交验收）")
      const v = r.verification
      if (v === undefined) {
        badInput("需求 " + id + " 还没有验收材料：窗口需先 reqboard_verify_submit 提交证据（做了什么、怎么验的、看到什么）")
      }
      // REQ-9f4a44：验收通过 → 直接归档（无 done 中转）；退回仍回 implementing
      const to = pass ? ACCEPTED_REQ_STATUS : REWORK_REQ_STATUS
      assertReqTransition(r.status, to, 'human')
      // ── 分类感知产物闸门（REQ-31e11f t4）──
      // accepting>done 的确认门由本路由的人工审核替代：人点 pass 本身就是确认 verification 产物。
      // 所以这里只检查 missing_artifact（产物必须存在），不检查 artifact_not_confirmed。
      if (pass) {
        const artifacts = r.artifacts
        const isLegacy = artifacts === undefined || artifacts.length === 0
        if (!isLegacy) {
          const verArtifact = artifacts.find(a => isAcceptingStage(a.stage) && a.kind === 'verification')
          if (verArtifact === undefined) {
            throw Object.assign(new Error('节点产物缺失：accepting 阶段须先完成产物（kind=verification）并登记'), { code: 'missing_artifact' })
          }
        }
      }
      v.reviewedAt = now()
      v.reviewedBy = { kind: 'human' }
      v.decision = pass ? 'pass' : 'rework'
      if (note.length > 0) v.reviewNote = note
      r.status = to
      r.version += 1
      r.updatedAt = now()
      r.updatedBy = { kind: 'human' }
      recordStatus(r, to, r.updatedAt, { kind: 'human' }, pass ? '人工验收通过' : '人工验收退回返工：' + note)
      r.comments.push({
        id: ids.comment(),
        body: pass
          ? '[验收] 人工审核通过（人）：' + v.summary
          : '[验收] 人工审核退回返工（人）：' + note,
        createdAt: now(),
        createdBy: { kind: 'human' },
      })
      return { requirements: [r] }
    })
    ok(res, result.changed.requirements[0])
  }

  /**
   * POST /dashboard/api/reqboard/req/verdicts
   * 验收单逐项裁决（REQ-2e9473 t14/W6）：人逐项打勾（passed/failed + 意见）。
   *  - 全部通过 → 提示人点「验收通过」归档（不自动归档：验收通过是人工门）；
   *  - 有不通过 → 需求打回 implementing + 为每个未过项自动生成返工任务（关联原任务 + 意见）；
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
      return { itemId, status, opinion }
    })
    const nowTs = now()
    const result = await store.mutate('requirement-updated', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound('需求 ' + id)
      if (!isVerifiableStage(r)) {
        badInput('需求 ' + id + ' 当前处于 ' + r.status + '，不在验收/返工态（先提交验收单）')
      }
      const v = r.verification
      if (v === undefined || v.sheet === undefined) badInput('需求 ' + id + ' 还没有验收单（先 reqboard_verify_submit）')
      const sheet = v.sheet
      if (sheet.version !== version) badInput('验收单版本不匹配：当前 v' + sheet.version + '，收到 v' + version + '（防并发错版）')
      const failed: { item: typeof sheet.items[number] }[] = []
      for (const verdict of verdicts) {
        const item = sheet.items.find(i => i.id === verdict.itemId) ?? notFound('验收项 ' + verdict.itemId + ' 不存在')
        item.status = verdict.status
        if (verdict.opinion.length > 0) item.opinion = verdict.opinion
        item.decidedAt = nowTs
        item.decidedBy = { kind: 'human' }
        if (isFailedItem(verdict.status)) failed.push({ item })
      }
      const pendingCount = countPendingItems(sheet.items)
      // 返工回路：有不通过项 → 打回 implementing + 为每个未过项生成关联返工任务
      const reworkTaskIds: string[] = []
      if (failed.length > 0 && isAccepting(r)) {
        assertReqTransition(r.status, REWORK_REQ_STATUS, 'human')
        for (const { item } of failed) {
          const sourceTaskId = item.source.kind === 'task' ? item.source.taskId : undefined
          const orig = sourceTaskId === undefined ? undefined : ledger.tasks.find(t => t.id === sourceTaskId)
          let tid = newTaskId()
          for (let g = 0; g < 50 && ledger.tasks.some(t => t.id === tid); g++) tid = newTaskId()
          reworkTaskIds.push(tid)
          const task: TaskRecord = {
            id: tid,
            requirementId: r.id,
            title: '返工：' + (orig?.title ?? item.criterion).slice(0, 60),
            description: '验收不通过项返工（v' + sheet.version + ' 项 ' + item.id + '）：' + item.criterion,
            phase: (orig?.phase ?? 'implement') as TaskRecord['phase'],
            side: (orig?.side ?? 'fullstack') as TaskRecord['side'],
            dependsOn: [],
            scope: orig?.scope ?? asScope({}),
            acceptance: item.criterion,
            implementation: '按验收意见修复：' + (item.opinion ?? '（见验收单）'),
            context: '承接自 ' + (item.source.kind === 'requirement' ? '需求级验收项' : '任务 ' + item.source.taskId) + '；验收意见：' + (item.opinion ?? ''),
            status: INITIAL_TASK_STATUS,
            blocked: false,
            executions: [],
            comments: [],
            version: 1,
            createdAt: nowTs,
            updatedAt: nowTs,
            createdBy: { kind: 'human' },
            updatedBy: { kind: 'human' },
          }
          recordStatus(task, INITIAL_TASK_STATUS, nowTs, { kind: 'human' }, '验收不通过 → 自动生成返工任务（t14）')
          ledger.tasks.push(task)
        }
        r.status = REWORK_REQ_STATUS
        r.version += 1
        r.updatedAt = nowTs
        r.updatedBy = { kind: 'human' }
        recordStatus(r, REWORK_REQ_STATUS, nowTs, { kind: 'human' }, '验收单 '+failed.length+' 项不通过 → 打回返工（自动生成 ' + reworkTaskIds.length + ' 个返工任务）')
        r.comments.push({
          id: ids.comment(),
          body: '[验收单] v' + sheet.version + ' 逐项裁决：' + failed.length + ' 项不通过 → 打回实施。\n'
            + failed.map(f => '- ✗ ' + f.item.criterion + '：' + (f.item.opinion ?? '')).join('\n')
            + '\n返工任务：' + reworkTaskIds.join('、'),
          createdAt: nowTs,
          createdBy: { kind: 'human' },
        })
      } else {
        r.version += 1
        r.updatedAt = nowTs
        r.updatedBy = { kind: 'human' }
        const passed = countPassedItems(sheet.items)
        r.comments.push({
          id: ids.comment(),
          body: '[验收单] v' + sheet.version + ' 逐项裁决：通过 ' + passed + ' 项，待验 ' + pendingCount + ' 项'
            + (pendingCount === 0 ? '（全部通过 → 可点「验收通过」归档）' : '（挂起，稍后从断点续验）'),
          createdAt: nowTs,
          createdBy: { kind: 'human' },
        })
      }
      return { requirements: [r], tasks: ledger.tasks.filter(t => reworkTaskIds.includes(t.id)) }
    })
    const r = result.changed.requirements[0]
    const sheet = r.verification?.sheet
    return ok(res, {
      requirement_id: r.id,
      status: r.status,
      sheet_version: sheet?.version ?? 0,
      pending: sheet === undefined ? 0 : countPendingItems(sheet.items),
      passed: sheet === undefined ? 0 : countPassedItems(sheet.items),
      failed: sheet === undefined ? 0 : countFailedItems(sheet.items),
      rework_tasks: result.changed.tasks.map(t => t.id),
      note: result.changed.tasks.length > 0
        ? '有不通过项：需求已打回 implementing，生成 ' + result.changed.tasks.length + ' 个返工任务'
        : ((sheet !== undefined && isEveryItemPassed(sheet.items))
            ? '全部通过 → 请点「验收通过」归档（人工门）'
            : '裁决已记录（挂起中，可稍后从断点续验）'),
    })
  }

  return { handleVerifyDecision, handleVerdicts }
}
