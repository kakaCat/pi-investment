/**
 * Requirements 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * @module dsh-pmboard/http/routers/Requirements
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  assertReqTransition,
  asActor,
  asReqStatus,
  normalizeText,
  normalizeTitle,
  recordStatus,
  type ActorRef,
  type CommentRecord,
  type RequirementRecord,
} from '../../shared/protocol.js'
import { assertArtifactGates } from '../../application/internal/artifact-gates.js'
import { transitionRequirement } from '../../application/internal/token-usage.js'
import { INITIAL_REQ_STATUS, canReqTransition } from '../../domain/requirement/RequirementStatus.js'
import { gateFromStage } from '../../domain/gate/GateCatalog.js'
import { fmt } from '../../domain/text/fmt.js'
import type { RouterCtx } from './shared.js'

export function createRequirementsRouter(ctx: RouterCtx) {
  const { store, now, ids, mintId, ok, readBody, badInput, notFound } = ctx

  /** 解析在线 agent（未装配 / 不在线 / 查询抛错 → undefined，一律视为离线）。 */
  function onlineAgent(windowKey: string | undefined): unknown {
    if (windowKey === undefined || windowKey.length === 0) return undefined
    const agents = ctx.deps.agents?.()
    if (typeof agents?.get !== 'function') return undefined
    try {
      return agents.get(windowKey) ?? undefined
    } catch {
      return undefined
    }
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
      status: INITIAL_REQ_STATUS,
      blocked: false,
      comments: [],
      version: 1,
      createdAt: nowTs,
      updatedAt: nowTs,
      createdBy: actor,
      updatedBy: actor,
    }
    recordStatus(record, INITIAL_REQ_STATUS, nowTs, actor, '创建（看板人工建卡）')
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
   * 计划裁决（仅人）：批准 / 退回需求的拆分计划。
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
      const plan = r.plan ?? notFound("需求 " + id + " 的拆分计划")
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
        ?? badInput("需求 " + id + " 没有 kind=" + kind + " 的产物（须先由工具登记）")
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
    const confirmed = result.changed.requirements[0] as RequirementRecord

    // ── 确认即推进 + 链侧投递（REQ-e3b6a0 t9 / FR-9）────────────────────────
    // 两者都以「绑定窗口在线」为前提：窗口不在线就只落章，并如实说明——不伪造推进成功。
    const windowKey = confirmed.sourceSessionId
    const agent = onlineAgent(windowKey)
    if (agent === undefined) {
      ok(res, { ...confirmed, advanced: false, delivered: false, note: '窗口不在线，请回会话推进（本次仅落章）' })
      return
    }

    const gate = gateFromStage(confirmed.status)
    let advanced = false
    // 护栏：确认的产物必须**正是该门要求的产物**（gate.requiredKind === kind）。
    // 否则二次确认同一产物会顺着新状态的门再推进一次（B 后再点一次 = 连跳两格）。
    const gateMatches = gate !== undefined && gate.requiredKind === kind
    if (gateMatches && gate.autoAdvance && gate.from !== undefined && canReqTransition(gate.from, gate.to)) {
      await store.mutate('requirement-moved', (ledger) => {
        const r = ledger.requirements.find(x => x.id === id) ?? notFound(fmt('需求 {id}', { id }))
        if (r.status !== gate.from) return undefined // 并发下已推进过 → 幂等，不重复推进
        transitionRequirement(r, gate.to, {
          at: now(),
          actor: { kind: 'human' },
          reason: fmt('看板确认即推进（{from} → {to}）', { from: gate.from, to: gate.to }),
        })
        r.comments.push({
          id: ids.comment(),
          body: fmt('[自动推进] {from} → {to}：看板一键确认产物（kind={kind}）', { from: gate.from, to: gate.to, kind }),
          createdAt: now(),
          createdBy: { kind: 'human' },
        })
        return { requirements: [r] }
      })
      advanced = true
    }

    let delivered = false
    let note: string | undefined
    const chain = ctx.deps.gateChain
    if (chain === undefined) {
      note = '闸门后置链未装配：本次仅落章与推进，未触发压缩/注入/唤醒'
    } else if (!gateMatches || windowKey === undefined) {
      note = fmt('当前状态 {s} 与已确认产物 kind={kind} 不构成闸门，未触发后置链', { s: confirmed.status, kind })
    } else {
      chain.enqueue({
        windowKey,
        gate: gate.id,
        ...(gate.from === undefined ? {} : { from: gate.from }),
        to: gate.to,
        requirementId: id,
        verdict: 'affirmative',
        answers: [{ id: 'board-confirm', selected: [fmt('确认 {kind}', { kind })] }],
        decidedAt: now(),
      })
      const run = await chain.runPending(windowKey, (agent as { session?: unknown }).session)
      delivered = run.ran
      note = delivered ? undefined : '链路未执行（无待处理闸门或幂等命中）'
    }

    const final = store.snapshot().requirements.find(r => r.id === id) ?? confirmed
    ok(res, { ...final, advanced, delivered, ...(note === undefined ? {} : { note }) })
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

  return { handleReqCreate, handleReqMove, handleReqUpdate, handlePlanDecision, handleArtifactConfirm, handleComment }
}
