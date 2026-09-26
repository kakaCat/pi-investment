/**
 * Dive 会话驱动器的**空闲采集动作**（REQ-260926215013-1568 T-4 · serves: FR-3, FR-5, FR-6）。
 *
 * 从 session-driver.ts **逐字抽出**（纯函数、零框架依赖），唯一目的是让 session-driver 留在
 * ≤400 行尺寸门禁内、同时给它腾出接 round 半的空间。行为逐字不变。
 *
 * @module dsh-pmboard/application/dive/idle-capture-actions
 */
import type { ReqboardLedger, RequirementRecord } from '../../shared/protocol.js'
import { resolveStagePrompt } from '../../domain/prompt/index.js'
import { augmentResolvedPrompt } from '../internal/injection-address.js'
import { isInProgressTask } from '../../domain/status/Predicates.js'
import { findStaleUnconfirmedArtifact } from '../../domain/workflow/MilestoneSpec.js'
import { openRequirementsFor } from '../internal/window.js'

/** 里程碑提醒阈值（REQ-2e9473 t09/W1.5）：产物登记超过此时长未确认 → 主动提醒弹框。 */
export const MILESTONE_REMINDER_MS = 30 * 60 * 1000

/** T-3 地址段增强：开关关/根缺失/渲染异常 → 原样返回（与其它注入点同一纯函数）。 */
export function addressSectionFor(
  resolved: ReturnType<typeof resolveStagePrompt>,
  address: { templateRoot?: string; enabled?: boolean } | undefined,
  ledger: ReqboardLedger,
  requirement: RequirementRecord,
  stage: string,
): ReturnType<typeof resolveStagePrompt> {
  if (address === undefined || address.enabled === false || address.templateRoot === undefined) return resolved
  const currentTask = ledger.tasks.find(t => t.requirementId === requirement.id && isInProgressTask(t))
  try {
    // 注：与 h3-inject 同一形态（同一共用类型 AddressSectionInput 目前与实际 render 入参
    // 不一致，属基线 tsc 噪音，见 domain/template/render.ts:39/44 与 h3-inject.ts:45）。
    return augmentResolvedPrompt(resolved, {
      stage,
      category: requirement.category,
      requirement,
      ...(currentTask === undefined ? {} : { currentTask: { id: currentTask.id, title: currentTask.title, cardDoc: currentTask.cardDoc } }),
      templateRoot: address.templateRoot,
    })
  } catch {
    return resolved
  }
}

/**
 * 里程碑超时提醒（REQ-2e9473 t09，解决"agent 不主动弹框"）：
 * 绑定窗口的最新 open 需求存在"当前阶段已登记但超时未确认"的产物 → 返回提醒文本。
 * 每产物只提醒一次由调用方（driver 闭包里的 remindedAt Map）保证。
 */
export function milestoneReminderFor(
  ledger: ReqboardLedger,
  windowKey: string,
  now: number,
): { text: string; artifactKey: string } | undefined {
  const open = openRequirementsFor(ledger, windowKey)
  const req = [...open].sort((a, b) => b.updatedAt - a.updatedAt)[0]
  if (req === undefined) return undefined
  // 判定（当前阶段已登记但超时未确认）在 domain/workflow/MilestoneSpec.ts（REQ-47939a t3）。
  const stale = findStaleUnconfirmedArtifact(req, now, MILESTONE_REMINDER_MS)
  if (stale === undefined) return undefined
  const minutes = Math.round((now - stale.registeredAt) / 60000)
  return {
    artifactKey: req.id + ':' + stale.kind,
    text: '【里程碑提醒】产物 kind=' + stale.kind + '（' + stale.path + '）已登记 ' + minutes + ' 分钟未确认。'
      + '请立即调 reqboard_ask_confirm（target=artifact, kind=' + stale.kind + '）弹框请人确认——'
      + '用户点肯定项即自动落章并推进节点；或提示用户在看板点「确认产物」。',
  }
}
