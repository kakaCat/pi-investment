/**
 * H4 唤醒续跑（REQ-e3b6a0 t7 / FR-5）——链的**收尾动作**：把 agent 从"停下等人敲继续"叫起来。
 *
 * 消息组装按 **D5 分流**：
 *  · H2 真压缩过（`scratch.compacted`，提示词已在节点输入包里）→ **只发作答摘要**；
 *  · H2 跳过/降级 → 摘要 **+ 阶段纪律提示词全文**（否则这一步等于没注入纪律）。
 *
 * 【2026-09-26 修正两处实测缺陷】
 *  ① **缺开工令**：唤醒消息此前只有「状态通报 + 阶段纪律清单」，纪律清单讲的是**该交什么**，
 *     于是 agent 被叫醒后不知道该先做什么。现补「进入本阶段的第一步」——取自 domain 单点
 *     `STAGE_CHAIN[to].entry`（与节点输入包同源），不新写第二份文案。
 *  ② **空唤醒假话**：没压缩、也没取到提示词时（H3 skip/degraded），旧代码仍发
 *     「阶段纪律已随节点输入包一并给出」——实测 bug/spike/refactor 的 G0 正是这种情况。
 *     现按 `scratch.promptSkipped` 如实说明原因。
 *
 * 非肯定项同样要唤醒（带用户意见），否则人会以为"点了没反应"。投递失败只降级、不抛。
 *
 * @module dsh-pmboard/application/gate/handlers/h4-resume
 */
import { fmt } from '../../../domain/text/fmt.js'
import { STAGE_CHAIN } from '../../../domain/prompt/chain.js'
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

/**
 * 进入本阶段的第一个动作（kickoff 开工令）——domain 单点 STAGE_CHAIN.entry。
 * 未注册的阶段返回空串（不编造动作）。
 */
function entryActionOf(to: string): string {
  const step = (STAGE_CHAIN as Partial<Record<string, { entry?: string }>>)[to]
  return step?.entry ?? ''
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
        const negative = ctx.verdict !== 'affirmative'
        const prompt = scratch?.promptText
        const compacted = scratch?.compacted === true
        const includePrompt = !compacted && prompt !== undefined && prompt.length > 0
        const skipped = scratch?.promptSkipped
        // 缺陷①修正：肯定分支**必发开工令**（"叫醒了却不知道该干什么"是实测缺陷）。
        const entry = negative ? '' : entryActionOf(ctx.to)
        const entryBlock = entry.length === 0 ? '' : fmt('\n\n进入本阶段的第一步：{e}', { e: entry })
        // T-4（FR-10）：非肯定答复**不附任何纪律块**（只发作答摘要 + 用户意见）。
        // 肯定分支三分支必须**如实**：① 压缩过 = 纪律真在输入包里；② 取到词 = 随本条发全文；
        // ③ 都没发生 = 如实说明原因（缺陷②修正：不再谎称"已随节点输入包一并给出"）。
        const promptBlock = negative
          ? ''
          : includePrompt
            ? fmt('\n\n按以下阶段纪律继续：\n\n{p}', { p: prompt })
            : compacted
              ? '\n\n阶段纪律已随节点输入包一并给出，按其继续。'
              : skipped === undefined
                ? '\n\n本阶段未产出可注入的阶段纪律（取词未产出）；按节点输入包继续。'
                : fmt('\n\n本阶段未产出可注入的阶段纪律（{code}：{reason}）；按节点输入包继续。', { code: skipped.code, reason: skipped.reason })
        const text = fmt('{head}\n{answers}{entry}{block}', { head, answers: answerLine, entry: entryBlock, block: promptBlock })
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
