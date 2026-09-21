/**
 * Reqboard 路由薄层（REQ-47939a t7）：/dashboard/api/reqboard 前缀分发。
 * 信封：200 {success:true,data} / 4xx|500 {success:false,error,code?}。
 * SSE：GET /events 推送台账变更（revision + kind）。
 *
 * 本文件 = 组合根（构造 RouterCtx → 实例化 6 个资源路由 → 分发）+ **错误 → HTTP 状态码的
 * 唯一映射点**（fail）。资源处理器在 http/routers/*.ts，只做协议转换。
 *
 * 闸门在此强制执行：move 的 actor 经 protocol/domain 断言，人工闸门拒绝 agent/system。
 *
 * @module dsh-pmboard/http/routes
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { JsonLedgerRepository as ReqboardStore } from '../adapters/JsonLedgerRepository.js'
import { newCommentId, newRequirementId, newTaskId } from '../shared/protocol.js'
import type { InjectionLogReadPort } from '../application/internal/injection-log.js'
import type { RouterCtx } from './routers/shared.js'
import { createRequirementsRouter } from './routers/requirements.js'
import { createTasksRouter } from './routers/tasks.js'
import { createStagesRouter } from './routers/stages.js'
import { createVerdictsRouter } from './routers/verdicts.js'
import { createArtifactsRouter } from './routers/artifacts.js'
import { createTriageRouter } from './routers/triage.js'
import { createInjectionRouter } from './routers/injection.js'

export interface ReqboardRouteDeps {
  store: ReqboardStore
  now: () => number
  /** 注入留痕**只读**端口（REQ-422af1 t11）：看板「本次注入了什么」的数据源；缺省则接口返回空清单。 */
  injectionLog?: InjectionLogReadPort
  /** 系统提示词装配服务提供者（REQ-a33899 t5）：读时折算固定系统提示词成本；缺省 → unavailable。 */
  systemPrompt?: () => unknown
  /** Token 快照提供者（REQ-b545fe t6）：HTTP 任务操作（body.sessionId）可结算快照；缺省 → 无快照。 */
  tokenSnapshot?: (windowKey: string) => import('../shared/protocol.js').TokenSnapshot | undefined
  /** 可注入 id 生成器（测试用） */
  ids?: {
    requirement?: () => string
    task?: () => string
    comment?: () => string
  }
  /** 工作区根（REQ-2e9473 t11 产物自动发现扫描 docs/requirements/ 用；缺省 process.cwd()）。 */
  cwd?: string
  /** 文档仓储（REQ-308b9a AC-7.7：看板裁决后回填 verification.md）。 */
  docs?: import('../application/ports.js').DocRepository
  /** 闸门后置链（REQ-e3b6a0 t9 / FR-9）：看板一键确认后触发 Phase B。缺省 → 只落章。 */
  gateChain?: import('../application/gate/GatePostChain.js').GateChainPort
  /** 在线 agent 查询（取会话句柄供 H2 用）；缺省 → 视为窗口不在线。 */
  agents?: () => { get?: (id: string) => unknown } | undefined
  /**
   * 推进器（REQ-4842fe FR-12 / t-3be71b）：看板控制面「继续」= 置 autoRun=true **并触发一次推进事件**。
   * 缺省 → 只置开关并在响应里如实说明（不伪造"已续跑"）。
   */
  advance?: (requirementId: string) => Promise<{ steps: number; stopped: string }>
}

function json(res: ServerResponse, status: number, body: unknown): void {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify(body))
}

function ok(res: ServerResponse, data: unknown): void {
  json(res, 200, { success: true, data })
}

/**
 * 错误 → HTTP 状态码的**唯一映射点**（t7：此前散在各处理器的 badInput/notFound，
 * 现集中在此）。code 语义对齐 design/domain-model.md §7。
 */
function fail(res: ServerResponse, err: unknown): void {
  const e = err as { message?: string; code?: string }
  const status = e.code === 'invalid_input' || e.code === 'invalid_transition' || e.code === 'invalid_dag'
    // verify_override_required（REQ-a8d582 FR-4）：不合规通过缺覆盖说明 → 400（补上说明可重发）
    || e.code === 'missing_artifact' || e.code === 'artifact_not_confirmed' || e.code === 'verify_override_required'
    // REQ-2d1c74 FR-2/FR-3：G2 完整性门与拆分内容硬门 = 流程不满足（补交/挪内容后可重发）→ 400
    || e.code === 'design_doc_incomplete' || e.code === 'design_contains_decomposition' ? 400
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

  const ctx: RouterCtx = {
    store,
    now,
    deps: {
      ...(deps.cwd !== undefined ? { cwd: deps.cwd } : {}),
      ...(deps.injectionLog !== undefined ? { injectionLog: deps.injectionLog } : {}),
      ...(deps.systemPrompt !== undefined ? { systemPrompt: deps.systemPrompt } : {}),
      ...(deps.tokenSnapshot !== undefined ? { tokenSnapshot: deps.tokenSnapshot } : {}),
      ...(deps.docs !== undefined ? { docs: deps.docs } : {}),
      ...(deps.gateChain !== undefined ? { gateChain: deps.gateChain } : {}),
      ...(deps.agents !== undefined ? { agents: deps.agents } : {}),
      ...(deps.advance !== undefined ? { advance: deps.advance } : {}),
    },
    ids,
    mintId,
    json,
    ok,
    fail,
    badInput,
    notFound,
    readBody,
  }
  const requirements = createRequirementsRouter(ctx)
  const tasks = createTasksRouter(ctx)
  const stages = createStagesRouter(ctx)
  const verdicts = createVerdictsRouter(ctx)
  const artifacts = createArtifactsRouter(ctx)
  const triage = createTriageRouter(ctx)
  const injection = createInjectionRouter(ctx)

  // -- 分发 ----------------------------------------------------------------

  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const url = new URL(req.url ?? '/', 'http://localhost')
      const sub = url.pathname.replace(/^\/dashboard\/api\/reqboard\/?/, '')
      const method = req.method ?? 'GET'

      if (method === 'GET' && (sub === '' || sub === 'state')) return await stages.handleState(res)
      if (method === 'GET' && sub === 'events') return stages.handleEvents(req, res)
      if (method === 'GET' && sub === 'health') return ok(res, { status: 'ok' })
      // 注入留痕只读回查（REQ-422af1 t11）：看板「本次注入了什么」的唯一数据源
      if (method === 'GET' && sub === 'injection-log') return await injection.handleInjectionLog(res, url)
      if (method === 'GET' && sub === 'file') {
        const p = url.searchParams.get('path') ?? ''
        return await artifacts.handleFileRead(res, p)
      }
      if (method === 'GET' && sub === 'requirements/summary') return await stages.handleRequirementsSummary(res)
      if (method === 'GET' && /^requirements\/[^/]+\/token$/.test(sub)) {
        const id = decodeURIComponent(sub.split('/')[1] ?? '')
        if (id.length === 0) {
          return json(res, 400, { success: false, error: '缺少 id 参数', code: 'invalid_input' })
        }
        return await stages.handleRequirementToken(res, id)
      }
      // REQ-d3e61a T-5：需求侧接收标记（看板详情页「未被接收（红）」的数据源）
      if (method === 'GET' && /^requirements\/[^/]+\/marks$/.test(sub)) {
        const id = decodeURIComponent(sub.split('/')[1] ?? '')
        if (id.length === 0) {
          return json(res, 400, { success: false, error: '缺少 id 参数', code: 'invalid_input' })
        }
        return await stages.handleRequirementMarks(res, id)
      }
      if (method === 'GET' && /^requirements\/[^/]+\/stages$/.test(sub)) {
        const id = decodeURIComponent(sub.split('/')[1] ?? '')
        if (id.length === 0) {
          return json(res, 400, { success: false, error: '缺少 id 参数', code: 'invalid_input' })
        }
        return await stages.handleStageOverview(res, id)
      }
      if (method === 'GET' && /^requirements\/[^/]+\/stage\/[^/]+$/.test(sub)) {
        const parts = sub.split('/')
        const id = decodeURIComponent(parts[1] ?? '')
        const stage = decodeURIComponent(parts[3] ?? '')
        if (id.length === 0 || stage.length === 0) {
          return json(res, 400, { success: false, error: '缺少 id 或 stage 参数', code: 'invalid_input' })
        }
        return await stages.handleStageDetail(res, id, stage)
      }
      if (method === 'GET' && sub.startsWith('session/') && sub.endsWith('/progress')) {
        const sid = decodeURIComponent(sub.slice('session/'.length, sub.length - '/progress'.length))
        if (sid.length === 0) return json(res, 400, { success: false, error: '缺少 sessionId', code: 'invalid_input' })
        return await stages.handleSessionProgress(res, sid)
      }

      if (method === 'POST' && sub === 'req/create') return await requirements.handleReqCreate(req, res)
      if (method === 'POST' && sub === 'req/move') return await requirements.handleReqMove(req, res)
      if (method === 'POST' && sub === 'req/update') return await requirements.handleReqUpdate(req, res)
      if (method === 'POST' && sub === 'req/verify/pass') return await verdicts.handleVerifyDecision(req, res, true)
      if (method === 'POST' && sub === 'req/verify/rework') return await verdicts.handleVerifyDecision(req, res, false)
      // 验收单逐项裁决（REQ-2e9473 t14/W6）
      if (method === 'POST' && sub === 'req/verdicts') return await verdicts.handleVerdicts(req, res)
      // （REQ-9f4a44）req/archive 已移除：归档自动化，无需人工触发
      if (method === 'POST' && sub === 'req/plan/approve') return await requirements.handlePlanDecision(req, res, true)
      if (method === 'POST' && sub === 'req/plan/reject') return await requirements.handlePlanDecision(req, res, false)
      // 自动链控制面（REQ-4842fe t-3be71b）：暂停/继续；继续即触发一次推进事件
      if (method === 'POST' && sub === 'req/autorun') return await requirements.handleAutoRun(req, res)
      if (method === 'POST' && sub === 'req/artifact/confirm') return await requirements.handleArtifactConfirm(req, res)
      if (method === 'POST' && sub === 'task/create') return await tasks.handleTaskCreate(req, res)
      if (method === 'POST' && sub === 'task/move') return await tasks.handleTaskMove(req, res)
      if (method === 'POST' && sub === 'task/update') return await tasks.handleTaskUpdate(req, res)
      if (method === 'POST' && sub === 'comment') return await requirements.handleComment(req, res)
      // 文档可打开性批量解析（REQ-b63a7d t4）：前端一次请求替代逐条预检
      if (method === 'POST' && sub === 'docs/resolve') return await artifacts.handleDocsResolve(req, res)

      if (method === 'GET' && sub === 'triage') return await triage.handleTriageList(res)
      if (method === 'POST' && sub === 'triage/confirm') return await triage.handleTriageConfirm(req, res)
      if (method === 'POST' && sub === 'triage/rebind') return await triage.handleTriageRebind(req, res)
      if (method === 'POST' && sub === 'triage/reject') return await triage.handleTriageReject(req, res)

      json(res, 404, { success: false, error: `未知路由：${method} ${url.pathname}`, code: 'not_found' })
    } catch (err) {
      fail(res, err)
    }
  }
}
