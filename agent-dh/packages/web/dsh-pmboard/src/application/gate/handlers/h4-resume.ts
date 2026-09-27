/**
 * H4 唤醒续跑（REQ-e3b6a0 t7 / FR-5）——链的**收尾动作**：把 agent 从"停下等人敲继续"叫起来。
 *
 * 【2026-XX-XX 全面Dive化】
 * 所有需求都在Dive模式下运行，不再需要followup投递到inbox。
 * H4统一返回skip，让Dive的roundDriver自己处理续跑。
 *
 * @module dsh-pmboard/application/gate/handlers/h4-resume
 */
import { fmt } from '../../../domain/text/fmt.js'
import type { ChainInput, GateHandler, HandlerOutcome } from '../GatePostChain.js'

export interface H4ResumeDeps {
  // 不再需要任何依赖
}

export function createH4ResumeHandler(deps: H4ResumeDeps): GateHandler {
  return {
    name: 'h4-resume',
    async run({ ctx }: ChainInput): Promise<HandlerOutcome> {
      // 所有需求都在Dive模式下运行，Dive的roundDriver会自己处理续跑
      // 这里只需要返回skip，表示"唤醒"这一步由Dive负责
      return {
        kind: 'skip',
        code: 'dive_handles_resume',
        reason: fmt('闸门 {gate} 确认后的续跑由Dive自动处理', { gate: ctx.gate })
      }
    },
  }
}