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
import { parseDocument, extractClauseDefinitions, extractSkippedClauses } from '../internal/content-gates.js'
import { collectTaskRefs, clauseReceiveStatus } from '../internal/content-gate-wiring.js'

export async function queryState(deps: UseCaseDeps, _args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      const ledger = await deps.repo.read((l) => l)
      const open = openRequirementsFor(ledger, windowKey)
      const pending = findPending(ledger, windowKey)
      // 需求侧接收标记（FR-3 / T-5）：逐条功能点显示"谁接了 / 还没人接"。
      // R9 的形态就是"未被接收"，必须在**每次 status 调用**里显眼可见，而不是靠人记得去查。
      let clause_receive_status: unknown[] = []
      let unreceived: string[] = []
      if (open.length > 0) {
        const boundReq = open[0]
        const reqPath = 'docs/requirements/' + boundReq.id + '/requirement.md'
        if (deps.docs.exists(reqPath)) {
          const doc = parseDocument(await deps.docs.read(reqPath))
          const roots = extractClauseDefinitions(doc)
          if (roots.length > 0) {
            const status = clauseReceiveStatus(
              roots,
              await collectTaskRefs(deps.docs, boundReq),
              ledger.tasks,
              extractSkippedClauses(doc),
            )
            clause_receive_status = status
            unreceived = status.filter(s => s.state === 'unreceived').map(s => s.clause)
          }
        }
      }
      return {
        window_key: windowKey,
        bound: open.length > 0,
        open_count: open.length,
        open_requirements: open.map(projectRequirement),
        has_pending: pending !== undefined,
        pending_triage_id: pending?.id ?? '',
        next_actions: open.length > 0 ? agentNextActions(open[0].status) : [],
        clause_receive_status,
        unreceived_clauses: unreceived,
        note:
          open.length > 0
            ? `本窗口已绑定进行中需求（当前 ${open[0].status}）：里程碑处用 reqboard_move 自行推进（${agentNextActions(open[0].status).join(' / ') || '无可推进项'}），勿重复立项`
            : pending !== undefined
              ? '存在遗留待确认建议卡（旧流程产物）：可在看板确认/拒绝，或忽略；新立项直接走 reqboard_create'
              : '本窗口未绑定需求：识别到值得立项的新工作 → 调 reqboard_capture 弹「立项三问」（需求名称 / 需求类型 / 提示词难度），用户作答即在同一次调用内创建并绑定本窗口（创建即立项）',
        board_link: open.length > 0 ? `/dashboard#pmboard?req=${open[0].id}` : '/dashboard#pmboard',
      }
    }
