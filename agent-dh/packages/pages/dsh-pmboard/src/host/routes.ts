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
  assertArchiveMaterials,
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
  recordStatus,
  windowCodeFromSessionId,
  type ActorRef,
  type CommentRecord,
  type RequirementRecord,
  type TaskRecord,
  type TriageRecord,
} from '../shared/protocol.js'
import { applyTaskRollup } from './rollup.js'
import { readFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'

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

/** 入参/流程不满足 → 400（消息即指引）。 */
function badInput(message: string): never {
  throw Object.assign(new Error(message), { code: 'invalid_input' })
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
    recordStatus(record, 'draft', nowTs, actor, '创建（看板人工建卡）')
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
      recordStatus(req, to, req.updatedAt, { kind: actor }, reason || undefined)
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

  /**
   * 计划裁决（仅人）：批准 / 退回需求的实施计划。
   * 这是 plan mode 的唯一人工闸门——批准 = 允许拆分；退回 = 打回重写（附理由）。
   * 除它之外，评审→拆分→实施→验收全部由窗口 agent 自行推进（2026-09-11 用户裁定）。
   */
  async function handlePlanDecision(req: IncomingMessage, res: ServerResponse, approve: boolean): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const reason = normalizeText(body.reason, 'reason', 500)
    if (!approve && reason.length === 0) {
      throw Object.assign(new Error('退回计划必须写清理由（reason）'), { code: 'invalid_input' })
    }
    const result = await store.mutate('requirement-updated', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound("需求 " + id)
      if (r.plan === undefined) notFound("需求 " + id + " 的实施计划")
      const plan = r.plan
      if (approve) {
        plan.approvedAt = now()
        plan.approvedBy = { kind: 'human' }
        delete plan.rejectedAt
        delete plan.rejectedReason
      } else {
        plan.rejectedAt = now()
        plan.rejectedReason = reason
        delete plan.approvedAt
        delete plan.approvedBy
      }
      r.comments.push({
        id: ids.comment(),
        body: approve
          ? '[计划] 已批准（人）：' + plan.tasks.length + ' 个任务，窗口可拆分落库'
          : '[计划] 已退回（人）：' + reason,
        createdAt: now(),
        createdBy: { kind: 'human' },
      })
      r.version += 1
      r.updatedAt = now()
      r.updatedBy = { kind: 'human' }
      return { requirements: [r] }
    })
    ok(res, result.changed.requirements[0])
  }

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
      if (r.status !== 'accepting') badInput("需求 " + id + " 当前处于 " + r.status + "，不在验收态（先提交验收）")
      const v = r.verification
      if (v === undefined) {
        badInput("需求 " + id + " 还没有验收材料：窗口需先 reqboard_verify_submit 提交证据（做了什么、怎么验的、看到什么）")
      }
      const to = pass ? 'done' : 'implementing'
      assertReqTransition(r.status, to, 'human')
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
   * 归档（仅人）：done → archived。前置：agent 已准备归档材料，且材料符合该需求类型的
   * 文档规范（必填文档 + 合并去向 + 索引条目）——归档不是挪目录，是把产出并进项目文档。
   */
  async function handleArchive(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const result = await store.mutate('requirement-moved', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound("需求 " + id)
      if (r.status !== 'done') badInput("需求 " + id + " 当前处于 " + r.status + "，未完成不能归档")
      const a = r.archive
      if (a === undefined) {
        badInput("需求 " + id + " 还没有归档材料：窗口需先 reqboard_archive_submit 提交需求目录、文档清单、合并去向与索引条目")
      }
      assertArchiveMaterials(r.category, a)
      assertReqTransition('done', 'archived', 'human')
      a.archivedAt = now()
      a.archivedBy = { kind: 'human' }
      r.status = 'archived'
      r.archivePath = a.dir
      r.version += 1
      r.updatedAt = now()
      r.updatedBy = { kind: 'human' }
      recordStatus(r, 'archived', r.updatedAt, { kind: 'human' }, '归档：' + a.indexEntry)
      r.comments.push({
        id: ids.comment(),
        body: '[归档] 已归档（人）：' + a.dir + ' → 合并进 ' + a.mergedInto.join(', '),
        createdAt: now(),
        createdBy: { kind: 'human' },
      })
      return { requirements: [r] }
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
    recordStatus(record, 'todo', nowTs, { kind: 'human' }, '创建（看板人工建卡）')
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
      // 执行段闭合：离开 in_progress 时结算运行中的执行记录（甘特图与耗时统计依赖）
      if (to !== 'in_progress') {
        for (const exec of task.executions) {
          if (exec.outcome === 'running') {
            exec.endedAt = now()
            exec.outcome = to === 'canceled' || to === 'todo' ? 'cancelled' : 'succeeded'
          }
        }
      }
      recordStatus(task, to, task.updatedAt, { kind: actor, ...(sessionId ? { sessionId } : {}) }, reason || undefined)
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

  // -- 会话进度 / 需求摘要（2026-09-15：会话顶部进度条 + 侧边栏下拉）------------

  /** 仍处进行中的需求状态（会话进度锚点用）。 */
  const OPEN_STATUSES: ReadonlySet<string> = new Set([
    'draft', 'brainstorming', 'planning', 'decomposing', 'implementing', 'accepting',
  ])

  /** 任务状态在流水线上的显示顺序（客户端按此分组渲染）。 */
  const TASK_ORDER = ['in_progress', 'integrating', 'testing', 'in_review', 'todo', 'done', 'canceled']

  /**
   * GET /dashboard/api/reqboard/requirements/summary
   * 进行中需求的紧凑摘要（侧边栏下拉 / 列表视图共用）：
   * 标题 / 状态 / 来源窗口码 / 任务进度。按「越靠后越靠前」排序。
   */
  async function handleRequirementsSummary(res: ServerResponse): Promise<void> {
    const ledger = await store.read(l => l)
    const rank: Record<string, number> = {
      implementing: 0, accepting: 1, decomposing: 2, planning: 3, brainstorming: 4, draft: 5, done: 6,
    }
    const summaries = ledger.requirements
      .filter(r => r.status !== 'archived' && r.status !== 'canceled')
      .map(req => {
        const tasks = ledger.tasks.filter(t => t.requirementId === req.id)
        const done = tasks.filter(t => t.status === 'done').length
        const active = tasks.filter(t => t.status !== 'todo' && t.status !== 'done' && t.status !== 'canceled').length
        return {
          id: req.id,
          title: req.title,
          status: req.status,
          category: req.category ?? null,
          sourceSessionId: req.sourceSessionId ?? null,
          windowCode: req.sourceSessionId !== undefined ? windowCodeFromSessionId(req.sourceSessionId) : null,
          tasksDone: done,
          tasksActive: active,
          tasksTotal: tasks.length,
          percentage: tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0,
          updatedAt: req.updatedAt,
        }
      })
      .sort((a, b) => {
        const ra = rank[a.status] ?? 99
        const rb = rank[b.status] ?? 99
        return ra !== rb ? ra - rb : b.updatedAt - a.updatedAt
      })
    ok(res, { requirements: summaries, total: summaries.length })
  }

  /**
   * GET /dashboard/api/reqboard/session/:sessionId/progress
   * 某会话关联的需求进度（会话顶部进度条数据源）。
   *
   * 锚点两级：① 需求 sourceSessionId（立项窗口）；② 任务执行记录 sessionId（接手窗口）。
   * 状态两级：① **进行中**需求优先（进度条主用途）；② 没有进行中的，回退到该会话
   * **最近关联过的需求**（含 done/archived，closed=true）——用户核心诉求是「agent 跑久了
   * 我总忘记之前做了什么」，会话结束后留一条「最近完成」锚点比什么都不显示有用得多。
   * 完全无关联 → { hasRequirement: false }（前端不渲染，零噪音）。
   */
  async function handleSessionProgress(res: ServerResponse, sessionId: string): Promise<void> {
    const ledger = await store.read(l => l)

    // 该会话关联的全部需求 id（来源窗口 ∪ 任务执行会话）
    const isOpen = (s: string): boolean => OPEN_STATUSES.has(s)
    const taskAnchoredIds = new Set<string>()
    for (const t of ledger.tasks) {
      if (t.executions.some(e => e.sessionId === sessionId)) taskAnchoredIds.add(t.requirementId)
    }
    const anchored = ledger.requirements.filter(
      r => r.sourceSessionId === sessionId || taskAnchoredIds.has(r.id),
    )
    const byRecent = (a: RequirementRecord, b: RequirementRecord): number => b.updatedAt - a.updatedAt

    const target = anchored.filter(r => isOpen(r.status)).sort(byRecent)[0]
      ?? anchored.slice().sort(byRecent)[0]

    if (target === undefined) {
      ok(res, { hasRequirement: false, sessionId })
      return
    }

    const tasks = ledger.tasks.filter(t => t.requirementId === target.id)
    const done = tasks.filter(t => t.status === 'done').length
    const byStatus: Record<string, number> = {}
    for (const s of TASK_ORDER) byStatus[s] = 0
    for (const t of tasks) byStatus[t.status] = (byStatus[t.status] ?? 0) + 1

    ok(res, {
      hasRequirement: true,
      sessionId,
      /** true = 该会话没有进行中需求，展示的是最近关联过的已完成需求 */
      closed: !isOpen(target.status),
      requirement: {
        id: target.id,
        title: target.title,
        description: target.description,
        status: target.status,
        category: target.category ?? null,
        blocked: target.blocked,
        paused: target.paused === true,
        sourceSessionId: target.sourceSessionId ?? null,
        updatedAt: target.updatedAt,
      },
      progress: {
        total: tasks.length,
        done,
        active: tasks.filter(t => t.status !== 'todo' && t.status !== 'done' && t.status !== 'canceled').length,
        percentage: tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0,
        byStatus,
      },
      // 状态时间线（谁在什么时候推进到哪一步）——折叠展开后的「做了什么」主线
      timeline: (target.statusHistory ?? []).map(e => ({
        status: e.status, at: e.at, by: e.by, reason: e.reason ?? null, inferred: e.inferred === true,
      })),
      tasks: tasks
        .slice()
        .sort((a, b) => (TASK_ORDER.indexOf(a.status) - TASK_ORDER.indexOf(b.status)) || (a.createdAt - b.createdAt))
        .map(t => ({
          id: t.id,
          title: t.title,
          status: t.status,
          phase: t.phase,
          side: t.side,
          acceptance: t.acceptance,
          updatedAt: t.updatedAt,
          durationMs: t.executions.reduce((s, e) => s + Math.max(0, (e.endedAt ?? e.startedAt) - e.startedAt), 0),
        })),
    })
  }

  /**
   * GET /dashboard/api/reqboard/file?path=xxx
   * 读取工作区 docs/ 下的文档（需求详情页「文档记录」弹窗打开用）。
   * 安全：只允许相对路径、禁止 ../ 与绝对路径、解析后必须落在 docs/ 内。
   */
  async function handleFileRead(res: ServerResponse, rawPath: string): Promise<void> {
    const rel = (rawPath ?? '').trim()
    if (!rel) return badInput('缺少 path 参数')
    if (rel.startsWith('/') || rel.includes('..') || rel.includes('\\')) {
      return json(res, 403, { success: false, error: '仅允许访问工作区 docs/ 目录', code: 'forbidden' })
    }
    const cwd = process.cwd()
    const docsRoot = resolve(cwd, 'docs')
    const target = resolve(cwd, rel)
    if (target !== docsRoot && !target.startsWith(docsRoot + sep)) {
      return json(res, 403, { success: false, error: '仅允许访问工作区 docs/ 目录', code: 'forbidden' })
    }
    try {
      const content = await readFile(target, 'utf8')
      ok(res, { path: rel, content })
    } catch {
      return json(res, 404, { success: false, error: '文件不存在：' + rel, code: 'not_found' })
    }
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
      if (method === 'GET' && sub === 'file') {
        const p = url.searchParams.get('path') ?? ''
        return await handleFileRead(res, p)
      }
      if (method === 'GET' && sub === 'requirements/summary') return await handleRequirementsSummary(res)
      if (method === 'GET' && sub.startsWith('session/') && sub.endsWith('/progress')) {
        const sid = decodeURIComponent(sub.slice('session/'.length, sub.length - '/progress'.length))
        if (sid.length === 0) return json(res, 400, { success: false, error: '缺少 sessionId', code: 'invalid_input' })
        return await handleSessionProgress(res, sid)
      }

      if (method === 'POST' && sub === 'req/create') return await handleReqCreate(req, res)
      if (method === 'POST' && sub === 'req/move') return await handleReqMove(req, res)
      if (method === 'POST' && sub === 'req/update') return await handleReqUpdate(req, res)
      if (method === 'POST' && sub === 'req/verify/pass') return await handleVerifyDecision(req, res, true)
      if (method === 'POST' && sub === 'req/verify/rework') return await handleVerifyDecision(req, res, false)
      if (method === 'POST' && sub === 'req/archive') return await handleArchive(req, res)
      if (method === 'POST' && sub === 'req/plan/approve') return await handlePlanDecision(req, res, true)
      if (method === 'POST' && sub === 'req/plan/reject') return await handlePlanDecision(req, res, false)
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
