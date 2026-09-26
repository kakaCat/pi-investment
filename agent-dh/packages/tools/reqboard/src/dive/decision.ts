/**
 * Dive 决策函数（REQ-260926140539-457b FR-8 / design/interfaces.md §3.2）。
 *
 * 纯读 RTM 快照做判定：给定当前节点，回答"能不能推进、下一站是谁、卡在哪"。
 * 不做任何写操作，也不再解析文档——这条路径就是 FR-8 声称的"~2ms 决策"。
 *
 * RTM 缺失时**不猜**：返回 can_proceed=false 并如实说明缺哪份数据（FR-9 响亮失败）。
 *
 * @module @pi-investment/reqboard/dive/decision
 */
import type { Coverage, RTMBrainstorming, RTMDesign, RTMDecomposing, RTMAccepting, RTMImplementing } from '../rtm/types.js'
import { thresholdFor } from '../rtm/validator.js'
import { readStageRTM } from '../stage-overview/rtm-reader.js'
import { coverageAt, nextStageOf } from './node-input.js'

/** Dive 模式的一次决策结果。 */
export interface DiveDecision {
  /** 是否可以推进到 next_stage。 */
  can_proceed: boolean
  stage: string
  next_stage?: string
  /** 人话理由。 */
  reason: string
  coverage?: Coverage
  /** 未过的项（缺哪些 FR / 设计章节 / 任务）。 */
  blockers?: string[]
}

function num(v: unknown): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : 0
}

/**
 * 对当前节点做一次推进决策。
 *
 * @param workspaceRoot 工作区根（docs/requirements 所在处）
 * @param stage 当前节点（draft / brainstorming / design / decomposing / implementing / accepting / done）
 * @param reqId 需求 id
 */
export function makeDiveDecision(workspaceRoot: string, stage: string, reqId: string): DiveDecision {
  const stageRTM = readStageRTM<Record<string, unknown>>(workspaceRoot, reqId, stage)
  if (stageRTM === null) {
    return {
      can_proceed: false,
      stage,
      reason: `RTM 数据缺失（rtm-${stage}.yml），无法做出决策，请先重生成 RTM`,
    }
  }

  const next = nextStageOf(stage)

  switch (stage) {
    case 'draft':
      return { can_proceed: true, stage, next_stage: next, reason: '已立项，进入需求分析' }

    case 'brainstorming': {
      const rtm = stageRTM as unknown as RTMBrainstorming
      const frs = rtm.outputs?.requirements ?? []
      const confirmed = (rtm.status?.artifacts ?? []).some(a => a.confirmed)
      if (confirmed) {
        return {
          can_proceed: true,
          stage,
          next_stage: next,
          reason: `需求已确认，识别到 ${frs.length} 个功能点，可以进入 design`,
        }
      }
      return {
        can_proceed: false,
        stage,
        reason: `需求产物尚未确认（已提取 ${frs.length} 个功能点）`,
        blockers: ['artifact:requirement 未落章'],
      }
    }

    case 'design': {
      const rtm = stageRTM as unknown as RTMDesign
      const coverage = rtm.coverage?.design
      if (coverage === undefined) {
        return { can_proceed: false, stage, reason: 'rtm-design.yml 无 design 覆盖度，无法判定' }
      }
      const gate = coverage.rate >= thresholdFor('design')
      return gate
        ? { can_proceed: true, stage, next_stage: next, reason: '所有 FR 都有设计，可以准备拆分', coverage }
        : {
            can_proceed: false,
            stage,
            reason: `还有 ${coverage.uncovered.length} 个 FR 缺少设计`,
            coverage,
            blockers: coverage.uncovered,
          }
    }

    case 'decomposing': {
      const rtm = stageRTM as unknown as RTMDecomposing
      const coverage = rtm.coverage?.implementation
      if (coverage === undefined) {
        return { can_proceed: false, stage, reason: 'rtm-decomposing.yml 无 implementation 覆盖度，无法判定' }
      }
      const gate = coverage.rate >= thresholdFor('decomposing')
      return gate
        ? { can_proceed: true, stage, next_stage: next, reason: '实施覆盖度 100%，所有设计都有任务，可以开工', coverage }
        : {
            can_proceed: false,
            stage,
            reason: `还有 ${coverage.uncovered.length} 个设计章节缺少任务`,
            coverage,
            blockers: coverage.uncovered,
          }
    }

    case 'implementing': {
      const rtm = stageRTM as unknown as RTMImplementing
      const total = num(rtm.status?.tasks_total)
      const done = num(rtm.status?.tasks_done)
      const doing = num(rtm.status?.tasks_in_progress)
      if (total === 0) {
        return { can_proceed: false, stage, reason: 'rtm-implementing.yml 尚无任务，可能拆分未落库' }
      }
      if (done >= total) {
        return {
          can_proceed: true,
          stage,
          next_stage: next,
          reason: `所有任务已完成（${done}/${total}），可以进入验收`,
        }
      }
      return {
        can_proceed: false,
        stage,
        reason: `任务进度 ${done}/${total}（${doing} 个进行中），尚未全部完成`,
        blockers: (rtm.tasks ?? []).filter(t => t.status !== 'done').map(t => t.id),
      }
    }

    case 'accepting': {
      const rtm = stageRTM as unknown as RTMAccepting
      const coverage = rtm.coverage?.testing ?? coverageAt(stageRTM, 'testing')
      if (coverage === undefined) {
        return { can_proceed: false, stage, reason: 'rtm-accepting.yml 无 testing 覆盖度，无法判定' }
      }
      const gate = coverage.rate >= thresholdFor('accepting')
      return gate
        ? { can_proceed: true, stage, next_stage: next, reason: `测试覆盖度 ${coverage.rate}%，可以归档`, coverage }
        : {
            can_proceed: false,
            stage,
            reason: `测试覆盖度不足（${coverage.rate}% < ${thresholdFor('accepting')}%）`,
            coverage,
            blockers: coverage.uncovered,
          }
    }

    default:
      return { can_proceed: true, stage, reason: '需求已完成，无需推进' }
  }
}
