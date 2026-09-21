/**
 * Stages 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * @module dsh-pmboard/http/routers/Stages
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  asStageKey,
  readyTasks,
  totalTokens,
  windowCodeFromSessionId,
  type RequirementRecord,
  type TaskRecord,
} from '../../shared/protocol.js'
import { syncAllReqArtifacts, syncReqArtifacts } from '../../adapters/ArtifactSync.js'
import { assembleStageDetail, assembleStageOverview } from '../../application/query/QueryStageDetail.js'
import { designDocPolicyOf } from '../../application/internal/design-docs.js'
import { assembleRequirementToken, requirementTotalTokens } from '../../application/query/QueryRequirementToken.js'
import { assembleRequirementMarks } from '../../application/query/QueryRequirementMarks.js'
import { FileDocRepository } from '../../adapters/FileDocRepository.js'
import {
  injectionWindowsOf,
  summarizeInjections,
  summarizeSystemPrompt,
  unavailableSystemPromptCost,
} from '../../application/internal/prompt-cost.js'
import { countDoneTasks, countUnfinishedTasks, isActiveRequirement, isOpenRequirement } from '../../domain/status/Predicates.js'
import { TASK_STATUS_ORDER } from '../../domain/task/TaskStatus.js'
import { fmt } from '../../domain/text/fmt.js'
import type { RouterCtx } from './shared.js'

export function createStagesRouter(ctx: RouterCtx) {
  const { store, ok, deps } = ctx

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
      // REQ-a33899：需求卡面累计 token。**无快照的需求不出现该键**（缺失 ≠ 0）。
      tokenTotals: Object.fromEntries(
        ledger.requirements
          .map(r => [r.id, requirementTotalTokens(r)] as const)
          .filter(([, v]) => v !== undefined),
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

  /**
   * GET /dashboard/api/reqboard/requirements/summary
   * 进行中需求的紧凑摘要（侧边栏下拉 / 列表视图共用）：
   * 标题 / 状态 / 来源窗口码 / 任务进度。按「越靠后越靠前」排序。
   */
  async function handleRequirementsSummary(res: ServerResponse): Promise<void> {
    const ledger = await store.read(l => l)
    const rank: Record<string, number> = {
      implementing: 0, accepting: 1, decomposing: 2, design: 3, brainstorming: 4, draft: 5, done: 6,
    }
    const summaries = ledger.requirements
      .filter(r => isActiveRequirement(r))
      .map(req => {
        const tasks = ledger.tasks.filter(t => t.requirementId === req.id)
        const done = countDoneTasks(tasks)
        const active = countUnfinishedTasks(tasks)
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
    // 进行中判据取自 domain（此前这里引用未定义的 OPEN_STATUSES → 运行时 500）
    const isOpen = (s: string): boolean => isOpenRequirement({ status: s })
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
    const done = countDoneTasks(tasks)
    const byStatus: Record<string, number> = {}
    for (const s of TASK_STATUS_ORDER) byStatus[s] = 0
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
        active: countUnfinishedTasks(tasks),
        percentage: tasks.length > 0 ? Math.round((done / tasks.length) * 100) : 0,
        byStatus,
      },
      // 状态时间线（谁在什么时候推进到哪一步）——折叠展开后的「做了什么」主线
      timeline: (target.statusHistory ?? []).map(e => ({
        status: e.status, at: e.at, by: e.by, reason: e.reason ?? null, inferred: e.inferred === true,
      })),
      // REQ-a33899：每个流程节点的 token。口径与详情页一致：节点有快照用节点差值；
      // 节点无快照但任务执行有差值时用执行差值兜底——否则功能上线前创建的需求
      // 在会话顶部一个数字都不显示（用户实测反馈）。total=0 的节点不输出 tokens（避免一排 0）。
      nodes: nodeTokensOf(target, tasks),
      tasks: tasks
        .slice()
        .sort((a, b) => (TASK_STATUS_ORDER.indexOf(a.status) - TASK_STATUS_ORDER.indexOf(b.status)) || (a.createdAt - b.createdAt))
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
   * GET /dashboard/api/reqboard/requirements/:id/stage/:stage
   * 节点详情（REQ-31e11f t2）：模板装配器产出 StageDetail 判别联合（含产物与
   * 确认状态、分类跳过态、时间线切片）。需求不存在 → 404；stage 非法 → 400。
   * 薄适配：校验 → 读台账 → assembleStageDetail → ok。
   */
  async function handleStageDetail(res: ServerResponse, id: string, stageRaw: string): Promise<void> {
    await syncReqArtifacts(store, id, deps.cwd).catch(() => { /* 扫描失败不阻断详情 */ })
    const stage = asStageKey(stageRaw) // 非法 → code=invalid_input → 400
    // REQ-2d1c74 FR-1/FR-2：host 侧读 requirement.md front-matter 注入设计文档策略（client 不碰 fs）
    const docs = new FileDocRepository(deps.cwd !== undefined ? { workspaceRoot: deps.cwd } : {})
    const target = (await store.read(l => l)).requirements.find(r => r.id === id)
    const policy = target === undefined ? undefined : await designDocPolicyOf(docs, target)
    const detail = await store.read(ledger =>
      assembleStageDetail(ledger.requirements.find(r => r.id === id), { tasks: ledger.tasks }, stage, { ...(policy !== undefined ? { designDocPolicy: policy } : {}) }),
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
    const docs = new FileDocRepository(deps.cwd !== undefined ? { workspaceRoot: deps.cwd } : {})
    const target = (await store.read(l => l)).requirements.find(r => r.id === id)
    const policy = target === undefined ? undefined : await designDocPolicyOf(docs, target)
    const overview = await store.read(ledger =>
      assembleStageOverview(ledger.requirements.find(r => r.id === id), { tasks: ledger.tasks }, { ...(policy !== undefined ? { designDocPolicy: policy } : {}) }),
    )
    ok(res, overview)
  }

  /**
   * GET /dashboard/api/reqboard/requirements/:id/token
   * 单需求的 token 去向（REQ-a33899）：byStage + 任务执行下钻；不存在 → 404。
   */
  /** 固定系统提示词成本：读时装配；服务不可得或装配抛错 → source=unavailable（不猜）。 */
  async function systemPromptCostOf(provider: (() => unknown) | undefined) {
    const svc = provider?.() as { assemble?: (ctx?: unknown) => Promise<unknown> } | undefined
    if (typeof svc?.assemble !== 'function') return unavailableSystemPromptCost()
    try {
      // turns 暂不可得（会话回合统计未接入本接口）→ 不猜累计，只给每回合成本
      return summarizeSystemPrompt(await svc.assemble(), 0)
    } catch {
      return unavailableSystemPromptCost()
    }
  }

  async function handleRequirementToken(res: ServerResponse, id: string): Promise<void> {
    const ledger = await store.read(l => l)
    const req = ledger.requirements.find(r => r.id === id)
    if (req === undefined) {
      throw Object.assign(new Error(fmt('需求 {id}不存在', { id })), { code: 'not_found' })
    }
    const view = assembleRequirementToken(req, { tasks: ledger.tasks })
    // REQ-a33899 t5：提示词成本（读时装配，不落台账）
    view.systemPrompt = await systemPromptCostOf(deps.systemPrompt)
    const entries = deps.injectionLog !== undefined ? await deps.injectionLog.readAll().catch(() => []) : []
    const windows = injectionWindowsOf([
      req.sourceSessionId,
      req.reviewSessionId,
      ...ledger.tasks.filter(t => t.requirementId === req.id).flatMap(t => t.executions.map(e => e.sessionId)),
    ])
    const injections = summarizeInjections(entries, windows)
    const totals = totalTokens(view.totals)
    if (totals > 0) injections.sharePct = Math.round((injections.estTokens / totals) * 1000) / 10
    view.injections = injections
    ok(res, view)
  }

  /**
   * 每节点 token（REQ-a33899）：与详情页同口径——节点快照优先，缺失时用该节点任务执行差值兜底。
   * total=0 的节点只给 key（前端显示节点名，不显示 0）。
   */
  function nodeTokensOf(req: RequirementRecord, reqTasks: readonly TaskRecord[]): Array<{ key: string; tokens?: { total: number } }> {
    const view = assembleRequirementToken(req, { tasks: reqTasks })
    return view.byStage.map((row) => {
      const total = row.buckets !== undefined
        ? totalTokens(row.buckets)
        : row.executions.reduce((n, e) => n + (e.delta !== undefined ? totalTokens(e.delta) : 0), 0)
      return total > 0 ? { key: row.stage, tokens: { total } } : { key: row.stage }
    })
  }

  /**
   * 需求侧接收标记（REQ-d3e61a T-5）：逐条功能点显示「谁接了 / 还没人接」。
   * 判据（条款清单 + 任务↔条款绑定）只存在于文档，client 拿不到，故必须服务端算。
   */
  async function handleRequirementMarks(res: ServerResponse, id: string): Promise<void> {
    const ledger = await store.read(l => l)
    const req = ledger.requirements.find(r => r.id === id)
    if (req === undefined) {
      throw Object.assign(new Error(fmt('需求 {id}不存在', { id })), { code: 'not_found' })
    }
    // 路由层的 deps 只有 cwd（无 docs 端口，且不许出现状态字面量——过滤下沉到 application 层）
    const docs = new FileDocRepository(deps.cwd !== undefined ? { workspaceRoot: deps.cwd } : {})
    ok(res, await assembleRequirementMarks({ docs }, req, ledger.tasks))
  }

  return { handleState, handleEvents, handleRequirementsSummary, handleSessionProgress, handleStageDetail, handleStageOverview, handleRequirementToken, handleRequirementMarks }
}
