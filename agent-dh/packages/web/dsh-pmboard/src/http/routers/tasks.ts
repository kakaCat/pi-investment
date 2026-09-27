/**
 * Tasks 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * REQ-260927202051-f6df（队列为任务唯一存储）：三个入口一律走
 * **「先 taskStore.mutate/createMany（任务）→ 再 repo.mutate（需求 + rollup）」** 的顺序契约
 * （design/interfaces.md I-11）。反序会出现"需求已推进但任务未落"的悬空态，且 v9 台账已无
 * `tasks` 键，`LedgerView.tasks` 一读即为空 —— 故任务读写一律经 TaskStore，绝不碰台账任务。
 *
 * @module dsh-pmboard/http/routers/Tasks
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  assertDagAcyclic,
  asActor,
  asDependsOn,
  asScope,
  asTaskPhase,
  asTaskSide,
  asTaskStatus,
  newExecutionId,
  normalizeText,
  normalizeTitle,
  recordStatus,
  type TaskRecord,
} from '../../shared/protocol.js'
import { applyTaskRollup, type RollupContext } from '../../application/internal/rollup.js'
import { closeExecutions, openExecution } from '../../application/internal/token-usage.js'
import { transitionTask } from '../../application/internal/task-transition.js'
import { endsExecutionSegment, isRollbackOrCancel, startsExecutionSegment } from '../../domain/status/Predicates.js'
import { INITIAL_TASK_STATUS } from '../../domain/task/TaskStatus.js'
import type { RouterCtx } from './shared.js'
import { syncRTMYamlWithSnapshot } from '../../application/internal/rtm-yaml.js'

export function createTasksRouter(ctx: RouterCtx) {
  const { store, taskStore, now, ids, mintId, ok, readBody, notFound } = ctx

  /**
   * 请求体可选会话码（REQ-260927121324-abde t4）：看板操作带上真实 agent 会话才有写时快照。
   * 缺省 / 空串 → undefined（无会话，诚实降级，禁止编造）。
   */
  function sessionIdOf(body: Record<string, unknown>): string | undefined {
    return normalizeText(body.sessionId, 'sessionId', 128) || undefined
  }

  /**
   * 会话码 → 写时快照（快照是旁路证据，缺省一律不传，不写任何 token 字段）。
   * 建卡 / 流转 / 改卡三个入口共用同一口径，保证「无会话不伪造」。
   */
  function snapshotOf(sessionId: string | undefined) {
    return sessionId !== undefined ? ctx.deps.tokenSnapshot?.(sessionId) : undefined
  }

  /** 派生推进（rollup）的快照提供者：有会话才给，无会话不传（FR-6）。 */
  function rollupSnapshot(sessionId: string | undefined) {
    return sessionId !== undefined ? () => ctx.deps.tokenSnapshot?.(sessionId) : undefined
  }

  /**
   * rollup 上下文（三入口共用口径）。
   * REQ-260927121324-abde t4：建卡/流转/改卡共用同一快照提供者（有会话才给，无会话不伪造）。
   */
  function rollupCtx(sessionId: string | undefined): RollupContext {
    return { now: now(), commentId: () => ids.comment(), snapshot: rollupSnapshot(sessionId) }
  }

  async function handleTaskCreate(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const requirementId = normalizeText(body.requirementId, 'requirementId', 64)
    const sessionId = sessionIdOf(body)
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
    recordStatus(record, INITIAL_TASK_STATUS, nowTs, { kind: 'human' }, '创建（看板人工建卡）')

    // 前置校验（**不落盘**）：需求存在 + DAG 无环。
    // 必须先校验再写队列——否则会给不存在的需求建出 queue.json（createMany 允许建档）。
    if (!store.snapshot().requirements.some(r => r.id === requirementId)) notFound(`需求 ${requirementId}`)
    assertDagAcyclic([...(await taskStore.listByRequirement(requirementId)), record], requirementId)

    // ① 任务写（**先**）：建卡入队列（createMany 允许建档——建卡/拆分是队列的诞生时刻）
    await taskStore.createMany(requirementId, [record])

    // ② 需求写（**后**）：任务集变化 → 重算所属需求完成度（派生推进；有会话才带写时快照）
    const after = await taskStore.listAll()
    await store.mutate('task-created', (ledger) => ({
      requirements: applyTaskRollup(ledger, after, rollupCtx(sessionId), record.requirementId),
    }))
    ok(res, record)
  }

  async function handleTaskMove(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const to = asTaskStatus(body.to)
    const actor = asActor(body.actor ?? 'human')
    const reason = normalizeText(body.reason, 'reason', 500)
    const sessionId = sessionIdOf(body)

    const existing = await taskStore.get(id)
    if (existing === undefined) return notFound(`任务 ${id}`)
    const requirementId = existing.requirementId

    // ① 任务写（**先**）：状态流转 + 执行段开闭 + 评论，全部落在队列任务上
    const changed = await taskStore.mutate(requirementId, (tasks) => {
      const task = tasks.find(t => t.id === id)
      if (task === undefined) return undefined
      // 收敛点：校验 + 状态 + 事件一步到位（原为直接赋值，只有本路由校验过）
      transitionTask(task, to, {
        at: now(),
        actor: { kind: actor, ...(sessionId ? { sessionId } : {}) },
        ...(reason ? { reason } : {}),
      })
      if (startsExecutionSegment(to) && sessionId) {
        task.claimedBy = sessionId
        task.claimedAt = now()
        // 执行快照唯一写入口（REQ-260927121324-abde FR-4）：开工落记录 + 写 start 快照。
        openExecution(
          task,
          { id: newExecutionId(), sessionId, trigger: actor === 'system' ? 'auto' : 'manual', at: now() },
          snapshotOf(sessionId),
        )
      }
      if (endsExecutionSegment(to)) {
        delete task.claimedBy
        delete task.claimedAt
      }
      // 执行段闭合：离开 in_progress 时经唯一入口闭合 running 执行并写 end/delta
      // （甘特图与耗时统计依赖；无会话只闭合记录、不写 token 字段）
      if (!startsExecutionSegment(to)) {
        closeExecutions(
          task,
          { at: now(), outcome: isRollbackOrCancel(to) ? 'cancelled' : 'succeeded' },
          snapshotOf(sessionId),
        )
      }
      if (reason) {
        task.comments.push({ id: ids.comment(), body: `[状态] → ${to}：${reason}`, createdAt: now(), createdBy: { kind: actor } })
      }
      return tasks
    })
    const movedTask = changed[0]

    // ② 需求写（**后**）：派生推进（system）——任务状态落定后重算所属需求（全部实施任务 done → 验收）
    const after = await taskStore.listAll()
    await store.mutate('task-moved', (ledger) => ({
      requirements: applyTaskRollup(ledger, after, rollupCtx(sessionId), requirementId),
    }))

    if (movedTask !== undefined) {
      // RTM 触发点 6（REQ-260926140539-457b FR-2）：任务状态变更 → rtm-implementing 同步
      const rtmRoot = ctx.deps.docs?.workspaceRoot() ?? ctx.deps.cwd
      if (rtmRoot !== undefined) {
        syncRTMYamlWithSnapshot(rtmRoot, store.snapshot(), after, movedTask.requirementId, 'task:status', { taskId: movedTask.id })
      }
    }
    ok(res, movedTask)
  }

  async function handleTaskUpdate(req: IncomingMessage, res: ServerResponse): Promise<void> {
    const body = await readBody(req)
    const id = normalizeText(body.id, 'id', 64)
    const sessionId = sessionIdOf(body)

    const existing = await taskStore.get(id)
    if (existing === undefined) return notFound(`任务 ${id}`)
    const requirementId = existing.requirementId

    // ① 任务写（**先**）：改卡字段（DAG 校验在本需求任务集上做）
    const changed = await taskStore.mutate(requirementId, (tasks) => {
      const task = tasks.find(t => t.id === id)
      if (task === undefined) return undefined
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
        assertDagAcyclic(tasks, task.requirementId)
      }
      if (body.blocked !== undefined) {
        task.blocked = Boolean(body.blocked)
        task.blockedReason = task.blocked ? normalizeText(body.blockedReason, 'blockedReason', 300) : undefined
      }
      task.version += 1
      task.updatedAt = now()
      task.updatedBy = { kind: 'human' }
      return tasks
    })
    const updatedTask = changed[0]

    // ② 需求写（**后**）：取消/依赖变更都可能改变完成度 → 重算所属需求（有会话才带写时快照）
    const after = await taskStore.listAll()
    await store.mutate('task-updated', (ledger) => ({
      requirements: applyTaskRollup(ledger, after, rollupCtx(sessionId), requirementId),
    }))
    ok(res, updatedTask)
  }

  return { handleTaskCreate, handleTaskMove, handleTaskUpdate }
}
