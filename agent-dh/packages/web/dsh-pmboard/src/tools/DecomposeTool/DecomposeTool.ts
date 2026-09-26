/**
 * DecomposeTool（工具名 reqboard_decompose）——**恢复版**（2026-09-26）。
 *
 * 背景：`application/use-cases/Decompose.ts` 与对应的 agent 工具在 REQ-260925234037-1503
 * 的"删除手动工具"改造中一并下线，但后继的自动拆分路径（`deps.jobs.start`）从未装配
 * （`useCaseDeps.jobs` 缺失）→ 批准计划后抛 `Cannot read properties of undefined (reading 'start')`，
 * 需求停在 implementing/0 任务卡，无法开工。
 *
 * 本工具把**已存在的用例** `executeDecompose` 重新接回工具面：批准计划后由窗口 agent 调用，
 * 把批准的任务表落库为任务卡 DAG。工具壳只做协议转换（状态/计划校验全在用例与 domain）。
 *
 * @module dsh-pmboard/tools/DecomposeTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeDecompose } from '../../application/use-cases/Decompose.js'
import { renderSmart } from '../shared.js'
import { decomposeSummary } from '../render-summaries.js'

export function defineDecomposeTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_decompose',
    description:
      '用于：把已批准的拆分计划落库成任务卡 DAG（写台账任务卡 + 任务卡文档 + 依赖）。'
      + '批准计划后调本工具落库；不传 tasks = 直接落库批准计划里的任务表（key 必须一致）。'
      + '未批准 / 已有任务 / 需求未绑定本窗口 → 代码级拒绝。',
    parameters: {
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传默认本窗口绑定的需求' },
      tasks: {
        type: 'array',
        description: '计划未含任务表时用于创作任务卡（每项含 key/title/implementation/可证伪 acceptance）',
        items: { type: 'object', additionalProperties: true },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: true,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          requirement_status: { type: 'string' },
          created: { type: 'array', items: { type: 'object', additionalProperties: true } },
          task_coverage: { type: 'object', additionalProperties: true },
          coverage_check: { type: 'object', additionalProperties: true },
          thin_cards: { type: 'array', items: { type: 'string' } },
          warning: { type: 'string' },
          note: { type: 'string' },
        },
      },
      render: renderSmart(decomposeSummary),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    async execute(args: unknown, exec: unknown): Promise<Record<string, unknown>> {
      return await executeDecompose(deps, args, exec) as Record<string, unknown>
    },
  } as any)
}
