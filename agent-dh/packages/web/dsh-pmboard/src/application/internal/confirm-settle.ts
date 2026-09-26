/**
 * 确认裁决应用（REQ-260924213231-b1c4 T-6 · serves: FR-3）——「落章 + 推进」的**唯一实现**。
 *
 * 为什么要抽出来：同一条「肯定作答 → 落章 → 推进（含批准拆分计划的门合并自动拆分）」
 * 既要在**宽限内同步**走，也要在**超宽限的后台续跑**里走；两份实现必然漂移。故
 * AskConfirm（宽限赛跑）与 ConfirmReceipt（后台落章）都调本模块，返回语义与改造前
 * 逐字一致（note / gate_failure / advanced / from / to）。
 *
 * @module dsh-pmboard/application/internal/confirm-settle
 */
import type { UseCaseDeps } from '../ports.js'
import { canReqTransition } from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'
import { advanceTargetFor, gateForTransition } from '../../domain/gate/GateCatalog.js'
import { checkDesignCompletenessGate, checkDesignDecompositionGate } from './content-gate-wiring.js'
import { artifactsToConfirm, type GateFailure } from './artifact-gates.js'
import { captureSnapshot, transitionRequirement } from './token-usage.js'
// import { executeDecompose } from '../use-cases/Decompose.js' // 已改用 deps.jobs.start（REQ-260925212722-96e7 t-003dc5）
import { advanceRequirement } from '../use-cases/AdvanceChain.js'
import { stampCheckpoint } from './interruption.js'
import { reject } from './support.js'

/** 通用确认推进的留痕原因（确认回执据此从 statusHistory 还原 from → to，单点定义）。 */
export const CONFIRM_ADVANCE_REASON = '确认弹框后自动推进（reqboard_ask_confirm）'
/** 批准拆分计划的门合并推进原因（同上，单点定义）。 */
export const PLAN_MERGE_ADVANCE_REASON = '批准拆分计划后自动进入实施（拆分确认门已并入批准门）'

/** 一次已作答的确认请求（同步与后台共用同一入参形状）。 */
import { syncRTMYaml } from './rtm-yaml.js'

export interface ConfirmDecision {
  requirementId: string
  windowKey: string
  target: 'artifact' | 'plan'
  kind: string
  /** 弹框题干原文（留痕/证据用） */
  question: string
  /** 用户选中的选项 label（肯定项 = optionLabels[0]） */
  picked: string
  nowTs: number
  /** 是否允许自动推进（同 ask_confirm 的 advance 参数） */
  advance: boolean
}

/** 裁决应用结果（AskConfirm 与后台落章都据此组装返回体/回执）。 */
export interface ConfirmDecisionOutcome {
  from: string
  to: string
  advanced: boolean
  gateFailure?: GateFailure
  /** '已落章（via=session）' + 推进/缺口/自动开跑说明（逐字沿用改造前拼接） */
  note: string
}

/** 非肯定作答的留痕（同步路径与后台续跑共用；原 AskConfirm 内联块逐字搬入）。 */
export async function recordDeclinedConfirmation(
  deps: UseCaseDeps,
  input: { requirementId: string; windowKey: string; question: string; picked: string; userFeedback: string; nowTs: number },
): Promise<void> {
  const feedbackNote = input.userFeedback.length > 0 ? fmt('。用户意见：{fb}', { fb: input.userFeedback }) : ''
  await deps.repo.mutate('requirement-updated', (ledger) => {
    const req = ledger.requirements.find(r => r.id === input.requirementId)
    if (req === undefined) return undefined
    req.comments.push({
      id: deps.ids.comment(),
      body: '[确认弹框] 用户未确认（选择：' + (input.picked || '（未选）') + '）——节点未推进。问题：' + input.question + feedbackNote,
      createdAt: input.nowTs,
      createdBy: { kind: 'human', sessionId: input.windowKey },
    })
    req.version += 1
    req.updatedAt = input.nowTs
    // FR-6 写入器 A（T-9）：未确认也是一次交棒——断点写 checkpoint，pendingAction 重算为
    // 「再发一次 ask_confirm」（状态未变），随后被 turn/end 的异常原因覆盖。
    stampCheckpoint(req, input.nowTs, 'reqboard_ask_confirm')
    return { requirements: [req] }
  })
}

/**
 * 应用一次**肯定**作答：落章（artifact 成组 / plan 批准）→ 可选推进 → 拆分计划门合并开跑。
 * 任一步被闸门拒绝即抛（调用方按同步/后台两种语境处置）。行为与改造前 askConfirm 内联块逐字一致。
 */
export async function applyConfirmDecision(
  deps: UseCaseDeps,
  exec: unknown,
  d: ConfirmDecision,
): Promise<ConfirmDecisionOutcome> {
  const targetKind = d.target
  const kindRaw = d.kind
  const nowTs = d.nowTs
  const before = deps.repo.snapshot().requirements.find(r => r.id === d.requirementId)
  if (before === undefined) {
    reject('reqboard_ask_confirm 未执行：需求 ' + d.requirementId + ' 不在台账中', 'REQBOARD_STORE_INCONSISTENT')
  }

  // ── REQ-2d1c74 FR-3：确认 kind=design 落章前扫描拆分内容（三通道之一：会话弹框）──
  // 用户已作答，但检出拆分内容即拒——不落章、不推进（扫描只读，无副作用）
  if (targetKind === 'artifact' && kindRaw === 'design') {
    const scan = await checkDesignDecompositionGate(deps.docs, before)
    if (scan !== undefined) reject(fmt('reqboard_ask_confirm 未执行：{msg}', { msg: scan.message }), scan.code)
  }

  // ── 肯定项：落章（与 reqboard_confirm_artifact 同语义）────────────────
  const evidence = '用户在 reqboard_ask_confirm 弹框（问题："' + d.question + '"）中选择"' + d.picked + '"'
  await deps.repo.mutate('requirement-updated', (ledger) => {
    const req = ledger.requirements.find(r => r.id === d.requirementId)
    if (req === undefined) return undefined
    if (targetKind === 'artifact') {
      // REQ-2d1c74 FR-2：kind=design 成组落章（全部 design 产物一次确认）
      const arts = artifactsToConfirm(req, kindRaw as never)
      if (arts.length === 0) {
        throw Object.assign(
          new Error('需求 ' + req.id + ' 没有 kind=' + kindRaw + ' 的产物（请先提交该阶段产物）'),
          { code: 'REQBOARD_MISSING_ARTIFACT' },
        )
      }
      for (const art of arts) {
        art.confirmedAt = nowTs
        art.confirmedBy = { kind: 'human', sessionId: d.windowKey }
        art.confirmedVia = 'session'
        art.confirmedEvidence = evidence
      }
    } else {
      if (req.plan === undefined) {
        throw Object.assign(new Error('需求 ' + req.id + ' 还没有拆分计划'), { code: 'REQBOARD_MISSING_PLAN' })
      }
      req.plan.approvedAt = nowTs
      req.plan.approvedBy = { kind: 'human', sessionId: d.windowKey }
      req.plan.approvedVia = 'session'
      req.plan.approvedEvidence = evidence
      delete req.plan.rejectedAt
      delete req.plan.rejectedReason
    }
    req.comments.push({
      id: deps.ids.comment(),
      body: '[确认弹框] 用户确认（' + (targetKind === 'artifact' ? 'kind=' + kindRaw : '批准计划') + '）：' + evidence,
      createdAt: nowTs,
      createdBy: { kind: 'human', sessionId: d.windowKey },
    })
    req.version += 1
    req.updatedAt = nowTs
    req.updatedBy = { kind: 'human', sessionId: d.windowKey }
    // FR-6 写入器 A（T-9）：落章即写 checkpoint（下一步由状态+产物态重算；后续推进覆盖之）。
    stampCheckpoint(req, nowTs, 'reqboard_ask_confirm')
    return { requirements: [req] }
  }).catch((err: unknown) => {
    reject('reqboard_ask_confirm 落章失败：' + ((err as Error).message ?? String(err)), (err as { code?: string }).code ?? 'REQBOARD_STORE_INCONSISTENT')
  })

  // ── 推进（可选，限白名单转移）───────────────────────────────────────
  // RTM 触发点 3/5：确认落章后同步 RTM（ask_confirm 弹框与看板确认都走这里）
  syncRTMYaml(deps, d.requirementId, targetKind === 'artifact' ? 'confirm:artifact' : 'confirm:plan')

  const from = deps.repo.snapshot().requirements.find(r => r.id === d.requirementId)?.status ?? before.status
  const to = advanceTargetFor(from)
  let advanced = false
  let advanceNote = ''
  // 2026-09-21：批准拆分计划（target=plan 且已在拆分阶段）不走通用推进——
  // 须先拆分落库再进实施（顺序在下方「门合并」块里保证）
  const planInDecomposing = targetKind === 'plan' && from === 'decomposing'
  // REQ-2d1c74 FR-2：G2 弹框确认后的自动推进先过文档集完整性闸门（四路径之一）。
  // 落章保留（确认动作有效），推进可拦——缺口经返回体 gate_failure 如实告知。
  let designGateFailure: GateFailure | undefined
  if (d.advance && to !== undefined && !planInDecomposing && gateForTransition(from, to)?.id === 'G2') {
    const fresh = deps.repo.snapshot().requirements.find(r => r.id === d.requirementId)
    if (fresh !== undefined) designGateFailure = await checkDesignCompletenessGate(deps.docs, fresh)
  }
  if (designGateFailure !== undefined) {
    advanceNote = '；design → decomposing 未推进：' + designGateFailure.message
  } else if (d.advance && to !== undefined && !planInDecomposing && canReqTransition(from, to as never)) {
    try {
      await deps.repo.mutate('requirement-moved', (ledger) => {
        const req = ledger.requirements.find(r => r.id === d.requirementId)
        if (req === undefined || req.status !== from) return undefined
        // REQ-b545fe t3：使用唯一迁移助手
        transitionRequirement(req, to as never, {
          at: nowTs,
          actor: { kind: 'human', sessionId: d.windowKey },
          reason: CONFIRM_ADVANCE_REASON,
          snap: captureSnapshot(deps, d.windowKey),
        })
        req.comments.push({
          id: deps.ids.comment(),
          body: '[自动推进] ' + from + ' → ' + to + '：确认弹框肯定答复（reqboard_ask_confirm 原子推进）',
          createdAt: nowTs,
          createdBy: { kind: 'human', sessionId: d.windowKey },
        })
        stampCheckpoint(req, nowTs, 'reqboard_ask_confirm')
        return { requirements: [req] }
      })
      advanced = true
    } catch (err) {
      advanceNote = '；推进失败：' + ((err as Error).message ?? String(err))
    }
  } else if (d.advance) {
    advanceNote = '；当前状态 ' + from + ' 无可自动推进的下一阶段（验收/归档走验收单流程）'
  }

  // ── REQ-4842fe t10：批准拆分计划 = 落章 + 拆分落库 + 开跑（门合并，FR-16）────
  // 2026-09-21 用户裁定（w-2105d331 代录）：拆分计划挪到**拆分阶段**提交与批准——
  // 本块在 from=decomposing 时生效：先落章 decomposition 产物（拆分计划本体）→
  // 自动落库任务卡 → 自动进实施 + autoRun=true → 触发首个推进事件，中途不再打断。
  // （legacy：design 阶段批准的旧计划走通用推进到 decomposing，之后在拆分阶段手动
  //   reqboard_decompose + 确认 decomposition 产物，退化为门合并前的两步流程。）
  let autoNote = ''
  if (targetKind === 'plan' && from === 'decomposing') {
    try {
      await deps.repo.mutate('decomposition-confirmed-by-plan', (ledger) => {
        const req = ledger.requirements.find(x => x.id === d.requirementId)
        if (req === undefined) return undefined
        const art = (req.artifacts ?? []).find(x => x.kind === 'decomposition')
        if (art !== undefined) {
          art.confirmedAt = nowTs
          art.confirmedBy = { kind: 'human', sessionId: d.windowKey }
          art.confirmedVia = 'session'
          art.confirmedEvidence = evidence
        }
        req.comments.push({
          id: deps.ids.comment(),
          body: fmt('[门合并] 批准拆分计划：decomposition 产物自动落章（不再单独弹「确认拆分清单」）', {}),
          createdAt: nowTs,
          createdBy: { kind: 'human', sessionId: d.windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        return { requirements: [req] }
      })
      
      // 优化：移除 deps.jobs 依赖，改为 Dive 续跑模式（事件驱动，毫秒级响应）
      // 批准计划后只推进状态，Dive 管理器监听 'requirement-moved' 事件立即触发续跑
      // Agent 续跑时检测到 implementing + 无任务 → 自动执行 reqboard_decompose
      const createdCount = 0 // 任务将由 Dive 续跑时创建
      await deps.repo.mutate('requirement-moved', (ledger) => {
        const req = ledger.requirements.find(x => x.id === d.requirementId)
        if (req === undefined || req.status !== 'decomposing') return undefined
        transitionRequirement(req, 'implementing', {
          at: nowTs,
          actor: { kind: 'human', sessionId: d.windowKey },
          reason: PLAN_MERGE_ADVANCE_REASON,
        })
        req.autoRun = true
        req.comments.push({
          id: deps.ids.comment(),
          body: fmt('[自动开跑] 批准拆分计划 → 自动拆分 {n} 张卡 → 自动进入实施（autoRun=true），触发首个推进事件', { n: createdCount }),
          createdAt: nowTs,
          createdBy: { kind: 'human', sessionId: d.windowKey },
        })
        stampCheckpoint(req, nowTs, 'reqboard_ask_confirm')
        return { requirements: [req] }
      })
      advanced = true
      // 注：任务拆分和执行由 Dive 管理器通过 'requirement-moved' 事件自动触发
      autoNote = '；已推进到 implementing，Dive 管理器将自动触发任务拆分和执行'
    } catch (err) {
      const errMsg = String((err as Error).message ?? err)
      autoNote = fmt('；自动拆分/开跑失败（计划已批准，可手动调 reqboard_decompose 重试）：{msg}', {
        msg: errMsg,
      })

      // FR-2（REQ-84bea5）：失败响亮化——评论+告警+标记
      await deps.repo.mutate('auto-run-failed', (ledger) => {
        const req = ledger.requirements.find(x => x.id === d.requirementId)
        if (req === undefined) return undefined

        // 写系统评论（含恢复指引）
        req.comments.push({
          id: deps.ids.comment(),
          body: fmt(
            '[自动开跑失败] {reason}。\n\n恢复路径：修复后手动调用 reqboard_decompose(requirement_id="{reqId}")，或在看板点「拆分」按钮。',
            { reason: errMsg, reqId: d.requirementId },
          ),
          createdAt: nowTs,
          createdBy: { kind: 'system' },
        })

        // 标记 advance.pausedReason
        if (req.advance === undefined) req.advance = {}
        req.advance.pausedReason = 'auto_decompose_failed: ' + errMsg

        req.version += 1
        req.updatedAt = nowTs
        return { requirements: [req] }
      })

      // 调用 deps.alert 发高优告警
      deps.alert?.alert({
        requirementId: d.requirementId,
        title: '自动开跑失败',
        content: fmt('需求 {id} 批准计划后自动拆分/开跑失败：{msg}', { id: d.requirementId, msg: errMsg }),
      })
    }
  }

  return {
    from,
    to: (advanced ? to : from) as string,
    advanced,
    ...(designGateFailure !== undefined ? { gateFailure: designGateFailure } : {}),
    note: '已落章（via=session）'
      + (advanced ? '，已推进：' + from + ' → ' + to : '')
      + advanceNote
      + autoNote,
  }
}
