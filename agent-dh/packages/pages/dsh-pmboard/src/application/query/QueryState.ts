/**
 * QueryState 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineStatusTool / reqboard_status 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/QueryState
 */
import type { UseCaseDeps } from '../ports.js'
import {
  agentNextActions,
} from '../../shared/protocol.js'
import { openRequirementsFor } from '../internal/window.js'
import {
  agentIdFromExec,
  findPending,
  projectRequirement,
} from '../internal/support.js'

export async function queryState(deps: UseCaseDeps, _args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      const ledger = await deps.repo.read((l) => l)
      const open = openRequirementsFor(ledger, windowKey)
      const pending = findPending(ledger, windowKey)
      return {
        window_key: windowKey,
        bound: open.length > 0,
        open_count: open.length,
        open_requirements: open.map(projectRequirement),
        has_pending: pending !== undefined,
        pending_triage_id: pending?.id ?? '',
        next_actions: open.length > 0 ? agentNextActions(open[0].status) : [],
        note:
          open.length > 0
            ? `本窗口已绑定进行中需求（当前 ${open[0].status}）：里程碑处用 reqboard_move 自行推进（${agentNextActions(open[0].status).join(' / ') || '无可推进项'}），勿重复立项`
            : pending !== undefined
              ? '存在遗留待确认建议卡（旧流程产物）：可在看板确认/拒绝，或忽略；新立项直接走 reqboard_create'
              : '本窗口未绑定需求：识别到值得立项的新工作 → 先 ask_user_question 弹「两问确认」（需求名称+需求类型）获用户确认，再按确认值调 reqboard_create 直接立项（创建即立项）',
      }
    }
