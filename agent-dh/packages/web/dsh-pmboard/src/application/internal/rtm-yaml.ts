/**
 * RTM YAML 触发点接线（REQ-260926140539-457b FR-2 / FR-9）。
 *
 * 把需求流水线上的六个业务动作接到 RTM YAML 生成器：
 *   reqboard_create            → create（rtm-lifecycle.yml 骨架）
 *   submit(kind=requirement)   → submit:requirement
 *   ask_confirm / 看板确认产物 → confirm:artifact
 *   submit(kind=design)        → submit:design
 *   ask_confirm / 看板批准计划 → confirm:plan（拆分 + 实施骨架）
 *   任务状态变更 / task_report → task:status / task:report
 *   submit(kind=verification)  → submit:verification
 *
 * **失败绝不打断主流程**（FR-9）：RTM 是增强层，任何异常只记 warning 并结构化返回，
 * 需求创建/提交/确认/推进的既有行为逐字节不变。
 *
 * @module dsh-pmboard/application/internal/rtm-yaml
 */
import type { UseCaseDeps } from '../ports.js'
import { recordRTMFailure, clearRTMFailure } from './rtm-health.js'
import { flowProfileFor, type RequirementCategory, type RequirementRecord, type TaskRecord } from '../../shared/protocol.js'
import { stageOfStatus } from '../../../../../tools/reqboard/src/rtm/lifecycle-generator.js'
import { RTMGenerator, runRTMTrigger, type RTMTrigger, type RTMTriggerResult } from '../../../../../tools/reqboard/src/rtm/generator.js'
import type { LedgerReader } from '../../../../../tools/reqboard/src/rtm/context.js'
import type { GateResult, RTMTaskLike, WorkflowPhase } from '../../../../../tools/reqboard/src/rtm/types.js'
import { rtmValidator } from '../../../../../tools/reqboard/src/rtm/validator.js'
import type { TaskDetailUpdate } from '../../../../../tools/reqboard/src/rtm/implementing-generator.js'

/** 触发点附加载荷。 */
export interface RtmYamlPayload {
  taskId?: string
  updates?: TaskDetailUpdate
}

/**
 * 台账只读快照的形状（JsonLedgerRepository.snapshot() 返回的 LedgerView 是 readonly 数组，
 * 这里按只读接收，避免为了类型而复制一份）。
 */
export interface RTMLedgerSnapshot {
  requirements: readonly RequirementRecord[]
  tasks: readonly TaskRecord[]
}

/** 台账任务 → RTM 任务投影。 */
function toTaskLike(t: TaskRecord): RTMTaskLike {
  return {
    id: t.id,
    title: t.title,
    status: t.status,
    phase: t.phase,
    side: t.side,
    depends_on: [...t.dependsOn],
  }
}

/** 用台账快照搭一个只读 LedgerReader（RTM 只读台账，不反向写）。 */
function ledgerReaderOf(snap: RTMLedgerSnapshot): LedgerReader {
  return {
    requirement: id => {
      const r = snap.requirements.find(x => x.id === id)
      if (r === undefined) return undefined
      return {
        id: r.id,
        title: r.title,
        category: r.category ?? '',
        status: r.status,
        createdAt: r.createdAt,
        updatedAt: r.updatedAt,
        // 绑定窗口进 RTM：Dive 唤醒要按它投递（见 RTMLifecycle.requirement.source_session）。
        ...(typeof r.sourceSessionId === 'string' && r.sourceSessionId.length > 0
          ? { sourceSessionId: r.sourceSessionId }
          : {}),
        artifacts: (r.artifacts ?? []).map(a => ({
          kind: a.kind,
          path: a.path,
          stage: a.stage,
          confirmedAt: a.confirmedAt,
          registeredAt: a.registeredAt,
        })),
      }
    },
    tasksOf: reqId => snap.tasks.filter(t => t.requirementId === reqId).map(toTaskLike),
  }
}

/** 从汇报文案推断当前子阶段（t16：doc/ui/analysis/implement/test/review/commit）。 */
export function inferWorkflowPhase(summary: string): WorkflowPhase {
  const s = summary.toLowerCase()
  if (/文档|doc|readme/.test(s)) return 'doc'
  if (/测试|test|用例|回归/.test(s)) return 'test'
  if (/审查|review|复核|检查/.test(s)) return 'review'
  if (/提交|commit|推送/.test(s)) return 'commit'
  if (/分析|analysis|调研|方案/.test(s)) return 'analysis'
  if (/界面|ui|样式|布局/.test(s)) return 'ui'
  return 'implement'
}

/**
 * 覆盖度门禁（FR-2 / FR-5 / design/interfaces.md §4.1）。
 *
 * 把触发点本次生成的覆盖度过一次校验，返回 undefined = **不拦截**：
 *  - 触发失败（ok=false）；
 *  - 该触发点没有覆盖度产出；
 *  - 覆盖度 total=0（无项可判）。
 * 这是 FR-9 的边界：RTM 是增强层，绝不能因为它的数据缺失而拦住主流程；
 * 只有**拿到真实覆盖度数据**时才执法。
 */
export function coverageGateOf(
  stage: 'design' | 'decomposing' | 'accepting',
  result: RTMTriggerResult | undefined,
): GateResult | undefined {
  if (result?.ok !== true) return undefined
  const coverage = result.coverage
  if (coverage === undefined || coverage.total <= 0) return undefined
  return rtmValidator.checkGate(stage, coverage)
}

/**
 * 触发一次 RTM 同步。返回结构化结果；异常被吞并记 warning（不抛）。
 */
export function syncRTMYaml(
  deps: UseCaseDeps,
  reqId: string,
  trigger: RTMTrigger,
  payload?: RtmYamlPayload,
): RTMTriggerResult | undefined {
  // FR-9：本函数的契约是"失败绝不打断主流程"——**连取根/取快照都必须在 try 内**。
  // 此前它们在 try 之外求值，docs/repo 端口缺失时会在进 try 之前抛出去（实测：不注入
  // docs 的工具用例会炸），与"RTM 是增强层"的承诺相反。
  try {
    return syncRTMYamlWithSnapshot(deps.docs.workspaceRoot(), deps.repo.snapshot(), reqId, trigger, payload)
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : String(err)
    console.warn('[rtm-yaml] ' + trigger + ' ' + reqId + ' 取工作区根/台账快照失败（已忽略，不影响主流程）:', err)
    // 记录失败到 state/rtm-failures.json（修复：yaml 生成失败，下一次校验时提醒）
    try {
      const stateDir = deps.docs.workspaceRoot() + '/.dsh-data/state'
      recordRTMFailure(stateDir, reqId, trigger, errMsg)
    } catch {
      // 记录失败本身也失败时静默（不能因为记录失败而影响主流程）
    }
    return undefined
  }
}

/**
 * HTTP 路由（只拿到 store/deps.cwd，不是完整 UseCaseDeps）用的入口。
 */
export function syncRTMYamlWithSnapshot(
  workspaceRoot: string,
  snapshot: RTMLedgerSnapshot,
  reqId: string,
  trigger: RTMTrigger,
  payload?: RtmYamlPayload,
): RTMTriggerResult | undefined {
  try {
    const generator = new RTMGenerator({
      workspaceRoot,
      ledger: ledgerReaderOf(snapshot),
      generatedBy: 'dsh-pmboard',
      // "这个需求有多少个节点"：取分类流程档案（单一事实源在 shared/protocol）；
      // archived 按 RTM 口径归一到 done（stageOfStatus 是同一归一函数的单点）。
      enabledStagesOf: (category: string | undefined) =>
        flowProfileFor(category as RequirementCategory | undefined).stages.map(stageOfStatus),
    })
    const result = runRTMTrigger(generator, trigger, reqId, payload)
    if (!result.ok) {
      console.warn('[rtm-yaml] ' + trigger + ' ' + reqId + ' 同步失败：' + (result.error ?? '未知原因'))
      // 记录失败
      try {
        const stateDir = workspaceRoot + '/.dsh-data/state'
        recordRTMFailure(stateDir, reqId, trigger, result.error ?? '未知原因')
      } catch {
        // 记录失败本身也失败时静默
      }
    } else {
      // 成功时清除失败记录
      try {
        const stateDir = workspaceRoot + '/.dsh-data/state'
        clearRTMFailure(stateDir, reqId)
      } catch {
        // 清除失败记录失败时静默
      }
    }
    return result
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : String(err)
    console.warn('[rtm-yaml] ' + trigger + ' ' + reqId + ' 接线异常（已忽略，不影响主流程）:', err)
    // 记录失败（注意：这里只有 workspaceRoot，需要手动拼接 stateDir）
    try {
      const stateDir = workspaceRoot + '/.dsh-data/state'
      recordRTMFailure(stateDir, reqId, trigger, errMsg)
    } catch {
      // 记录失败本身也失败时静默
    }
    return undefined
  }
}
