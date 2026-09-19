/**
 * 弹框通道适配器（REQ-47939a t5 / ports.ts UserQuestionPort）——`deps.userQuestions` 接缝。
 *
 * reqboard_ask_confirm / accept_sheet 需要向用户弹框；服务可能未注入（子代理/无 UI/服务缺失）。
 * available() 给出可用性判定，ask() 在不可用时抛带 code 的错误（调用方据此返回 fallback=board）。
 *
 * 自动继续扩展：支持在用户回答后自动注入继续消息（agents.followup），让 agent 无需等待
 * 用户手动输入"继续"就能执行后续步骤。仅用于 pmboard 业务工具（reqboard_ask_confirm /
 * reqboard_accept_sheet），不影响通用的 ask_user_question。
 *
 * @module dsh-pmboard/adapters/UserQuestionsAdapter
 */
import type { AskAnswer, AskQuestion, UserQuestionPort } from '../application/ports.js'

interface RawQuestionService {
  ask?: (req: unknown) => Promise<{ answers?: AskAnswer[] }>
}

export class UserQuestionsAdapter implements UserQuestionPort {
  private readonly resolve: () => unknown
  private readonly onAnswered?: (windowKey: string, config: {
    message: string
    answers: readonly AskAnswer[]
  }) => void

  constructor(
    resolve: () => unknown,
    onAnswered?: (windowKey: string, config: {
      message: string
      answers: readonly AskAnswer[]
    }) => void
  ) {
    this.resolve = resolve
    this.onAnswered = onAnswered
  }

  available(): boolean {
    const svc = this.resolve() as RawQuestionService | undefined
    return typeof svc?.ask === 'function'
  }

  async ask(
    questions: readonly AskQuestion[],
    opts: { 
      agent?: unknown
      signal?: unknown
      autoContinue?: {
        message: string
        condition?: (answers: readonly AskAnswer[]) => boolean
      }
    },
  ): Promise<readonly AskAnswer[]> {
    const svc = this.resolve() as RawQuestionService | undefined
    if (typeof svc?.ask !== 'function') {
      throw Object.assign(new Error('弹框通道不可用（userQuestions 服务缺失）'), { code: 'REQBOARD_NO_UI' })
    }
    
    const result = await svc.ask({
      questions,
      ...(opts.agent !== undefined ? { agent: opts.agent } : {}),
      signal: opts.signal,
    })
    
    const answers = result.answers ?? []

    // ✨ 自动继续 hook 触发点
    if (opts.autoContinue && this.onAnswered && answers.length > 0) {
      const shouldContinue = opts.autoContinue.condition 
        ? opts.autoContinue.condition(answers)
        : true // 默认：只要用户回答了就继续

      if (shouldContinue) {
        const windowKey = extractWindowKey(opts.agent)
        if (windowKey) {
          this.onAnswered(windowKey, {
            message: opts.autoContinue.message,
            answers
          })
        }
      }
    }

    return answers
  }
}

function extractWindowKey(agent: unknown): string | undefined {
  if (typeof agent !== 'object' || agent === null) return undefined
  const id = (agent as { id?: unknown }).id
  return typeof id === 'string' ? id : undefined
}
