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
  projectRequirement,
} from '../internal/support.js'
import { parseDocument, extractClauseDefinitions, extractSkippedClauses } from '../internal/content-gates.js'
import { collectTaskRefs, clauseReceiveStatus, checkFullTraceability } from '../internal/content-gate-wiring.js'
import { designDocRegistrationOf } from '../internal/design-docs.js'
import { generateStatusRTM } from '../internal/status-rtm-integration.js'
import { checkRTMHealth } from '../internal/rtm-health.js'

export async function queryState(deps: UseCaseDeps, _args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      const ledger = await deps.repo.read((l) => l)
      const open = openRequirementsFor(ledger, windowKey)
      // 需求侧接收标记（FR-3 / T-5）：逐条功能点显示"谁接了 / 还没人接"。
      // R9 的形态就是"未被接收"，必须在**每次 status 调用**里显眼可见，而不是靠人记得去查。
      let clause_receive_status: unknown[] = []
      let unreceived: string[] = []
      // 设计文档逐份登记态（FR-1 / I-2，T-4）：磁盘 / 产物簿 / 确认章三源合成——agent 不打开看板
      // 也能读出「未登记 / 待确认 / 已落章」。与 reqboard_submit(kind=design) 的 design_docs 同源同口径。
      let design_docs: unknown[] = []
      if (open.length > 0) {
        const boundReq = open[0]
        design_docs = await designDocRegistrationOf(deps.docs, boundReq)
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
      // RTM 集成：生成 FR 覆盖度和验收进度（REQ-260925172227-2d61 FR-4）
      let rtmData: ReturnType<typeof generateStatusRTM> | undefined
      if (open.length > 0) {
        try {
          const boundReq = open[0]
          const reqDir = 'docs/requirements/' + boundReq.id
          const reqTasks = ledger.tasks.filter(t => t.requirementId === boundReq.id && t.status !== 'canceled')
          const verificationSheet = boundReq.verification?.sheet
          rtmData = generateStatusRTM(reqDir, reqTasks, verificationSheet)
        } catch (rtmErr) {
          console.warn('[QueryState] RTM 集成失败:', rtmErr)
        }
      }
      
      // RTM 健康检查（修复：yaml 生成失败，下一次校验时提醒）
      let rtm_health: unknown | undefined
      if (open.length > 0) {
        try {
          const boundReq = open[0]
          const workspaceRoot = deps.docs.workspaceRoot()
          const stateDir = workspaceRoot + '/.dsh-data/state'
          rtm_health = checkRTMHealth(workspaceRoot, stateDir, boundReq)
        } catch (healthErr) {
          console.warn('[QueryState] RTM 健康检查失败:', healthErr)
        }
      }
      
      // 三级追溯链统计（2026-09-26 追溯性改进）
      let traceability_chain: unknown | undefined
      if (open.length > 0) {
        try {
          const boundReq = open[0]
          const reqTasks = ledger.tasks.filter(t => t.requirementId === boundReq.id && t.status !== 'canceled')
          const coverage = await checkFullTraceability(deps.docs, boundReq, reqTasks)
          
          traceability_chain = {
            design_coverage: {
              total: coverage.designCoverage.total,
              covered: coverage.designCoverage.covered,
              coverage_rate: coverage.designCoverage.total > 0 
                ? Math.round((coverage.designCoverage.covered / coverage.designCoverage.total) * 100) 
                : 100,
              gaps: coverage.designCoverage.gaps,
              status: coverage.designCoverage.gaps.length === 0 ? 'complete' : 'incomplete'
            },
            implementation_coverage: {
              total: coverage.implementationCoverage.total,
              covered: coverage.implementationCoverage.covered,
              coverage_rate: coverage.implementationCoverage.total > 0
                ? Math.round((coverage.implementationCoverage.covered / coverage.implementationCoverage.total) * 100)
                : 100,
              gaps: coverage.implementationCoverage.gaps,
              status: coverage.implementationCoverage.gaps.length === 0 ? 'complete' : 'incomplete'
            },
            test_coverage: {
              total: coverage.testCoverage.total,
              tested: coverage.testCoverage.tested,
              coverage_rate: coverage.testCoverage.total > 0
                ? Math.round((coverage.testCoverage.tested / coverage.testCoverage.total) * 100)
                : 0,
              gaps: coverage.testCoverage.gaps,
              status: coverage.testCoverage.tested === coverage.testCoverage.total ? 'complete' : 'incomplete'
            },
            overall_status: 
              coverage.designCoverage.gaps.length === 0 &&
              coverage.implementationCoverage.gaps.length === 0 &&
              coverage.testCoverage.tested === coverage.testCoverage.total
                ? 'complete'
                : 'incomplete'
          }
        } catch (traceErr) {
          console.warn('[QueryState] 追溯链统计失败:', traceErr)
        }
      }
      
      return {
        window_key: windowKey,
        bound: open.length > 0,
        open_count: open.length,
        open_requirements: open.map(projectRequirement),
        next_actions: open.length > 0 ? agentNextActions(open[0].status) : [],
        clause_receive_status,
        unreceived_clauses: unreceived,
        design_docs,
        ...(rtmData !== undefined
          ? {
              fr_coverage: rtmData.fr_coverage,
              ...(rtmData.fr_acceptance_progress !== undefined
                ? { fr_acceptance_progress: rtmData.fr_acceptance_progress }
                : {}),
            }
          : {}),
        ...(traceability_chain !== undefined
          ? { traceability_chain }
          : {}),
        ...(rtm_health !== undefined
          ? { rtm_health }
          : {}),
        note:
          open.length > 0
            ? `本窗口已绑定进行中需求（当前 ${open[0].status}）：里程碑处用 reqboard_move 自行推进（${agentNextActions(open[0].status).join(' / ') || '无可推进项'}），勿重复立项`
            : '本窗口未绑定需求：识别到值得立项的新工作 → 调 reqboard_capture 弹「立项三问」（需求名称 / 需求类型 / 提示词难度），用户作答即在同一次调用内创建并绑定本窗口（创建即立项）',
        board_link: open.length > 0 ? `/dashboard#pmboard?req=${open[0].id}` : '/dashboard#pmboard',
      }
    }