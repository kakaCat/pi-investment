/**
 * AdvanceTool（REQ-4842fe t10；REQ-260927144541-0481 FR-1/FR-2/FR-6）——工具名 reqboard_task_run。
 *
 * 事件链的**唯一对外入口**：一次调用推进当前 ready 的一张子卡（一次独立 workflow run），
 * 并在链尾自动收尾 / rollup。工具壳只做协议转换与窗口绑定校验，编排全在 AdvanceChain 用例。
 *
 * REQ-260927144541-0481 三处收口（P1/P2/P3）：
 *  ① 参数支持 requirement_id（与 task_id 至少给一个）——此前只吃父卡 id，实际推进**整个需求**，
 *     "传 A 跑 B"的语义只写在注释里，接口上看不出来；
 *  ② 返回体与 output.schema 逐键对齐——此前声明 subtask_executed/blocked/stopped，实际返回
 *     job_id/run_id/running，绑定层按 additionalProperties:false 会**拒收回执**；
 *  ③ autoRun 副作用显式写进工具描述（此前"悄悄开链"）。
 *
 * 纪律：工具壳不得出现状态字面量比较（tools-dispatch / layer-boundary 门禁）——状态判断一律走 application。
 *
 * @module dsh-pmboard/tools/AdvanceTool/AdvanceTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { advanceRequirement, progressOf } from '../../application/use-cases/AdvanceChain.js'
import { runningSubtaskIds, selectAdvanceEvent } from '../../application/internal/advance-select.js'
import { openRequirementsFor } from '../../application/internal/window.js'
import { fmt } from '../../domain/text/fmt.js'
import { ADVANCE_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'
import { moveSummary } from '../render-summaries.js'

interface AdvanceParams {
  task_id?: string
  requirement_id?: string
}

/** 统一的"未执行"返回体（键与 output.schema 对齐，error 文本内嵌错误码）。 */
function errorOut(taskId: string, requirementId: string, code: string, detail: string): Record<string, unknown> {
  return { success: false, task_id: taskId, requirement_id: requirementId, status: 'error', error: detail, code }
}

export function defineAdvanceTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_run',
    description: ADVANCE_PROMPT,
    parameters: {
      task_id: { type: 'string', description: '父卡 id（t-xxxxxx）；与 requirement_id 至少给一个（用于绑定与目标校验）' },
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；缺省 = 由 task_id 反查，或取本窗口绑定需求' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          requirement_id: { type: 'string' },
          status: { type: 'string', description: 'dispatched=已投递后台任务 / error=未执行' },
          job_id: { type: 'string' },
          run_id: { type: 'string' },
          running: { type: 'array', items: { type: 'string' }, description: '当前在跑的子卡 id' },
          next_ready: { type: 'array', items: { type: 'string' }, description: '下一批 ready 的任务 id' },
          chain: { type: 'object', additionalProperties: true, description: '子卡链进度 { done, total }' },
          parent_status: { type: 'string' },
          error: { type: 'string' },
          code: { type: 'string' },
        },
      },
      render: renderSmart(moveSummary),
    },
    // FR-6 超时归位（REQ-260927144541-0481）：投递类工具只做「认领 + 投递」即返回，
    // 不再挂 1 小时交互档——交互档只服务需要人作答的弹框类（AskConfirm/AcceptSheet）。
    // 此前用交互档是为救「deps.jobs 未装配时的同步兼容路径」，该根因已于 2026-09-27 17:35
    // 修复（DshJobsAdapter 接上 JobsPort）：同步路径只剩内存测试 / 嵌入调用，不代表线上路径。
    timeoutMs: LIMITS.timeoutWriteMs,
    async execute(args: AdvanceParams, exec: unknown): Promise<Record<string, unknown>> {
      const windowKey = deps.session.windowKey(exec)
      const snap = deps.repo.snapshot()
      const bound = openRequirementsFor(snap, windowKey)
      const taskId = typeof args.task_id === 'string' ? args.task_id : ''
      let requirementId = typeof args.requirement_id === 'string' ? args.requirement_id : ''

      // 目标需求解析：显式 requirement_id（须绑定）→ task_id 反查（须绑定）→ 本窗口绑定需求。
      if (requirementId.length > 0) {
        if (!bound.some((r) => r.id === requirementId)) {
          return errorOut(taskId, requirementId, 'REQBOARD_NOT_BOUND_TO_WINDOW',
            fmt('需求 {id} 不属于本窗口绑定的需求', { id: requirementId }))
        }
      } else if (taskId.length > 0) {
        // 任务来自队列（REQ-260927202051-f6df）：v9 台账已无 tasks。
        const task = deps.taskStore === undefined ? undefined : await deps.taskStore.get(taskId)
        if (task === undefined) {
          return errorOut(taskId, '', 'REQBOARD_TASK_NOT_FOUND', fmt('任务不存在：{id}', { id: taskId }))
        }
        if (!bound.some((r) => r.id === task.requirementId)) {
          return errorOut(task.id, task.requirementId, 'REQBOARD_NOT_BOUND_TO_WINDOW', '任务不属于本窗口绑定的需求')
        }
        requirementId = task.requirementId
      } else {
        const first = bound[0]
        if (first === undefined) {
          return errorOut('', '', 'REQBOARD_NO_BOUND_REQ', '本窗口未绑定需求，请传 task_id 或 requirement_id')
        }
        requirementId = first.id
      }

      // 显式触发 = 开启自动链（等价于"推倒第一张骨牌"）；已开启则保持不变。该副作用已写进工具描述。
      if (snap.requirements.find((r) => r.id === requirementId)?.autoRun !== true) {
        await deps.repo.mutate('task-run-autorun', (ledger) => {
          const req = ledger.requirements.find((r) => r.id === requirementId)
          if (req === undefined) return undefined
          req.autoRun = true
          return { requirements: [req] }
        })
      }

      // REQ-260925110957-552d: advanceRequirement 已改为投递式，立即返回
      const out = await advanceRequirement(deps, requirementId, exec)

      // 失败要响亮：**只要不是明确 dispatched**，一律走结构化错误回执。
      // 判别式从 `=== false` 收紧为 `!== true`（2026-09-28 实测）：早退路径（in-flight / 锁在跑 /
      // 终态 / 需求不存在）此前不设 dispatched，会漏过 `=== false` 掉进成功分支，返回
      // job_id/run_id=undefined —— undefined 不是 lossless JSON，dsh-tools 的 snapshotJsonValue
      // 会把它整体转成无信息的 "value is not lossless JSON" 硬错误，agent 只能猜。
      // 现在每种 stopped 都映射到可检索的 code + 人话 reason，回执键全为字符串。
      if (out.dispatched !== true) {
        const code = out.reason?.includes('jobs')
          ? 'DSH_JOBS_UNAVAILABLE'
          : out.stopped === 'locked'
            ? 'REQBOARD_ADVANCE_LOCKED'
            : out.stopped === 'not_found'
              ? 'REQBOARD_REQ_NOT_FOUND'
              : out.stopped === 'not_autorun'
                ? 'REQBOARD_NOT_AUTORUN'
                : out.stopped === 'terminal'
                  ? 'REQBOARD_REQ_TERMINAL'
                  : 'REQBOARD_DISPATCH_FAILED'
        return errorOut(taskId, requirementId, code, out.reason ?? fmt('推进未投递（stopped={s}）', { s: out.stopped }))
      }

      // 投递成功：立即返回（不等执行完成）。
      // 任务来自队列（REQ-260927202051-f6df）：v9 台账已无 tasks，`{ tasks }` 视图一律用队列任务。
      const afterTasks = deps.taskStore === undefined ? [] : await deps.taskStore.listAll()
      const after = { tasks: afterTasks }
      const progress = progressOf(after, requirementId)
      const sel = selectAdvanceEvent(after, requirementId, LIMITS.advanceMaxParallelParents)
      const nextReady = sel !== undefined && sel.event === 'RUN_SUBTASK' ? [sel.subtaskId ?? ''] : []

      return {
        success: true,
        task_id: taskId,
        requirement_id: requirementId,
        status: 'dispatched',
        // 条件展开：即便上游异常漏字段，也绝不把 undefined 带进回执（见上：undefined 会被绑定层拒收）。
        ...(out.job_id !== undefined ? { job_id: out.job_id } : {}),
        ...(out.run_id !== undefined ? { run_id: out.run_id } : {}),
        running: runningSubtaskIds(after, requirementId),
        next_ready: nextReady,
        chain: { done: progress.subtasksDone, total: progress.subtasksTotal },
        parent_status: afterTasks.find((t) => t.id === taskId)?.status ?? '',
      }
    },
  } as any)
}
