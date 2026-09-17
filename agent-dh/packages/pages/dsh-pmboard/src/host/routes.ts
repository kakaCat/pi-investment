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
  asStageKey,
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
import { assembleStageDetail, assembleStageOverview } from './stage-detail.js'
import { syncReqArtifacts, syncAllReqArtifacts } from './sync-artifacts.js'
import { assertArtifactGates } from './artifact-gates.js'
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
  /** 工作区根（REQ-2e9473 t11 产物自动发现扫描 docs/requirements/ 用；缺省 process.cwd()）。 */
  cwd?: string
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
  const status = e.code === 'invalid_input' || e.code === 'invalid_transition' || e.code === 'invalid_dag'
    || e.code === 'missing_artifact' || e.code === 'artifact_not_confirmed' ? 400
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
    // 产物自动发现（REQ-2e9473 t11/W4）：渲染前同步需求目录，落盘即产物
    await syncAllReqArtifacts(store, deps.cwd).catch(() => { /* 扫描失败不阻断看板 */ })
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
      // ── 分类感知产物闸门（REQ-31e11f t4）：assertReqTransition 之后、写盘之前 ──
      const gate = assertArtifactGates(req, req.status, to)
      if (gate !== undefined) {
        throw Object.assign(new Error(gate.message), { code: gate.code })
      }
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
        plan.approvedVia = 'board'
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
      // REQ-9f4a44：验收通过 → 直接归档（无 done 中转）；退回仍回 implementing
      const to = pass ? 'archived' : 'implementing'
      assertReqTransition(r.status, to, 'human')
      // ── 分类感知产物闸门（REQ-31e11f t4）──
      // accepting>done 的确认门由本路由的人工审核替代：人点 pass 本身就是确认 verification 产物。
      // 所以这里只检查 missing_artifact（产物必须存在），不检查 artifact_not_confirmed。
      if (pass) {
        const artifacts = r.artifacts
        const isLegacy = artifacts === undefined || artifacts.length === 0
        if (!isLegacy) {
          const verArtifact = artifacts.find(a => a.stage === 'accepting' && a.kind === 'verification')
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
      if (status !== 'passed' && status !== 'failed') badInput('verdicts[].status 只能是 passed 或 failed')
      const opinion = normalizeText(o.opinion, 'verdicts[].opinion', 1000)
      if (status === 'failed' && opinion.length === 0) badInput('不通过的验收项必须写意见（opinion）')
      return { itemId, status, opinion }
    })
    const nowTs = now()
    const result = await store.mutate('requirement-updated', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound('需求 ' + id)
      if (r.status !== 'accepting' && r.status !== 'implementing') {
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
        if (verdict.status === 'failed') failed.push({ item })
      }
      const pendingCount = sheet.items.filter(i => i.status === 'pending').length
      // 返工回路：有不通过项 → 打回 implementing + 为每个未过项生成关联返工任务
      const reworkTaskIds: string[] = []
      if (failed.length > 0 && r.status === 'accepting') {
        assertReqTransition(r.status, 'implementing', 'human')
        for (const { item } of failed) {
          const orig = ledger.tasks.find(t => t.id === item.source)
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
            context: '承接自 ' + (item.source === 'requirement' ? '需求级验收项' : '任务 ' + item.source) + '；验收意见：' + (item.opinion ?? ''),
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
          recordStatus(task, 'todo', nowTs, { kind: 'human' }, '验收不通过 → 自动生成返工任务（t14）')
          ledger.tasks.push(task)
        }
        r.status = 'implementing'
        r.version += 1
        r.updatedAt = nowTs
        r.updatedBy = { kind: 'human' }
        recordStatus(r, 'implementing', nowTs, { kind: 'human' }, '验收单 '+failed.length+' 项不通过 → 打回返工（自动生成 ' + reworkTaskIds.length + ' 个返工任务）')
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
        const passed = sheet.items.filter(i => i.status === 'passed').length
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
      pending: sheet?.items.filter(i => i.status === 'pending').length ?? 0,
      passed: sheet?.items.filter(i => i.status === 'passed').length ?? 0,
      failed: sheet?.items.filter(i => i.status === 'failed').length ?? 0,
      rework_tasks: result.changed.tasks.map(t => t.id),
      note: result.changed.tasks.length > 0
        ? '有不通过项：需求已打回 implementing，生成 ' + result.changed.tasks.length + ' 个返工任务'
        : ((sheet?.items.every(i => i.status === 'passed') ?? false)
            ? '全部通过 → 请点「验收通过」归档（人工门）'
            : '裁决已记录（挂起中，可稍后从断点续验）'),
    })
  }

  // （REQ-9f4a44）原 handleArchive（人点归档 done→archived）已移除：
  // 验收通过即自动归档，归档材料由 reqboard_archive_submit 在 archived 下补齐并落章，
  // 不再存在"人点归档"这一动作。

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

  /**
   * GET /dashboard/api/reqboard/requirements/:id/stage/:stage
   * 节点详情（REQ-31e11f t2）：模板装配器产出 StageDetail 判别联合（含产物与
   * 确认状态、分类跳过态、时间线切片）。需求不存在 → 404；stage 非法 → 400。
   * 薄适配：校验 → 读台账 → assembleStageDetail → ok。
   */
  async function handleStageDetail(res: ServerResponse, id: string, stageRaw: string): Promise<void> {
    await syncReqArtifacts(store, id, deps.cwd).catch(() => { /* 扫描失败不阻断详情 */ })
    const stage = asStageKey(stageRaw) // 非法 → code=invalid_input → 400
    const detail = await store.read(ledger =>
      assembleStageDetail(ledger.requirements.find(r => r.id === id), { tasks: ledger.tasks }, stage),
    )
    ok(res, detail)
  }

  /**
   * GET /dashboard/api/reqboard/requirements/:id/stages
   * 全流程一览（REQ-31e11f 节点详情重设计）：一次返回全部节点 StageDetail +
   * 当前节点，client 监控时间线一次渲染，免去逐节点点击加载。需求不存在 → 404。
   */
  async function handleStageOverview(res: ServerResponse, id: string): Promise<void> {
    await syncReqArtifacts(store, id, deps.cwd).catch(() => { /* 扫描失败不阻断概览 */ })
    const overview = await store.read(ledger =>
      assembleStageOverview(ledger.requirements.find(r => r.id === id), { tasks: ledger.tasks }),
    )
    ok(res, overview)
  }

  /**
   * POST /dashboard/api/reqboard/req/artifact/confirm
   * 产物人工确认（REQ-31e11f t4，五道人工确认门）：人在看板一键确认某 kind 的产物。
   * 仅 human actor 可调（参照既有 plan/approve 的 human 判定——路由层 actor 默认 human）。
   * 确认后该门放行：req.artifacts 里该 kind 产物写 confirmedAt=now / confirmedBy={kind:'human'}。
   */
  async function handleArtifactConfirm(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const kind = normalizeText(body.kind, 'kind', 64)
    if (kind.length === 0) badInput('kind 不能为空')
    const result = await store.mutate('requirement-updated', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id) ?? notFound("需求 " + id)
      const artifact = (r.artifacts ?? []).find(a => a.kind === kind)
      if (artifact === undefined) {
        badInput("需求 " + id + " 没有 kind=" + kind + " 的产物（须先由工具登记）")
      }
      artifact.confirmedAt = now()
      artifact.confirmedBy = { kind: 'human' }
      artifact.confirmedVia = 'board'
      r.comments.push({
        id: ids.comment(),
        body: '[产物确认] 人已确认产物（kind=' + kind + '）：' + artifact.path,
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
      if (method === 'GET' && /^requirements\/[^/]+\/stages$/.test(sub)) {
        const id = decodeURIComponent(sub.split('/')[1] ?? '')
        if (id.length === 0) {
          return json(res, 400, { success: false, error: '缺少 id 参数', code: 'invalid_input' })
        }
        return await handleStageOverview(res, id)
      }
      if (method === 'GET' && /^requirements\/[^/]+\/stage\/[^/]+$/.test(sub)) {
        const parts = sub.split('/')
        const id = decodeURIComponent(parts[1] ?? '')
        const stage = decodeURIComponent(parts[3] ?? '')
        if (id.length === 0 || stage.length === 0) {
          return json(res, 400, { success: false, error: '缺少 id 或 stage 参数', code: 'invalid_input' })
        }
        return await handleStageDetail(res, id, stage)
      }
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
      // 验收单逐项裁决（REQ-2e9473 t14/W6）
      if (method === 'POST' && sub === 'req/verdicts') return await handleVerdicts(req, res)
      // （REQ-9f4a44）req/archive 已移除：归档自动化，无需人工触发
      if (method === 'POST' && sub === 'req/plan/approve') return await handlePlanDecision(req, res, true)
      if (method === 'POST' && sub === 'req/plan/reject') return await handlePlanDecision(req, res, false)
      if (method === 'POST' && sub === 'req/artifact/confirm') return await handleArtifactConfirm(req, res)
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
