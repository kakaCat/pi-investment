/**
 * TaskMoveTool（工具名 reqboard_task_move）——agent 侧任务流转（REQ-260927100007-b8ba FR-7/FR-8；
 * REQ-260927144541-0481 FR-5）。
 *
 * FR-5 两件事：
 *  ① `acceptance` 参数**真正接线**：走 amendTaskAcceptanceIfRequested（台账落库 + 卡文档同步）。
 *     此前 AmendTaskAcceptance 用例已存在但**全仓无调用点**——死通道（P9）。只传 acceptance
 *     不传 to = 仅修订不改状态（开工时读到不可执行的验收标准，先改卡再干活）。
 *  ② 返回体声明补齐：用例实际返回 version / subtasks_created / task_card，此前 output.schema 没声明
 *     （additionalProperties:false 会把回执判成 invalid output）。
 *
 * 角色感知报错在用例/domain（非法转移文案含角色与合法边），工具壳只做协议转换。
 *
 * @module dsh-pmboard/tools/TaskMoveTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeMoveTask } from '../../application/use-cases/MoveTask.js'
import { amendTaskAcceptanceIfRequested } from '../../application/use-cases/AmendTaskAcceptance.js'
import { assertNoPendingConfirm } from '../../application/internal/support.js'
import { fmt } from '../../domain/text/fmt.js'
import { renderSmart } from '../shared.js'

const summarize = (v: unknown): string => {
  const o = (v ?? {}) as Record<string, unknown>
  const change = String(o['from'] ?? '?') + ' → ' + String(o['to'] ?? '?')
  const amended = o['acceptance'] !== undefined ? '（并已修订验收标准）' : ''
  return fmt('任务推进：{task_id} {change}{amended}', { task_id: String(o['task_id'] ?? ''), change, amended })
}

export function defineTaskMoveTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_move',
    description: [
      '用于：推进任务状态（todo → in_progress → integrating → testing → in_review → done）。',
      '非法转移的报错会说明**当前角色**（父卡/子卡/存量卡）与**该角色的全部合法边**。',
      '可选 acceptance：修订该任务的验收标准（≤2000 字符，须含可执行锚点）并同步卡文档；',
      '只传 acceptance 不传 to = 仅修订、不改状态（用于开工时发现验收标准不可执行）。',
      '人工门越权（取消/复活/重开已完成卡）代码级拒绝；任务必须属于本窗口绑定的需求。',
    ].join(''),
    parameters: {
      task_id: { type: 'string', description: '任务 id（t-xxxxxx）' },
      to: { type: 'string', description: '目标状态（todo/in_progress/integrating/testing/in_review/done/canceled）；与 acceptance 至少给一个' },
      reason: { type: 'string', description: '理由（进台账留痕）' },
      acceptance: { type: 'string', description: '修订验收标准（≤2000 字符，须含命令/断言锚点）；只传它 = 仅修订不改状态' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          task_id: { type: 'string' },
          from: { type: 'string' },
          to: { type: 'string' },
          status: { type: 'string' },
          version: { type: 'number' },
          subtasks_created: { type: 'array', items: { type: 'string' }, description: '父卡开工同事务懒展开的子卡 id' },
          task_card: { type: 'object', additionalProperties: true, description: '任务卡全文投影（照卡执行）' },
          acceptance: { type: 'string', description: '本次修订后的验收标准' },
          error: { type: 'string' },
          code: { type: 'string' },
        },
      },
      render: renderSmart(summarize),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    async execute(args: unknown, exec: unknown): Promise<Record<string, unknown>> {
      assertNoPendingConfirm(deps, deps.session.windowKey(exec))
      const a = (args ?? {}) as Record<string, unknown>
      const taskId = typeof a.task_id === 'string' ? a.task_id : ''

      // 先修订（如有）：开工时读到不可执行的验收标准，先改卡再干活（用例内保证零行为变更）。
      const amended = await amendTaskAcceptanceIfRequested(deps, args, exec)

      const hasTo = typeof a.to === 'string' && a.to.trim().length > 0
      if (!hasTo) {
        if (amended === undefined) {
          return {
            success: false,
            task_id: taskId,
            error: 'reqboard_task_move 未执行：至少给出 to 或 acceptance',
            code: 'REQBOARD_INVALID_INPUT',
          }
        }
        return { success: true, task_id: taskId, acceptance: amended }
      }

      const out = await executeMoveTask(deps, args, exec) as Record<string, unknown>
      return { ...out, ...(amended !== undefined ? { acceptance: amended } : {}) }
    },
  } as any)
}
