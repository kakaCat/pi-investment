/**
 * RunStatusTool 工具壳（REQ-260925110957-552d t-c031de）——查询实施链运行状态。
 *
 * 投递式调用后的配套查询工具：reqboard_task_run 返回 job_id/run_id 后，
 * 用本工具查询「跑到哪了」（stepIndex/currentSubtaskId/nextReady/jobStatus）。
 *
 * @module dsh-pmboard/tools/RunStatusTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import type { RequirementRecord, TaskRecord } from '../../client/types.js'
import { queryRunStatus } from '../../application/use-cases/QueryRunStatus.js'
import { openRequirementsFor } from '../../application/internal/window.js'
import { RUN_STATUS_PROMPT } from './prompt.js'
import { renderSmart } from '../shared.js'

/** 一句话摘要（renderSmart 用）。 */
function summarize(v: unknown): string {
  const o = (v ?? {}) as Record<string, unknown>
  if (o.success !== true) return '运行态查询未成功：' + String(o.error ?? '')
  const snap = (o.snapshot ?? {}) as Record<string, unknown>
  return '实施链运行态：' + String(o.requirement_id ?? '') + ' · jobStatus=' + String(snap.jobStatus ?? '') + ' · step=' + String(snap.stepIndex ?? '')
}

export function defineRunStatusTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_run_status',
    description: RUN_STATUS_PROMPT,
    // 2026-09-27（REQ-260927100007-b8ba t2/t15）：改用本仓统一的 DSL（parameters + output.render）。
    // 原 inputSchema/outputSchema 是旧式 JSON Schema 写法（含 enum/required），dsh-tools 的 defineTool
    // 在 output 缺失时直接读 output.render 崩溃——把它注册进工具面会让插件装配失败。
    parameters: {
      requirement_id: { type: 'string', description: '需求 ID（REQ-xxxxxx）；不传则默认本窗口绑定的需求' },
      run_id: { type: 'string', description: '运行 ID（run-xxx）；传入则直接按 run_id 查询' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          run_id: { type: 'string' },
          snapshot: {
            type: 'object',
            description: '运行状态快照',
            additionalProperties: true,
            properties: {
              runId: { type: 'string', description: '运行 ID；**无 active run 时该键整体省略**（不发 null——本仓 DSL 不支持 null 联合类型）' },
              stepIndex: { type: 'number', description: '当前步骤索引' },
              currentSubtaskId: { type: 'string', description: '当前正在执行的子卡 ID' },
              nextReady: { type: 'array', description: '下一批 ready 的任务 ID 列表', items: { type: 'string' } },
              jobStatus: { type: 'string', description: 'Job 状态：running/completed/failed/not_found' },
              pauseReason: { type: 'string', description: '暂停原因（如果已暂停）' },
              autoRun: { type: 'boolean', description: '是否自动运行' },
              status: { type: 'string', description: '（保留）无 active run 的状态；**当前生产路径不产出该键**' },
              reason: { type: 'string', description: '（保留）无 active run 的原因；**当前生产路径不产出该键**' },
            },
          },
          error: { type: 'string' },
        },
      },
      render: renderSmart(summarize),
    },
    // REQ-260927144541-0481 FR-6：查询式工具不得挂 1 小时交互超时——那种超时只服务需要人作答的弹框类。
    timeoutMs: LIMITS.timeoutReadMs,
    async execute(args: { requirement_id?: string; run_id?: string }, exec: unknown): Promise<Record<string, unknown>> {
      const windowKey = deps.session.windowKey(exec)
      const snap = deps.repo.snapshot()
      
      // 1. 确定目标需求
      let requirementId: string | undefined = args.requirement_id
      
      if (!requirementId && !args.run_id) {
        // 默认本窗口绑定的需求
        const bound = openRequirementsFor(snap, windowKey)
        if (bound.length === 0) {
          return { success: false, error: '本窗口未绑定需求，请传入 requirement_id 或 run_id' }
        }
        requirementId = bound[0].id
      }
      
      if (!requirementId && args.run_id) {
        // 通过 run_id 反查 requirement_id（从台账查找）
        const req = snap.requirements.find(r => r.advance?.runId === args.run_id)
        if (req) {
          requirementId = req.id
        } else {
          return { success: false, error: `未找到 run_id=${args.run_id} 对应的需求` }
        }
      }
      
      if (!requirementId) {
        return { success: false, error: '无法确定目标需求' }
      }
      
      // 2. 查询运行状态（QueryRunStatus 用例契约为单个 QueryParams 对象；此前误传
      //    (deps, requirementId, exec)，运行期 getRequirement 为 undefined →
      //    "getRequirement is not a function"（2026-09-27 实测））
      // 宿主 JobsPort 可得时注入 job 查询（jobStatus 才能反映真实后台任务）；缺失则用例如实报 not_found。
      const jobs = deps.jobs
      const dshJobsAdapter = jobs !== undefined && jobs.available()
        ? { getJob: (id: string): Promise<{ status: string } | null> => jobs.get(id) }
        : undefined
      const status = await queryRunStatus({
        requirementId,
        getRequirement: async () => {
          const rec = deps.repo.snapshot().requirements.find(r => r.id === requirementId)
          if (rec === undefined) {
            throw Object.assign(new Error('需求不存在：' + requirementId), { code: 'REQBOARD_REQUIREMENT_NOT_FOUND' })
          }
          return rec as unknown as RequirementRecord
        },
        getTasks: async () => {
          // 任务来自队列（REQ-260927202051-f6df）：v9 台账已无 tasks。
          const store = deps.taskStore
          if (store === undefined) {
            // 未装配 = 组合根配置错误：**显式失败**，不谎报"没有任务"（端口缺省语义）。
            throw new Error('reqboard_run_status：任务存储（TaskStore）未装配，无法读取任务')
          }
          return (await store.listByRequirement(requirementId)) as unknown as TaskRecord[]
        },
        ...(dshJobsAdapter !== undefined ? { dshJobsAdapter } : {}),
      })

      // ⚠️ 不要把 status 原样透传：无 active run 时 `queryRunStatus` 给出的是 `runId: null`
      // （QueryRunStatus.ts:72），而本工具 schema 把 runId 声明为 `type: 'string'`
      // ⇒ 值级类型校验失败，会把「当前没有链在跑」这个**正常事实**转译成硬错误
      // 「value.snapshot.runId must be a string」（与"诚实降级被 schema 边界消灭"同类缺陷）。
      // 口径与上面顶层 run_id 一致：**不是 string 就整个键省略**，不发 null
      //（本仓 DSL 只允许 type/properties/additionalProperties，表达不了 `string | null`）。
      const snapshot: Record<string, unknown> = { ...status }
      if (typeof snapshot.runId !== 'string') delete snapshot.runId

      return {
        success: true,
        requirement_id: requirementId,
        ...(typeof status.runId === 'string' ? { run_id: status.runId } : {}),
        snapshot,
      }
    }
  } as any)
}
