/**
 * Reqboard 路由薄层：/dashboard/api/reqboard 前缀分发。
 * 信封：200 {success:true,data} / 4xx|500 {success:false,error,code?}。
 * SSE：GET /events 推送台账变更（revision + kind）。
 *
 * 闸门在此强制执行：move 的 actor 经 protocol 断言，人工闸门拒绝 agent/system。
 *
 * @module dashboard-requirement/host/routes
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
} from '../shared/protocol.js'

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
      return { tasks: [record] }
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
      return { tasks: [task] }
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
      return { tasks: [task] }
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

      json(res, 404, { success: false, error: `未知路由：${method} ${url.pathname}`, code: 'not_found' })
    } catch (err) {
      fail(res, err)
    }
  }
}
