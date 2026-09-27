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
  type ArtifactKind,
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
  outcomeOf,
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
      // 死锁修复（2026-09-27 用户裁定「需要弹框的必须出现弹框来确认」）：计划已批准但 G3
      // 闸门**未推进**（自动拆分失败后手动补拆、或落库收尾报错）→ 产物章已落、状态仍停在
      // decomposing。此时早返回会把节点锁死（agent 无法越人工门），并把唯一出口逼成"文字证据"
      // 旁路。故该情形不得早返回，继续走弹框；确认后由 settle 幂等推进（不重复落卡）。
      const planAwaitingAdvance = targetKind === 'plan'
        && targetReq.plan?.approvedAt !== undefined
        && targetReq.status === 'decomposing'
      if (alreadyConfirmed && !planAwaitingAdvance) {
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

      // ── 等待语义（REQ-260927123256-196b FR-1 / FR-3 / I-1）────────────────
      // 缺省 = **阻塞**：await ask 直到作答 / 取消 / 中止；只有显式正数 inline_grace_ms 才启用
      // 「宽限赛跑 → 超时挂起」逃生舱（非阻塞必须显式声明，缺省不再 30s 自动放行）。
      const port = deps.pendingConfirms
      if (graceRaw !== undefined && port === undefined) {
        reject(
          fmt('reqboard_ask_confirm 未执行：显式 inline_grace_ms（{g}）需要挂起确认能力，本实例未装配'
            + '（pendingConfirms 缺省）——不传宽限即缺省阻塞等待，或修复装配（REQBOARD_NONBLOCK_UNAVAILABLE）',
            { g: String(graceRaw) }),
          'REQBOARD_NONBLOCK_UNAVAILABLE',
        )
      }
      // 进入等待前：先 settle 本窗口旧的未作答记录（重新发起 = 覆盖旧记录），再登记本次 ticket。
      // 登记与阻塞/非阻塞无关（I-4）：停手守卫据此在**整个等待期**生效。
      let ticket: string | undefined
      if (port !== undefined) {
        for (let stale = port.pendingForWindow(windowKey); stale !== undefined; stale = port.pendingForWindow(windowKey)) {
          port.settle(stale.ticket, { confirmed: false, advanced: false })
        }
        ticket = port.register({
          windowKey,
          requirementId: targetReq.id,
          target: targetKind as 'artifact' | 'plan',
          ...(targetKind === 'artifact' ? { kind: kindRaw as ArtifactKind } : {}),
        }).ticket
      }

      // ① 缺省阻塞：等到作答 / 取消 / 中止（FR-1；返回体恢复旧同步语义，无 pending/ticket）
      if (graceRaw === undefined) {
        let answers: readonly AskAnswer[]
        try {
          answers = await ask
        } catch (err) {
          return handleAskFailure(deps, exec, err, ticket, targetReq.id) as never
        }
        const body = await settleAnswers(deps, exec, answers, submitted)
        if (port !== undefined && ticket !== undefined) port.settle(ticket, outcomeOf(body))
        return body
      }

      // ② 显式正数宽限：宽限赛跑；宽限内作答 = 同步落章；超宽限 = 挂起 ticket 立即返回（FR-3）
      const raced = await raceAsk(ask, graceRaw as number)
      if (raced.kind === 'answered') {
        const body = await settleAnswers(deps, exec, raced.answers, submitted)
        if (port !== undefined && ticket !== undefined) port.settle(ticket, outcomeOf(body))
        return body
      }
      if (raced.kind === 'rejected') {
        return handleAskFailure(deps, exec, raced.err, ticket, targetReq.id) as never
      }
      return suspendConfirm(deps, ask, submitted, ticket!, (answers) => settleAnswers(deps, exec, answers, submitted)) as never
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
 * 弹框在等待/赛跑期间失败或中止的统一处置（REQ-260927123256-196b FR-4 / I-1）：
 *   · `ASK_ABORTED` 或 `exec.signal.aborted` → **响亮留痕**：`markInterrupted(ticket)`
 *     （守卫继续拦，直到人作答或显式解除），返回 `pending:true + ticket + interrupted:true`；
 *   · 其余（`ASK_CANCELLED` 用户取消 / `DELEGATED_CALLER` 等降级）→ `settle`（守卫放行）后
 *     走**与改造前逐字一致**的 `degradedAnswer`。
 *
 * 未装配注册表时没有可留痕的 ticket（仅测试/旧装配形态）：中止按中性降级返回——
 * 绝不把一次中止静默伪装成「已确认」或「成功」。
 */
function handleAskFailure(
  deps: UseCaseDeps,
  exec: unknown,
  err: unknown,
  ticket: string | undefined,
  requirementId: string,
): unknown {
  const port = deps.pendingConfirms
  const code = (err as { code?: string }).code ?? ''
  const aborted = code === 'ASK_ABORTED'
    || (exec as { signal?: { aborted?: boolean } } | undefined)?.signal?.aborted === true
  if (aborted && port !== undefined && ticket !== undefined) {
    port.markInterrupted(ticket)
    return interruptedBody(ticket, requirementId)
  }
  if (port !== undefined && ticket !== undefined) port.settle(ticket, { confirmed: false, advanced: false })
  return degradedAnswer(err)
}

/**
 * 阻塞等待被中止的返回体（I-1 中止分支）：`pending:true + ticket + interrupted:true`。
 * note 必含两条恢复命令（取回执 / 看板确认）与「收到作答前不得产出下游产物」。
 */
function interruptedBody(ticket: string, requirementId: string): Record<string, unknown> {
  return {
    success: false,
    confirmed: false,
    advanced: false,
    pending: true,
    ticket,
    requirement_id: requirementId,
    interrupted: true,
    note: fmt(
      '本次确认等待已被中止（弹框可能已消失），已留下可查的挂起记录（ticket={t}）。'
      + '**收到作答前不得产出下游产物**（本窗口 reqboard_submit / reqboard_decompose / reqboard_move / '
      + 'reqboard_task_move 会被代码级拒绝）。恢复路径：① 调 reqboard_confirm_receipt(ticket="{t}") 取回执；'
      + '② 到项目看板点确认按钮；③ 重新发起 reqboard_ask_confirm 覆盖旧记录。',
      { t: ticket },
    ),
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
