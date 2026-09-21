/**
 * 失败告警适配器（REQ-4842fe t8 / FR-13）：高优告警的唯一实现。
 *
 * 两条通道（都 best-effort，永不抛——告警失败不得反过来阻断暂停与留痕）：
 *  ① 宿主日志（logger，最高级别）——保证"响了"；
 *  ② 会话投递（投给需求来源窗口，复用 AgentDeliverer 这一唯一投递实现）。
 *
 * 为什么这里就是终点、不再外发（2026-09-21 用户裁定：**只有弹框**，requirement §8 #17）：
 * 失败后的唯一人工交互面 = 会话内弹框（三选一）；本适配器只把文本送到"弹框看得见"的两处
 * ——来源会话 + 宿主日志（排障），不另做告警通道、不发飞书、不接通知面。
 *
 * 投递内容 = **弹框指令壳**而非原始告警正文（2026-09-21 用户裁定 v2，w-2105d331 代录，
 * requirement §8 #18）：用户原话「我希望通过弹框的方式来交流，要不用户不知道重点，发生了
 * 什么」。原始正文作为 user 消息进入来源会话后，窗口 LLM 只能自由文本转述——重点被淹没、
 * 看不出"发生了什么/要我干嘛"。指令壳复用里程碑超时提醒同款机制（CaptureHook t09："从软
 * 纪律升级为到时触发"）：弹框必须由窗口在自己回合内发起，后台执行器无回合可弹，只能借
 * 来源窗口之手——指令壳就是这只手。宿主日志仍记原始正文（排障用，不受影响）。
 *
 * @module dsh-pmboard/adapters/FailureAlert
 */
import { fmt } from '../domain/text/fmt.js'
import type { FailureAlertPort } from '../application/ports.js'

export interface FailureAlertWiring {
  log: (message: string) => void
  deliver: (windowKey: string, text: string) => void
  windowFor: (requirementId: string) => string | undefined
}

/**
 * 弹框指令壳（§8 #18）：标题+正文是告警事实，指令段是给来源窗口 LLM 的处置纪律。
 * 题干长度纪律见 domain/limits.ts（弹框题干与选项共享滚动区，超限会被挤出可视区）。
 */
export function popupInstructionFor(title: string, content: string): string {
  // 逐行数组 + join：沿用消息卫生门禁的口径（禁止 '中文' + 拼接，改用 fmt 承载占位替换）。
  const instruction = [
    '—— 处置指令（给本窗口 LLM，不是给用户阅读的）：',
    '你绑定需求的实施链已暂停。不要长篇文字汇报，请立即调 ask_user_question（或当前可用的弹框确认工具）向用户弹框：',
    '· 题干 ≤80 字，说清三件事：哪条需求、停在哪张卡、为什么停（失败类别 + 一句话原因）；',
    '· 选项固定三项：重跑该卡 / 退回上游重新描述需求 / 取消该任务；',
    '· 用户点选后立即执行：①重跑=重开该需求 autoRun 并触发一次推进；②退回上游=reqboard_move 需求 implementing→design；③取消=走取消人工闸门。',
    '· 弹框通道不可用（无 UI）时，只回一行告知用户到项目看板处置，禁止输出长文。',
  ].join('\n')
  return fmt('{title}\n{content}\n\n{instruction}', { title, content, instruction })
}

export function createFailureAlert(wire: FailureAlertWiring): FailureAlertPort {
  return {
    alert: ({ requirementId, title, content }) => {
      const raw = fmt('{title}\n{content}', { title, content })
      try { wire.log(raw) } catch { /* 日志失败不阻断（宿主日志记原始正文，排障用） */ }
      try {
        const windowKey = wire.windowFor(requirementId)
        if (windowKey !== undefined && windowKey.length > 0) wire.deliver(windowKey, popupInstructionFor(title, content))
      } catch { /* 投递失败不阻断暂停语义 */ }
    },
  }
}
