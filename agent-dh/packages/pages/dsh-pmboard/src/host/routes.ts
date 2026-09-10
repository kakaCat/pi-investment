/**
 * Reqboard 路由薄层：/dashboard/api/reqboard 前缀分发。
 * 信封：200 {success:true,data} / 4xx|500 {success:false,error,code?}。
 * SSE：GET /events 推送台账变更（revision + kind）。
 *
 * 闸门在此强制执行：move 的 actor 经 protocol 断言，人工闸门拒绝 agent/system。
 *
 * @module dsh-pmboard/host/routes
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { ReqboardStore } from './store.js'
import {
  assertDagAcyclic,
  assertReqTransition,
  assertTaskTransition,
  asActor,
  asDependsOn,
  asReqStatus,
  asScope,
  asTaskPhase,
  asTaskSide,
  asTaskStatus,
  newCommentId,
  newExecutionId,
  newRequirementId,
  newTaskId,
  normalizeText,
  normalizeTitle,
  readyTasks,
  type ActorRef,
  type CommentRecord,
  type RequirementRecord,
  type TaskRecord,
  type TriageRecord,
} from '../shared/protocol.js'
import { applyTaskRollup } from './rollup.js'

export interface ReqboardRouteDeps {
  store: ReqboardStore
  now: () => number
  /** 可注入 id 生成器（测试用） */
  ids?: {
    requirement?: () => string
    task?: () => string
    comment?: () => string
  }
}

function json(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify(body))
}

function ok(res: ServerResponse, data: unknown): void {
  json(res, 200, { success: true, data })
}

function fail(res: ServerResponse, err: unknown): void {
  const e = err as { message?: string; code?: string }
  const status = e.code === 'invalid_input' || e.code === 'invalid_transition' || e.code === 'invalid_dag' ? 400
    : e.code === 'human_gate' || e.code === 'system_gate' ? 403
    : e.code === 'not_found' ? 404 : 500
  json(res, status, { success: false, error: e.message ?? String(err), ...(e.code ? { code: e.code } : {}) })
}

function notFound(what: string): never {
  throw Object.assign(new Error(`${what}不存在`), { code: 'not_found' })
}

async function readBody(req: IncomingMessage): Promise<Record<string, unknown>> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  if (chunks.length === 0) return {}
  try {
    const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8')) as unknown
    if (typeof parsed !== 'object' || parsed === null) throw new Error('not object')
    return parsed as Record<string, unknown>
  } catch {
    throw Object.assign(new Error('请求体不是合法 JSON'), { code: 'invalid_input' })
  }
}

export function createReqboardHandler(deps: ReqboardRouteDeps) {
  const { store, now } = deps
  const ids = {
    requirement: deps.ids?.requirement ?? (() => newRequirementId()),
    task: deps.ids?.task ?? (() => newTaskId()),
    comment: deps.ids?.comment ?? (() => newCommentId()),
  }

  /** 生成不与现有台账冲突的 id。 */
  async function mintId(kind: 'requirement' | 'task'): Promise<string> {
    return store.read(ledger => {
      for (let i = 0; i < 20; i++) {
        const id = kind === 'requirement' ? ids.requirement() : ids.task()
        const clash = kind === 'requirement'
          ? ledger.requirements.some(r => r.id === id)
          : ledger.tasks.some(t => t.id === id)
        if (!clash) return id
      }
      throw new Error('id 生成冲突过多')
    })
  }

  // -- 子路由实现 ----------------------------------------------------------

  async function handleState(res: ServerResponse): Promise<void> {
    const ledger = await store.read(l => l)
    ok(res, {
      revision: ledger.revision,
      requirements: ledger.requirements,
      tasks: ledger.tasks.map(t => ({ ...t })),
      // 派生视图：每个需求的 ready 任务（client 调度提示用）
      ready: Object.fromEntries(
        ledger.requirements.map(r => [r.id, readyTasks(ledger.tasks, r.id).map(t => t.id)]),
      ),
    })
  }

  function handleEvents(req: IncomingMessage, res: ServerResponse): void {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-store',
      Connection: 'keep-alive',
    })
    res.write(': connected\n\n')
    const unsubscribe = store.subscribe((change) => {
      try {
        res.write(`event: ${change.kind}\n`)
        res.write(`data: ${JSON.stringify({ revision: change.revision, kind: change.kind })}\n\n`)
      } catch { /* client gone */ }
    })
    const heartbeat = setInterval(() => { try { res.write(': hb\n\n') } catch { /* gone */ } }, 25_000)
    req.on('close', () => { clearInterval(heartbeat); unsubscribe() })
  }

  async function handleReqCreate(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const nowTs = now()
    const actor: ActorRef = { kind: 'human' }
    const record: RequirementRecord = {
      id: await mintId('requirement'),
      title: normalizeTitle(body.title),
      description: normalizeText(body.description, 'description'),
      ...(body.docLinks !== undefined ? { docLinks: body.docLinks as RequirementRecord['docLinks'] } : {}),
      status: 'draft',
      blocked: false,
      comments: [],
      version: 1,
      createdAt: nowTs,
      updatedAt: nowTs,
      createdBy: actor,
      updatedBy: actor,
    }
    await store.mutate('requirement-created', (ledger) => {
      ledger.requirements.push(record)
      return { requirements: [record] }
    })
    ok(res, record)
  }

  async function handleReqMove(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const to = asReqStatus(body.to)
    const actor = asActor(body.actor ?? 'human')
    const reason = normalizeText(body.reason, 'reason', 500)
    const result = await store.mutate('requirement-moved', (ledger) => {
      const req = ledger.requirements.find(r => r.id === id) ?? notFound(`需求 ${id}`)
      assertReqTransition(req.status, to, actor)
      req.status = to
      req.version += 1
      req.updatedAt = now()
      req.updatedBy = { kind: actor }
      if (reason) {
        req.comments.push({ id: ids.comment(), body: `[状态] ${req.status} ← 转移说明：${reason}`, createdAt: now(), createdBy: { kind: actor } })
      }
      return { requirements: [req] }
    })
    ok(res, result.changed.requirements[0])
  }

  async function handleReqUpdate(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const result = await store.mutate('requirement-updated', (ledger) => {
      const req = ledger.requirements.find(r => r.id === id) ?? notFound(`需求 ${id}`)
      if (body.title !== undefined) req.title = normalizeTitle(body.title)
      if (body.description !== undefined) req.description = normalizeText(body.description, 'description')
      if (body.docLinks !== undefined) req.docLinks = body.docLinks as RequirementRecord['docLinks']
      if (body.blocked !== undefined) {
        req.blocked = Boolean(body.blocked)
        req.blockedReason = req.blocked ? normalizeText(body.blockedReason, 'blockedReason', 300) : undefined
      }
      if (body.paused !== undefined) req.paused = Boolean(body.paused)
      req.version += 1
      req.updatedAt = now()
      req.updatedBy = { kind: 'human' }
      return { requirements: [req] }
    })
    ok(res, result.changed.requirements[0])
  }

  async function handleTaskCreate(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const requirementId = normalizeText(body.requirementId, 'requirementId', 64)
    const nowTs = now()
    const record: TaskRecord = {
      id: await mintId('task'),
      requirementId,
      title: normalizeTitle(body.title),
      description: normalizeText(body.description, 'description'),
      phase: asTaskPhase(body.phase),
      side: asTaskSide(body.side),
      dependsOn: asDependsOn(body.dependsOn),
      scope: asScope(body.scope),
      acceptance: normalizeText(body.acceptance, 'acceptance', 2000),
      context: normalizeText(body.context, 'context', 2000),
      ...(body.skipIntegration !== undefined ? { skipIntegration: Boolean(body.skipIntegration) } : {}),
      status: 'todo',
      blocked: false,
      executions: [],
      comments: [],
      version: 1,
      createdAt: nowTs,
      updatedAt: nowTs,
      createdBy: { kind: 'human' },
      updatedBy: { kind: 'human' },
    }
    await store.mutate('task-created', (ledger) => {
      if (!ledger.requirements.some(r => r.id === requirementId)) notFound(`需求 ${requirementId}`)
      assertDagAcyclic([...ledger.tasks, record], requirementId)
      ledger.tasks.push(record)
      // 任务集变化 → 重算所属需求完成度（派生推进）
      const advanced = applyTaskRollup(ledger, { now: now(), commentId: () => ids.comment() }, record.requirementId)
      return { tasks: [record], requirements: advanced }
    })
    ok(res, record)
  }

  async function handleTaskMove(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const to = asTaskStatus(body.to)
    const actor = asActor(body.actor ?? 'human')
    const reason = normalizeText(body.reason, 'reason', 500)
    const sessionId = normalizeText(body.sessionId, 'sessionId', 128) || undefined
    const result = await store.mutate('task-moved', (ledger) => {
      const task = ledger.tasks.find(t => t.id === id) ?? notFound(`任务 ${id}`)
      assertTaskTransition(task.status, to, actor)
      task.status = to
      task.version += 1
      task.updatedAt = now()
      task.updatedBy = { kind: actor, ...(sessionId ? { sessionId } : {}) }
      if (to === 'in_progress' && sessionId) {
        task.claimedBy = sessionId
        task.claimedAt = now()
        task.executions.push({ id: newExecutionId(), sessionId, trigger: actor === 'system' ? 'auto' : 'manual', startedAt: now(), outcome: 'running' })
      }
      if (to === 'todo' || to === 'done' || to === 'canceled') {
        delete task.claimedBy
        delete task.claimedAt
      }
      if (reason) {
        task.comments.push({ id: ids.comment(), body: `[状态] → ${to}：${reason}`, createdAt: now(), createdBy: { kind: actor } })
      }
      // 派生推进（system）：任务状态落定后重算所属需求（全部实施任务 done → 验收）
      const advanced = applyTaskRollup(ledger, { now: now(), commentId: () => ids.comment() }, task.requirementId)
      return { tasks: [task], requirements: advanced }
    })
    ok(res, result.changed.tasks[0])
  }

  async function handleTaskUpdate(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const result = await store.mutate('task-updated', (ledger) => {
      const task = ledger.tasks.find(t => t.id === id) ?? notFound(`任务 ${id}`)
      if (body.title !== undefined) task.title = normalizeTitle(body.title)
      if (body.description !== undefined) task.description = normalizeText(body.description, 'description')
      if (body.phase !== undefined) task.phase = asTaskPhase(body.phase)
      if (body.side !== undefined) task.side = asTaskSide(body.side)
      if (body.scope !== undefined) task.scope = asScope(body.scope)
      if (body.acceptance !== undefined) task.acceptance = normalizeText(body.acceptance, 'acceptance', 2000)
      if (body.context !== undefined) task.context = normalizeText(body.context, 'context', 2000)
      if (body.skipIntegration !== undefined) task.skipIntegration = Boolean(body.skipIntegration)
      if (body.dependsOn !== undefined) {
        task.dependsOn = asDependsOn(body.dependsOn)
        assertDagAcyclic(ledger.tasks, task.requirementId)
      }
      if (body.blocked !== undefined) {
        task.blocked = Boolean(body.blocked)
        task.blockedReason = task.blocked ? normalizeText(body.blockedReason, 'blockedReason', 300) : undefined
      }
      task.version += 1
      task.updatedAt = now()
      task.updatedBy = { kind: 'human' }
      // 取消/依赖变更都可能改变完成度 → 重算所属需求
      const advanced = applyTaskRollup(ledger, { now: now(), commentId: () => ids.comment() }, task.requirementId)
      return { tasks: [task], requirements: advanced }
    })
    ok(res, result.changed.tasks[0])
  }

  async function handleComment(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const target = normalizeText(body.target, 'target', 16)
    const id = normalizeText(body.id, 'id', 64)
    const actor = asActor(body.actor ?? 'human')
    const comment: CommentRecord = {
      id: ids.comment(),
      body: normalizeText(body.body, 'body', 2000),
      createdAt: now(),
      createdBy: { kind: actor },
    }
    if (comment.body.length === 0) throw Object.assign(new Error('评论不能为空'), { code: 'invalid_input' })
    const result = await store.mutate('comment-added', (ledger) => {
      if (target === 'req') {
        const req = ledger.requirements.find(r => r.id === id) ?? notFound(`需求 ${id}`)
        req.comments.push(comment)
        req.updatedAt = now()
        return { requirements: [req] }
      }
      if (target === 'task') {
        const task = ledger.tasks.find(t => t.id === id) ?? notFound(`任务 ${id}`)
        task.comments.push(comment)
        task.updatedAt = now()
        return { tasks: [task] }
      }
      throw Object.assign(new Error('target 必须是 req/task'), { code: 'invalid_input' })
    })
    ok(res, { comment, target: result.changed.requirements[0]?.id ?? result.changed.tasks[0]?.id })
  }


  // -- Triage（人机回路）----------------------------------------------------

  async function handleTriageList(res: ServerResponse): Promise<void> {
    const ledger = await store.read(l => l)
    ok(res, {
      pending: ledger.triages.filter(t => t.status === 'pending'),
      resolved: ledger.triages.filter(t => t.status !== 'pending').slice(-50),
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
        const tri = ledger.triages.find(t => t.id === triageId && t.status === 'pending') ?? notFound(`待归类 ${triageId}`)
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
    const preTri = pre.triages.find(t => t.id === triageId && t.status === 'pending')
    const autoDraft = preTri?.resultRequirementId
      ? pre.requirements.find(r => r.id === preTri!.resultRequirementId && r.status !== 'archived')
      : undefined

    if (autoDraft) {
      const result = await store.mutate('requirement-updated', (ledger) => {
        const tri = ledger.triages.find(t => t.id === triageId && t.status === 'pending') ?? notFound(`待归类 ${triageId}`)
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
      const tri = ledger.triages.find(t => t.id === triageId && t.status === 'pending') ?? notFound(`待归类 ${triageId}`)
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
        status: 'draft',
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
      const req = ledger.requirements.find(r => r.id === reqId && r.status === 'draft' && r.createdBy?.kind === 'agent')
      if (req) {
        req.status = 'canceled'
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
      const tri = ledger.triages.find(t => t.id === triageId && t.status === 'pending') ?? notFound(`待归类 ${triageId}`)
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
      const tri = ledger.triages.find(t => t.id === triageId && t.status === 'pending') ?? notFound(`待归类 ${triageId}`)
      tri.status = 'rejected'
      tri.resolvedAt = nowTs
      tri.resolvedBy = actor
      tri.comments.push({ id: ids.comment(), body: '[人工否决] 不建需求', createdAt: nowTs, createdBy: actor })
      const cancelled = cancelAutoDrafts(ledger, tri, nowTs)
      return { requirements: cancelled, triages: [tri] }
    })
    ok(res, result.changed.triages[0])
  }

  // -- 分发 ----------------------------------------------------------------

  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const url = new URL(req.url ?? '/', 'http://localhost')
      const sub = url.pathname.replace(/^\/dashboard\/api\/reqboard\/?/, '')
      const method = req.method ?? 'GET'

      if (method === 'GET' && (sub === '' || sub === 'state')) return await handleState(res)
      if (method === 'GET' && sub === 'events') return handleEvents(req, res)
      if (method === 'GET' && sub === 'health') return ok(res, { status: 'ok' })

      if (method === 'POST' && sub === 'req/create') return await handleReqCreate(req, res)
      if (method === 'POST' && sub === 'req/move') return await handleReqMove(req, res)
      if (method === 'POST' && sub === 'req/update') return await handleReqUpdate(req, res)
      if (method === 'POST' && sub === 'task/create') return await handleTaskCreate(req, res)
      if (method === 'POST' && sub === 'task/move') return await handleTaskMove(req, res)
      if (method === 'POST' && sub === 'task/update') return await handleTaskUpdate(req, res)
      if (method === 'POST' && sub === 'comment') return await handleComment(req, res)

      if (method === 'GET' && sub === 'triage') return await handleTriageList(res)
      if (method === 'POST' && sub === 'triage/confirm') return await handleTriageConfirm(req, res)
      if (method === 'POST' && sub === 'triage/rebind') return await handleTriageRebind(req, res)
      if (method === 'POST' && sub === 'triage/reject') return await handleTriageReject(req, res)

      json(res, 404, { success: false, error: `未知路由：${method} ${url.pathname}`, code: 'not_found' })
    } catch (err) {
      fail(res, err)
    }
  }
}
