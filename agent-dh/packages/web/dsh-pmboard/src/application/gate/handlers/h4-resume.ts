/**
 * H4 唤醒续跑（REQ-e3b6a0 t7 / FR-5）——链的**收尾动作**：把 agent 从"停下等人敲继续"叫起来。
 *
 * 消息组装按 **D5 分流**：
 *  · H2 真压缩过（`scratch.compacted`，提示词已在节点输入包里）→ **只发作答摘要**；
 *  · H2 跳过/降级 → 摘要 **+ 阶段纪律提示词全文**（否则这一步等于没注入纪律）。
 *
 * 非肯定项同样要唤醒（带用户意见），否则人会以为"点了没反应"。投递失败只降级、不抛。
 *
 * @module dsh-pmboard/application/gate/handlers/h4-resume
 */
import { fmt } from '../../../domain/text/fmt.js'
import type { AgentDeliveryPort } from '../../ports.js'
import type { ConfirmContext } from '../../../domain/gate/GateSpec.js'
import type { ChainInput, GateHandler, HandlerOutcome } from '../GatePostChain.js'
import { reasonOf } from './shared.js'

export interface H4ResumeDeps {
  delivery: AgentDeliveryPort
  /** 投递署名（写进 message.source.plugin）。 */
  plugin?: string
}

/** 作答摘要（选项 + 自定义意见）——一句人能读懂的话。 */
function describeAnswers(ctx: ConfirmContext): string {
  const parts: string[] = []
  for (const a of ctx.answers) {
    const picked = (a.selected ?? []).join('/')
    if (picked.length > 0) parts.push(fmt('选择「{picked}」', { picked }))
    if (a.custom !== undefined && a.custom.trim().length > 0) parts.push(fmt('意见「{c}」', { c: a.custom.trim() }))
  }
  return parts.length === 0 ? '（未记录具体作答）' : parts.join('；')
}

export function createH4ResumeHandler(deps: H4ResumeDeps): GateHandler {
  return {
    name: 'h4-resume',
    async run({ ctx, scratch }: ChainInput): Promise<HandlerOutcome> {
      try {
        // REQ-260924002956-f37c BUG-2：无 from 的门（G0 立项门）没有"当前节点"可言——
        // 不能把 to 当现状印成"节点仍在 brainstorming"（那是目标态，不是现状）。
        const head = ctx.verdict === 'affirmative'
          ? fmt('【闸门确认】{gate} 已确认，节点推进到 {to}。', { gate: ctx.gate, to: ctx.to })
          : ctx.from === undefined
            ? fmt('【闸门待改进】{gate} 未通过。', { gate: ctx.gate })
            : fmt('【闸门待改进】{gate} 未通过，节点仍在 {from}。', { gate: ctx.gate, from: ctx.from })
        const answerLine = describeAnswers(ctx)
        const prompt = scratch?.promptText
        const includePrompt = scratch?.compacted !== true && prompt !== undefined && prompt.length > 0
        // T-4（FR-10）：非肯定答复**不附任何纪律块**（只发作答摘要 + 用户意见）；
        // 肯定分支行为不变（防"修反"）。
        const negative = ctx.verdict !== 'affirmative'
        const promptBlock = negative
          ? ''
          : includePrompt
            ? fmt('\n\n按以下阶段纪律继续：\n\n{p}', { p: prompt })
            : '\n\n阶段纪律已随节点输入包一并给出，按其继续。'
        const text = fmt('{head}\n{answers}{block}', { head, answers: answerLine, block: promptBlock })
        const result = deps.delivery.deliver(ctx.windowKey, {
          text,
          ...(deps.plugin === undefined ? {} : { plugin: deps.plugin }),
        })
        if (result.delivered) return { kind: 'continue' }
        return { kind: 'degraded', code: 'not_delivered', reason: result.reason ?? '投递未成功' }
      } catch (error) {
        return { kind: 'degraded', code: 'h4_threw', reason: fmt('H4 唤醒异常：{err}', { err: reasonOf(error) }) }
      }
    },
  }
}
