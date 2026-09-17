/**
 * Triage 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * @module dsh-pmboard/http/routers/Triage
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  newRequirementId,
  normalizeText,
  normalizeTitle,
  type ActorRef,
  type RequirementRecord,
  type TriageRecord,
} from '../../shared/protocol.js'
import { isDraft, isNotArchived, isPendingTriage, isResolvedTriage } from '../../domain/status/Predicates.js'
import { CANCELED_REQ_STATUS, INITIAL_REQ_STATUS } from '../../domain/requirement/RequirementStatus.js'
import type { RouterCtx } from './shared.js'

export function createTriageRouter(ctx: RouterCtx) {
  const { store, now, ids, ok, readBody, notFound } = ctx

  async function handleTriageList(res: ServerResponse): Promise<void> {
    const ledger = await store.read(l => l)
    ok(res, {
      pending: ledger.triages.filter(t => isPendingTriage(t)),
      resolved: ledger.triages.filter(t => isResolvedTriage(t)).slice(-50),
    })
  }

  async function handleTriageConfirm(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const triageId = normalizeText(body.triageId, 'triageId', 64)
    const action = normalizeText(body.action, 'action', 32) as 'create_req' | 'bind_req'
    const targetId = body.targetId !== undefined ? normalizeText(body.targetId, 'targetId', 64) : undefined
    const nowTs = now()
    const actor: ActorRef = { kind: 'human' }

    // 人工编辑覆盖（可编辑建议卡）：标题/分类/描述
    const editTitle = body.title !== undefined && typeof body.title === 'string' ? normalizeTitle(body.title) : undefined
    const CATEGORIES = ['feature', 'bug', 'doc', 'refactor', 'spike', 'chore']
    let editCategory: RequirementRecord['category'] | undefined
    if (body.category !== undefined && body.category !== null && String(body.category) !== '') {
      const c = String(body.category)
      if (!CATEGORIES.includes(c)) {
        throw Object.assign(new Error(`分类必须是 ${CATEGORIES.join('/')}`), { code: 'invalid_input' })
      }
      editCategory = c as RequirementRecord['category']
    }
    const editDescription = body.description !== undefined && typeof body.description === 'string'
      ? body.description.slice(0, 4000)
      : undefined

    if (action === 'bind_req') {
      const result = await store.mutate('requirement-updated', (ledger) => {
        const tri = ledger.triages.find(t => t.id === triageId && isPendingTriage(t)) ?? notFound(`待归类 ${triageId}`)
        const req = ledger.requirements.find(r => r.id === targetId) ?? notFound(`目标需求 ${targetId}`)
        req.comments.push({
          id: ids.comment(),
          body: `[会话绑定] 会话 ${tri.sessionId} 已绑定（判定分数 ${tri.score}）`,
          createdAt: nowTs,
          createdBy: actor,
        })
        req.updatedAt = nowTs
        req.updatedBy = actor
        tri.status = 'confirmed'
        tri.resolvedAt = nowTs
        tri.resolvedBy = actor
        tri.resultRequirementId = req.id
        return { requirements: [req], triages: [tri] }
      })
      ok(res, result.changed)
      return
    }

    // create_req：可能已有 session-sync 自动立项的草稿 → 确认 = 采纳并应用人工编辑，不重复建卡
    const pre = await store.read(l => l)
    const preTri = pre.triages.find(t => t.id === triageId && isPendingTriage(t))
    const autoDraft = preTri?.resultRequirementId
      ? pre.requirements.find(r => r.id === preTri!.resultRequirementId && isNotArchived(r))
      : undefined

    if (autoDraft) {
      const result = await store.mutate('requirement-updated', (ledger) => {
        const tri = ledger.triages.find(t => t.id === triageId && isPendingTriage(t)) ?? notFound(`待归类 ${triageId}`)
        const req = ledger.requirements.find(r => r.id === autoDraft.id) ?? notFound(`自动立项草稿 ${autoDraft.id}`)
        if (editTitle !== undefined && editTitle.length > 0) req.title = editTitle
        if (editCategory !== undefined) req.category = editCategory
        if (editDescription !== undefined) req.description = editDescription
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = actor
        req.comments.push({
          id: ids.comment(),
          body: `[人工确认] 采纳自动立项草稿（原判定分数 ${tri.score}）${editTitle || editCategory ? '，已按人工编辑更新' : ''}`,
          createdAt: nowTs,
          createdBy: actor,
        })
        tri.status = 'confirmed'
        tri.resolvedAt = nowTs
        tri.resolvedBy = actor
        tri.resultRequirementId = req.id
        return { requirements: [req], triages: [tri] }
      })
      ok(res, result.changed)
      return
    }

    // 无自动草稿：直接建（分类/标题取自 LLM 结构化建议，可被人工编辑覆盖）
    const result = await store.mutate('requirement-created', (ledger) => {
      const tri = ledger.triages.find(t => t.id === triageId && isPendingTriage(t)) ?? notFound(`待归类 ${triageId}`)
      // 兼容旧账本：从 [LLM 分类] 评论提取分类/建议标题（结构化字段缺省时兜底）
      let category = tri.suggestedCategory ?? undefined
      let suggestedTitle = tri.suggestedTitle ?? undefined
      if (category === undefined || suggestedTitle === undefined) {
        const llmComment = tri.comments.find(c => c.body.includes('[LLM 分类]'))
        if (llmComment) {
          const catMatch = llmComment.body.match(/分类：([a-z]+)/)
          if (category === undefined && catMatch && CATEGORIES.includes(catMatch[1])) {
            category = catMatch[1] as RequirementRecord['category']
          }
          const titleMatch = llmComment.body.match(/建议标题：(.+)/)
          if (suggestedTitle === undefined && titleMatch) suggestedTitle = titleMatch[1].trim()
        }
      }
      const req: RequirementRecord = {
        id: newRequirementId(),
        title: normalizeTitle(editTitle || suggestedTitle || tri.firstMessageText) || '新建需求',
        description: editDescription ?? tri.firstMessageText.slice(0, 4000),
        ...(editCategory !== undefined ? { category: editCategory } : category ? { category } : {}),
        sourceSessionId: tri.sessionId,
        status: INITIAL_REQ_STATUS,
        blocked: false,
        comments: [
          { id: ids.comment(), body: `[会话捕获] 来自会话 ${tri.sessionId}，判定分数 ${tri.score}`, createdAt: nowTs, createdBy: actor },
        ],
        version: 1,
        createdAt: nowTs,
        updatedAt: nowTs,
        createdBy: actor,
        updatedBy: actor,
      }
      ledger.requirements.push(req)
      tri.status = 'confirmed'
      tri.resolvedAt = nowTs
      tri.resolvedBy = actor
      tri.resultRequirementId = req.id
      if (!Array.isArray(tri.resultRequirementIds)) tri.resultRequirementIds = []
      if (!tri.resultRequirementIds.includes(req.id)) tri.resultRequirementIds.push(req.id)
      return { requirements: [req], triages: [tri] }
    })
    ok(res, result.changed)
  }

  /** 取消该 triage 名下仍为草稿的自动立项卡（reject/改绑时清场，避免孤儿草稿）。 */
  function cancelAutoDrafts(ledger: { requirements: RequirementRecord[] }, tri: TriageRecord, nowTs: number): RequirementRecord[] {
    if (!Array.isArray(tri.resultRequirementIds) || tri.resultRequirementIds.length === 0) return []
    const cancelled: RequirementRecord[] = []
    for (const reqId of tri.resultRequirementIds) {
      const req = ledger.requirements.find(r => r.id === reqId && isDraft(r) && r.createdBy?.kind === 'agent')
      if (req) {
        req.status = CANCELED_REQ_STATUS
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'human' }
        req.comments.push({
          id: ids.comment(),
          body: `[人工] 未采纳自动立项草稿，取消（triage ${tri.id}）`,
          createdAt: nowTs,
          createdBy: { kind: 'human' },
        })
        cancelled.push(req)
      }
    }
    return cancelled
  }

  async function handleTriageRebind(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const triageId = normalizeText(body.triageId, 'triageId', 64)
    const targetId = normalizeText(body.targetId, 'targetId', 64)
    const nowTs = now()
    const actor: ActorRef = { kind: 'human' }

    const result = await store.mutate('requirement-updated', (ledger) => {
      const tri = ledger.triages.find(t => t.id === triageId && isPendingTriage(t)) ?? notFound(`待归类 ${triageId}`)
      // 校验目标存在（不存在 notFound 抛错）
      ledger.requirements.find(r => r.id === targetId) ?? notFound(`目标需求 ${targetId}`)
      tri.suggestedAction = 'bind_req'
      tri.suggestedTargetId = targetId
      tri.comments.push({ id: ids.comment(), body: `[人工改绑] 改为绑定 ${targetId}`, createdAt: nowTs, createdBy: actor })
      const cancelled = cancelAutoDrafts(ledger, tri, nowTs)
      return { requirements: cancelled, triages: [tri] }
    })
    ok(res, result.changed.triages[0])
  }

  async function handleTriageReject(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const triageId = normalizeText(body.triageId, 'triageId', 64)
    const nowTs = now()
    const actor: ActorRef = { kind: 'human' }

    const result = await store.mutate('requirement-updated', (ledger) => {
      const tri = ledger.triages.find(t => t.id === triageId && isPendingTriage(t)) ?? notFound(`待归类 ${triageId}`)
      tri.status = 'rejected'
      tri.resolvedAt = nowTs
      tri.resolvedBy = actor
      tri.comments.push({ id: ids.comment(), body: '[人工否决] 不建需求', createdAt: nowTs, createdBy: actor })
      const cancelled = cancelAutoDrafts(ledger, tri, nowTs)
      return { requirements: cancelled, triages: [tri] }
    })
    ok(res, result.changed.triages[0])
  }

  return { handleTriageList, handleTriageConfirm, cancelAutoDrafts, handleTriageRebind, handleTriageReject }
}
