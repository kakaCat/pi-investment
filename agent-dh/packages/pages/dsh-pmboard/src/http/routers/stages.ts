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
  assertArchiveMaterials, assertDagAcyclic, assertReqTransition, assertTaskTransition,
  asActor, asDependsOn, asReqStatus, asStageKey, asScope, asTaskPhase, asTaskSide, asTaskStatus,
  newCommentId, newExecutionId, newRequirementId, newTaskId,
  normalizeText, normalizeTitle, readyTasks, recordStatus, windowCodeFromSessionId,
  type ActorRef, type CommentRecord, type RequirementRecord, type TaskRecord, type TriageRecord,
} from '../../shared/protocol.js'
import { syncAllReqArtifacts, syncReqArtifacts } from '../../adapters/ArtifactSync.js'
import { assembleStageDetail, assembleStageOverview } from '../../application/query/QueryStageDetail.js'
import { countDoneTasks, countUnfinishedTasks, isActiveRequirement, isOpenRequirement } from '../../domain/status/Predicates.js'
import { TASK_STATUS_ORDER } from '../../domain/task/TaskStatus.js'
import type { RouterCtx } from './shared.js'

export function createStagesRouter(ctx: RouterCtx) {
  const { store, now, ids, mintId, ok, fail, json, readBody, badInput, notFound, deps } = ctx

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

  return { handleState, handleEvents, handleRequirementsSummary, handleSessionProgress, handleStageDetail, handleStageOverview }
}
