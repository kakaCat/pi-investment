/**
 * TaskAdoptTool（工具名 reqboard_task_adopt）——归属补救**薄壳**：三段式里只做
 * 参数/输出协议转换，领域判定全部在 application/use-cases/AdoptTask（与 task_move 同款分工）。
 *
 * 用途：把**缺父卡归属**的卡挂到指定父卡下（补 parentId + stageKind）。典型现场：
 * 卡片角色由"名下有没有子卡"派生，归属缺失的卡只能被当成存量卡硬走五段状态机，
 * 报错还会说"存量卡不允许 todo→done"——本工具是这条路的唯一修复入口。
 *
 * 拒绝条件（用例内实现，这里不重复判断）：跨需求 / 父卡本身是子卡 / 名下有子卡 /
 * 已有归属未 force / 自指依赖 / stageKind 缺失或非法 / 当前状态不在子卡生命周期 /
 * 挂载后新增 INV-1..INV-4 违规。
 *
 * @module dsh-pmboard/tools/AdoptTaskTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeAdoptTask } from '../../application/use-cases/AdoptTask.js'
import { assertNoPendingConfirm } from '../../application/internal/support.js'
import { fmt } from '../../domain/text/fmt.js'
import { renderSmart } from '../shared.js'

const summarize = (v: unknown): string => {
  const o = (v ?? {}) as Record<string, unknown>
  if (o['success'] === false || o['error'] !== undefined) {
    return fmt('归属补救被拒：{why}', { why: String(o['error'] ?? '见明细').slice(0, 80) })
  }
  return fmt('归属补救：{t} → 父卡 {p}（{k}）', {
    t: String(o['task_id'] ?? ''),
    p: String(o['parent_id'] ?? ''),
    k: String(o['stage_kind'] ?? ''),
  })
}

export function defineTaskAdoptTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_adopt',
    description: [
      '用于：**归属补救**——把缺父卡归属（parentId 缺失）的任务卡挂到指定父卡下，补上 parentId 与 stageKind，',
      '使其按子卡三态（todo→in_progress→done）推进，而不是被当成"存量卡"走五段。',
      '仅补**缺失**归属；改挂已有归属的卡必须传 force=true 并写明 reason。',
      '拒绝条件：跨需求 / 父卡本身是子卡 / 该卡名下有子卡 / 自指依赖 / stageKind 缺失或非法 / ',
      '当前状态不在子卡生命周期（integrating/testing/in_review 需先退回 in_progress）/ 挂载后新增子卡不变量违规。',
      '任务与父卡都必须属于本窗口绑定的需求。',
    ].join(''),
    parameters: {
      task_id: { type: 'string', description: '要补归属的任务 id（t-xxxxxx）', required: true },
      parent_id: { type: 'string', description: '挂到哪张父卡下（t-xxxxxx，须为同需求的顶层卡）', required: true },
      stage_kind: { type: 'string', description: '子卡阶段（受控枚举 dev/integrate/review/test）；卡上已有 stageKind 时可不传' },
      reason: { type: 'string', description: '补救原因（进队列卡片评论与需求评论留痕）' },
      force: { type: 'boolean', description: '改挂已有归属的卡时必传（默认 false：只补缺失）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          requirement_id: { type: 'string' },
          parent_id: { type: 'string' },
          previous_parent_id: { type: 'string', description: '改挂前的父卡（补缺失时为空串）' },
          stage_kind: { type: 'string' },
          role: { type: 'string', description: '补救后的角色（恒为 subtask）' },
          status: { type: 'string' },
          version: { type: 'number' },
          note: { type: 'string' },
          error: { type: 'string' },
          code: { type: 'string' },
        },
      },
      render: renderSmart(summarize),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    async execute(args: unknown, exec: unknown): Promise<Record<string, unknown>> {
      assertNoPendingConfirm(deps, deps.session.windowKey(exec))
      return await executeAdoptTask(deps, args, exec) as Record<string, unknown>
    },
  } as any)
}
