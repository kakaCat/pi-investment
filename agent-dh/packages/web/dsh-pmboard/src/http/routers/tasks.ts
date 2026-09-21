/**
 * Tasks 路由（REQ-47939a t7）——从 host/routes.ts 的 createReqboardHandler 内联处理器**逐字搬入**。
 *
 * 只做协议转换（请求体 → 用例/领域判定 → JSON 信封）；状态字面量比较一律经 domain 判定函数
 * （layer-boundary INV-2）。错误 → HTTP 状态码映射集中在本目录 shared.ts 的 fail()。
 *
 * @module dsh-pmboard/http/routers/Tasks
 */
import type { IncomingMessage, ServerResponse } from 'node:http'
import {
  assertDagAcyclic,
  assertTaskTransition,
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
import { applyTaskRollup } from '../../application/internal/rollup.js'
import { endsExecutionSegment, isRollbackOrCancel, startsExecutionSegment } from '../../domain/status/Predicates.js'
import { INITIAL_TASK_STATUS } from '../../domain/task/TaskStatus.js'
import type { RouterCtx } from './shared.js'

export function createTasksRouter(ctx: RouterCtx) {
  const { store, now, ids, mintId, ok, readBody, notFound } = ctx

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
      if (startsExecutionSegment(to) && sessionId) {
        task.claimedBy = sessionId
        task.claimedAt = now()
        task.executions.push({ id: newExecutionId(), sessionId, trigger: actor === 'system' ? 'auto' : 'manual', startedAt: now(), outcome: 'running' })
      }
      if (endsExecutionSegment(to)) {
        delete task.claimedBy
        delete task.claimedAt
      }
      // 执行段闭合：离开 in_progress 时结算运行中的执行记录（甘特图与耗时统计依赖）
      if (!startsExecutionSegment(to)) {
        for (const exec of task.executions) {
          if (exec.outcome === 'running') {
            exec.endedAt = now()
            exec.outcome = isRollbackOrCancel(to) ? 'cancelled' : 'succeeded'
          }
        }
      }
      recordStatus(task, to, task.updatedAt, { kind: actor, ...(sessionId ? { sessionId } : {}) }, reason || undefined)
      if (reason) {
        task.comments.push({ id: ids.comment(), body: `[状态] → ${to}：${reason}`, createdAt: now(), createdBy: { kind: actor } })
      }
      // 派生推进（system）：任务状态落定后重算所属需求（全部实施任务 done → 验收）
      // REQ-b545fe t6: HTTP 任务操作带 sessionId 时传快照提供者
      const advanced = applyTaskRollup(
        ledger,
        {
          now: now(),
          commentId: () => ids.comment(),
          snapshot: sessionId ? () => ctx.deps.tokenSnapshot?.(sessionId) : undefined,
        },
        task.requirementId,
      )
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

  return { handleTaskCreate, handleTaskMove, handleTaskUpdate }
}
