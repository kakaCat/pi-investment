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
import { queryRunStatus } from '../../application/use-cases/QueryRunStatus.js'
import { openRequirementsFor } from '../../application/internal/window.js'
import { RUN_STATUS_PROMPT } from './prompt.js'

export function defineRunStatusTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_run_status',
    description: RUN_STATUS_PROMPT,
    inputSchema: {
      type: 'object',
      properties: {
        requirement_id: {
          type: 'string',
          description: '需求 ID（REQ-xxxxxx）；不传则默认本窗口绑定的需求'
        },
        run_id: {
          type: 'string',
          description: '运行 ID（run-xxx）；传入则直接按 run_id 查询'
        }
      },
      additionalProperties: false
    },
    outputSchema: {
      type: 'object',
      required: ['success'],
      properties: {
        success: { type: 'boolean' },
        requirement_id: { type: 'string' },
        run_id: { type: 'string' },
        snapshot: {
          type: 'object',
          description: '运行状态快照',
          properties: {
            runId: { type: 'string', description: '运行 ID（无 active run 时为 null）' },
            stepIndex: { type: 'number', description: '当前步骤索引' },
            currentSubtaskId: { type: 'string', description: '当前正在执行的子卡 ID' },
            nextReady: {
              type: 'array',
              description: '下一批 ready 的任务 ID 列表',
              items: { type: 'string' }
            },
            jobStatus: {
              type: 'string',
              enum: ['running', 'completed', 'failed', 'not_found'],
              description: 'Job 状态'
            },
            pauseReason: { type: 'string', description: '暂停原因（如果已暂停）' },
            autoRun: { type: 'boolean', description: '是否自动运行' },
            status: { type: 'string', description: '无 active run 时的状态（terminated）' },
            reason: { type: 'string', description: '无 active run 时的原因' }
          }
        },
        error: { type: 'string' }
      },
      additionalProperties: false
    },
    timeoutMs: LIMITS.timeoutInteractiveMs,
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
      
      // 2. 查询运行状态
      const status = await queryRunStatus(deps, requirementId, exec)
      
      return {
        success: true,
        requirement_id: requirementId,
        run_id: status.runId ?? undefined,
        snapshot: status
      }
    }
  } as any)
}
