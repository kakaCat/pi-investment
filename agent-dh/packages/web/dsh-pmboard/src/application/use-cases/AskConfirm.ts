/**
 * AskConfirm 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineAskConfirmTool / reqboard_ask_confirm 工厂**逐字搬入**编排。
 *
 * REQ-260924213231-b1c4 T-6（serves: FR-3）：弹框改**非阻塞投递**（I-3）——\`questions.ask\` 与宽限计时器赛跑：
 *   · 宽限内作答 → 与改造前**逐字一致**的同步落章/推进（旧语义回归，TC-6）；
 *   · 超宽限   → 登记挂起 ticket、立即返回 \`pending=true\`（**不判失败**，TC-5），
 *                 后台继续等作答并落章/推进/唤醒窗口。
 *
 * 抽出点（避免两份实现漂移）：落章+推进的唯一实现在 \`application/internal/confirm-settle.ts\`；
 * 赛跑/挂起/后台唤起在 \`application/internal/pending-confirm.ts\`。本文件只留编排与响应组装。
 *
 * 兼容性（interfaces.md 兼容性矩阵）：\`deps.pendingConfirms\` 缺省 = 未装配非阻塞能力 →
 * 完全走旧的阻塞语义（本文件那条分支一字未改）。
 *
 * @module dsh-pmboard/application/use-cases/AskConfirm
 */
import type { AskAnswer, UseCaseDeps } from '../ports.js'
import {
  ALL_ARTIFACT_KINDS,
  normalizeText,
} from '../../shared/protocol.js'
import { DEFAULT_CONFIRM_OPTIONS } from '../../domain/text/labels.js'
import { clip, fmt } from '../../domain/text/fmt.js'
import { pmHeader } from '../../domain/text/pm-badge.js'
import { LIMITS } from '../../domain/limits.js'
import { gateFromStage } from '../../domain/gate/GateCatalog.js'
import { checkDesignCompletenessGate } from '../internal/content-gate-wiring.js'
import type { GateFailure } from '../internal/artifact-gates.js'
import { openRequirementsFor } from '../internal/window.js'
import { applyConfirmDecision, recordDeclinedConfirmation } from '../internal/confirm-settle.js'
import {
  raceAsk,
  suspendConfirm,
  type ConfirmSubmitted,
} from '../internal/pending-confirm.js'
import {
  reject,
  agentIdFromExec,
  requireLiveDriver,
} from '../internal/support.js'

// 自动推进白名单来自闸门目录（REQ-e3b6a0 t2：原私有 ADVANCE_MAP 已收敛进 domain/gate/GateCatalog）。

export async function askConfirm(deps: UseCaseDeps, args: unknown, exec: any): Promise<unknown> {
      const windowKey = agentIdFromExec(deps, exec)
      requireLiveDriver(deps, exec)
      const a = (args ?? {}) as {
        requirement_id?: unknown; target?: unknown; kind?: unknown
        question?: unknown; options?: unknown; advance?: unknown; inline_grace_ms?: unknown
      }
      const explicitId = normalizeText(a.requirement_id, 'requirement_id', 64)
      const targetKind = normalizeText(a.target, 'target', 32)
      const kindRaw = normalizeText(a.kind, 'kind', 64)
      // REQ-308b9a t5（AC-7.6 配套）：题干受长度纪律约束——过长会把选项挤出可视区
      // （用户实测「不能选择」）。accept_sheet 早已 clip，confirm 此前漏了。
      const question = clip(normalizeText(a.question, 'question', 2000), LIMITS.popupQuestionMax)
      const options = Array.isArray(a.options)
        ? (a.options as unknown[]).map(o => normalizeText(o, 'options[]', 200)).filter(o => o.length > 0).slice(0, 5)
        : []
      const advance = a.advance !== false
      if (question.length === 0) reject('reqboard_ask_confirm 未执行：question 不能为空', 'REQBOARD_INVALID_INPUT')
      if (targetKind !== 'artifact' && targetKind !== 'plan') {
        reject('reqboard_ask_confirm 未执行：target 只能是 artifact 或 plan', 'REQBOARD_INVALID_INPUT')
      }
      if (targetKind === 'artifact' && !(ALL_ARTIFACT_KINDS as readonly string[]).includes(kindRaw)) {
        reject('reqboard_ask_confirm 未执行：kind 必须是 ' + ALL_ARTIFACT_KINDS.join(' / '), 'REQBOARD_INVALID_INPUT')
      }
      // T-6（I-3 字段明细）：\`inline_grace_ms\` 可覆写宽限窗口（缺省取配置），非法值显式拒绝、不静默回落。
      const graceRaw = a.inline_grace_ms
      if (graceRaw !== undefined && (typeof graceRaw !== 'number' || !Number.isFinite(graceRaw) || graceRaw <= 0)) {
        reject('reqboard_ask_confirm 未执行：inline_grace_ms 必须是正数（毫秒）', 'REQBOARD_INVALID_INPUT')
      }
      const optionLabels = options.length > 0 ? options : [...DEFAULT_CONFIRM_OPTIONS]
      // REQ-4842fe t10/FR-16：批准计划的弹框必须写明「批准后自动拆分并立即开跑」（拆分确认门并入本门）。
      const popupQuestion = targetKind === 'plan'
        ? clip(fmt('{q}（批准后将自动拆分任务卡并立即开跑，中途不再打断；如需干预可在看板暂停或取消）', { q: question }), LIMITS.popupQuestionMax)
        : question

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_ask_confirm 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const targetReq = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (targetReq === undefined) {
        reject('reqboard_ask_confirm 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }

      // T-7（FR-9/FR-11）：目标产物已确认（或计划已批准）→ 直接返回，**不再弹框**。
      // 同一产物不重复打扰；弹框只在该节点闸门出现一次。
      const kindArts = (targetReq.artifacts ?? []).filter(a => a.kind === kindRaw)
      const alreadyConfirmed = targetKind === 'artifact'
        ? kindArts.length > 0 && kindArts.every(a => a.confirmedAt !== undefined)
        : targetReq.plan?.approvedAt !== undefined
      if (alreadyConfirmed) {
        // REQ-260924213231-b1c4 FR-2：早返回不再与 move 的 G2 文案打架——先跑一遍完整性闸门，
        // 把「仍有 N 份未登记」如实带回（落章保留；本路径本就不推进，只报缺口，不弹框）。
        let earlyGate: GateFailure | undefined
        if (targetKind === 'artifact' && kindRaw === 'design') {
          earlyGate = await checkDesignCompletenessGate(deps.docs, targetReq)
        }
        const unregistered = (earlyGate?.gaps ?? []).filter(g => g.includes('未登记')).length
        const gapNote = earlyGate === undefined
          ? ''
          : fmt('；design → decomposing 未推进：{msg}', { msg: earlyGate.message })
            + (unregistered > 0 ? fmt('。仍有 {n} 份未登记', { n: unregistered }) : '')
        return {
          success: true, confirmed: true, advanced: false, requirement_id: targetReq.id,
          ...(earlyGate !== undefined ? { gate_failure: earlyGate } : {}),
          note: (targetKind === 'artifact'
            ? '产物 ' + kindRaw + ' 已确认，未重复弹框（FR-9/FR-11）'
            : '拆分计划已批准，未重复弹框（FR-9/FR-11）') + gapNote,
        } as never
      }

      // ── 弹框（userQuestions 服务接缝，经 UserQuestionPort）────────────────
      if (!deps.questions.available()) {
        return {
          success: false, confirmed: false, advanced: false, fallback: 'board',
          note: '弹框通道不可用（userQuestions 服务缺失）：请用户到项目看板点确认按钮；或由 agent 改用 ask_user_question + reqboard_confirm_artifact 两步走',
        } as never
      }
      // 闸门声明（REQ-e3b6a0 t7）：由「作答前所处阶段」查闸门目录得到，装饰器据此登记后置链。
      const gateId = gateFromStage(targetReq.status)?.id
      const submitted: ConfirmSubmitted = {
        requirementId: targetReq.id,
        windowKey,
        target: targetKind as 'artifact' | 'plan',
        kind: kindRaw,
        question,
        optionLabels,
        advance,
      }
      const ask = deps.questions.ask([{
        id: 'confirm',
        question: popupQuestion,
        header: pmHeader('确认'),
        options: optionLabels.map((label, i) => ({ label, ...(i === 0 ? { description: '确认后自动落章并推进' } : {}) })),
      }], {
        ...(exec.agent !== undefined ? { agent: exec.agent } : {}),
        signal: (exec as { signal?: unknown }).signal,
        ...(gateId === undefined ? {} : { gate: gateId }),
      })

      // 未装配挂起确认注册表 = 非阻塞能力关闭 → **旧阻塞语义逐字一致**（兼容性矩阵）。
      if (deps.pendingConfirms === undefined) {
        let answers: readonly AskAnswer[]
        try {
          answers = await ask
        } catch (err) {
          return degradedAnswer(err) as never
        }
        return settleAnswers(deps, exec, answers, submitted)
      }

      // 宽限赛跑：宽限内作答 = 同步落章；超宽限 = 登记 ticket 立即返回（不判失败）。
      const graceMs = typeof graceRaw === 'number' ? graceRaw : LIMITS.confirmInlineGraceMs
      const raced = await raceAsk(ask, graceMs)
      if (raced.kind === 'answered') return settleAnswers(deps, exec, raced.answers, submitted)
      if (raced.kind === 'rejected') return degradedAnswer(raced.err) as never
      return suspendConfirm(deps, ask, submitted, (answers) => settleAnswers(deps, exec, answers, submitted)) as never
    }

/**
 * 弹框抛错的两条降级（与改造前逐字一致）：无弹框权限 → `fallback=board`；
 * 取消/暂离（ASK_ABORTED 等）→ 中性返回，**不算错误**。
 */
function degradedAnswer(err: unknown): Record<string, unknown> {
  const code = (err as { code?: string }).code ?? ''
  if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
    return {
      success: false, confirmed: false, advanced: false, fallback: 'board',
      note: '当前调用方无弹框权限（subagent/非活窗口）：请用户到项目看板点确认按钮完成本次确认',
    }
  }
  return {
    success: false, confirmed: false, advanced: false,
    note: '用户未作答（取消/暂离）：节点未推进。稍后可重新发起 reqboard_ask_confirm',
  }
}

/**
 * 已作答 → 裁决（同步路径与后台续跑共用）。非肯定项只留痕不推进；肯定项走
 * \`applyConfirmDecision\`（落章 + 可选推进 + 批准计划的门合并开跑）。
 * 返回体形状与改造前逐字一致（output-contract 静态扫描逐键对账）。
 */
async function settleAnswers(
  deps: UseCaseDeps,
  exec: unknown,
  answers: readonly AskAnswer[],
  s: ConfirmSubmitted,
): Promise<Record<string, unknown>> {
  const answer = answers[0]
  const picked = answer?.selected?.[0] ?? answer?.custom ?? ''
  const affirmative = picked.length > 0 && picked === s.optionLabels[0]
  const nowTs = deps.clock.now()

  // ── 非肯定项：不推进，留痕，返回用户意见 ──────────────────────────
  if (!affirmative) {
    const userFeedback = answer?.custom?.trim() ?? ''
    await recordDeclinedConfirmation(deps, {
      requirementId: s.requirementId,
      windowKey: s.windowKey,
      question: s.question,
      picked,
      userFeedback,
      nowTs,
    })
    return {
      success: true,
      confirmed: false,
      advanced: false,
      user_choice: picked || '（未选）',
      user_feedback: userFeedback.length > 0 ? userFeedback : undefined,
      note: fmt('用户选择"{picked}"：未落章、未推进。{feedback}按用户意见修改后可重新发起确认', {
        picked: picked || '（未选）',
        feedback: userFeedback.length > 0 ? fmt('用户反馈：{fb}。', { fb: userFeedback }) : '',
      }),
    }
  }

  // ── 肯定项：落章（+ 可选推进）────────────────────────────────────
  const outcome = await applyConfirmDecision(deps, exec, {
    requirementId: s.requirementId,
    windowKey: s.windowKey,
    target: s.target,
    kind: s.kind,
    question: s.question,
    picked,
    nowTs,
    advance: s.advance,
  })
  return {
    success: true,
    confirmed: true,
    advanced: outcome.advanced,
    from: outcome.from,
    to: outcome.to,
    requirement_id: s.requirementId,
    ...(outcome.gateFailure !== undefined ? { gate_failure: outcome.gateFailure } : {}),
    note: outcome.note,
  }
}
