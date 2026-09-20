/**
 * AskConfirm 用例（REQ-47939a t6）——从 host/agent-tools.ts 的 defineAskConfirmTool / reqboard_ask_confirm 工厂**逐字搬入**编排。
 *
 * 零行为变更：拒绝条件、错误码与消息文案与搬迁前一致；规则仍单点于 domain/。
 *
 * @module dsh-pmboard/application/use-cases/AskConfirm
 */
import type { UseCaseDeps } from '../ports.js'
import {
  ALL_ARTIFACT_KINDS,
  canReqTransition,
  normalizeText,
} from '../../shared/protocol.js'
import { DEFAULT_CONFIRM_OPTIONS } from '../../domain/text/labels.js'
import { clip, fmt } from '../../domain/text/fmt.js'
import { LIMITS } from '../../domain/limits.js'
import { advanceTargetFor, gateFromStage } from '../../domain/gate/GateCatalog.js'
import { captureSnapshot, transitionRequirement } from '../internal/token-usage.js'
import { openRequirementsFor } from '../internal/window.js'
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
        question?: unknown; options?: unknown; advance?: unknown
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
      const optionLabels = options.length > 0 ? options : [...DEFAULT_CONFIRM_OPTIONS]

      const snapshot = deps.repo.snapshot()
      const bound = openRequirementsFor(snapshot, windowKey)
      if (bound.length === 0) reject('reqboard_ask_confirm 未执行：本窗口没有绑定中的需求', 'REQBOARD_NO_BOUND_REQ')
      const targetReq = explicitId.length > 0 ? bound.find(r => r.id === explicitId) : bound[0]
      if (targetReq === undefined) {
        reject('reqboard_ask_confirm 未执行：需求 ' + explicitId + ' 不是本窗口绑定的进行中需求', 'REQBOARD_NOT_BOUND_TO_WINDOW')
      }

      // ── 弹框（userQuestions 服务接缝，经 UserQuestionPort）────────────────
      if (!deps.questions.available()) {
        return {
          success: false, confirmed: false, advanced: false, fallback: 'board',
          note: '弹框通道不可用（userQuestions 服务缺失）：请用户到项目看板点确认按钮；或由 agent 改用 ask_user_question + reqboard_confirm_artifact 两步走',
        } as never
      }
      let answers: { id?: string; selected?: string[]; custom?: string }[] = []
      // 闸门声明（REQ-e3b6a0 t7）：由「作答前所处阶段」查闸门目录得到，装饰器据此登记后置链。
      const gateId = gateFromStage(targetReq.status)?.id
      try {
        answers = [...await deps.questions.ask([{
          id: 'confirm',
          question,
          header: '确认',
          options: optionLabels.map((label, i) => ({ label, ...(i === 0 ? { description: '确认后自动落章并推进' } : {}) })),
        }], {
          ...(exec.agent !== undefined ? { agent: exec.agent } : {}),
          signal: (exec as { signal?: unknown }).signal,
          ...(gateId === undefined ? {} : { gate: gateId }),
        })]
      } catch (err) {
        const code = (err as { code?: string }).code ?? ''
        if (code === 'DELEGATED_CALLER' || code === 'CALLER_NOT_LIVE') {
          return {
            success: false, confirmed: false, advanced: false, fallback: 'board',
            note: '当前调用方无弹框权限（subagent/非活窗口）：请用户到项目看板点确认按钮完成本次确认',
          } as never
        }
        // ASK_ABORTED 等：用户暂离/取消——中性返回，不算错误
        return {
          success: false, confirmed: false, advanced: false,
          note: '用户未作答（取消/暂离）：节点未推进。稍后可重新发起 reqboard_ask_confirm',
        } as never
      }

      const answer = answers[0]
      const picked = answer?.selected?.[0] ?? answer?.custom ?? ''
      const affirmative = picked.length > 0 && picked === optionLabels[0]
      const nowTs = deps.clock.now()

      // ── 非肯定项：不推进，留痕，返回用户意见 ──────────────────────────
      if (!affirmative) {
        // 用户的自定义输入作为修改意见（如果有的话）
        const userFeedback = answer?.custom?.trim() ?? ''
        const feedbackNote = userFeedback.length > 0 ? fmt('。用户意见：{fb}', { fb: userFeedback }) : ''
        
        await deps.repo.mutate('requirement-updated', (ledger) => {
          const req = ledger.requirements.find(r => r.id === targetReq.id)
          if (req === undefined) return undefined
          req.comments.push({
            id: deps.ids.comment(),
            body: '[确认弹框] 用户未确认（选择：' + (picked || '（未选）') + '）——节点未推进。问题：' + question + feedbackNote,
            createdAt: nowTs,
            createdBy: { kind: 'human', sessionId: windowKey },
          })
          req.version += 1
          req.updatedAt = nowTs
          return { requirements: [req] }
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
        } as never
      }

      // ── 肯定项：落章（与 reqboard_confirm_artifact 同语义）────────────────
      const evidence = '用户在 reqboard_ask_confirm 弹框（问题："' + question + '"）中选择"' + picked + '"'
      await deps.repo.mutate('requirement-updated', (ledger) => {
        const req = ledger.requirements.find(r => r.id === targetReq.id)
        if (req === undefined) return undefined
        if (targetKind === 'artifact') {
          const art = (req.artifacts ?? []).find(x => x.kind === kindRaw)
          if (art === undefined) {
            throw Object.assign(
              new Error('需求 ' + req.id + ' 没有 kind=' + kindRaw + ' 的产物（请先提交该阶段产物）'),
              { code: 'REQBOARD_MISSING_ARTIFACT' },
            )
          }
          art.confirmedAt = nowTs
          art.confirmedBy = { kind: 'human', sessionId: windowKey }
          art.confirmedVia = 'session'
          art.confirmedEvidence = evidence
        } else {
          if (req.plan === undefined) {
            throw Object.assign(new Error('需求 ' + req.id + ' 还没有拆分计划'), { code: 'REQBOARD_MISSING_PLAN' })
          }
          req.plan.approvedAt = nowTs
          req.plan.approvedBy = { kind: 'human', sessionId: windowKey }
          req.plan.approvedVia = 'session'
          req.plan.approvedEvidence = evidence
          delete req.plan.rejectedAt
          delete req.plan.rejectedReason
        }
        req.comments.push({
          id: deps.ids.comment(),
          body: '[确认弹框] 用户确认（' + (targetKind === 'artifact' ? 'kind=' + kindRaw : '批准计划') + '）：' + evidence,
          createdAt: nowTs,
          createdBy: { kind: 'human', sessionId: windowKey },
        })
        req.version += 1
        req.updatedAt = nowTs
        req.updatedBy = { kind: 'human', sessionId: windowKey }
        return { requirements: [req] }
      }).catch((err: unknown) => {
        reject('reqboard_ask_confirm 落章失败：' + ((err as Error).message ?? String(err)), (err as { code?: string }).code ?? 'REQBOARD_STORE_INCONSISTENT')
      })

      // ── 推进（可选，限白名单转移）───────────────────────────────────────
      const from = targetReq.status
      const to = advanceTargetFor(from)
      let advanced = false
      let advanceNote = ''
      if (advance && to !== undefined && canReqTransition(from, to as never)) {
        try {
          await deps.repo.mutate('requirement-moved', (ledger) => {
            const req = ledger.requirements.find(r => r.id === targetReq.id)
            if (req === undefined || req.status !== from) return undefined
            // REQ-b545fe t3：使用唯一迁移助手
            transitionRequirement(req, to as never, {
              at: nowTs,
              actor: { kind: 'human', sessionId: windowKey },
              reason: '确认弹框后自动推进（reqboard_ask_confirm）',
              snap: captureSnapshot(deps, windowKey),
            })
            req.comments.push({
              id: deps.ids.comment(),
              body: '[自动推进] ' + from + ' → ' + to + '：确认弹框肯定答复（reqboard_ask_confirm 原子推进）',
              createdAt: nowTs,
              createdBy: { kind: 'human', sessionId: windowKey },
            })
            return { requirements: [req] }
          })
          advanced = true
        } catch (err) {
          advanceNote = '；推进失败：' + ((err as Error).message ?? String(err))
        }
      } else if (advance) {
        advanceNote = '；当前状态 ' + from + ' 无可自动推进的下一阶段（验收/归档走验收单流程）'
      }

      return {
        success: true,
        confirmed: true,
        advanced,
        from,
        to: advanced ? to : from,
        requirement_id: targetReq.id,
        note: '已落章（via=session）' + (advanced ? '，已推进：' + from + ' → ' + to : '') + advanceNote,
      } as never
    }