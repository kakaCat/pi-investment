/**
 * 弹框通道适配器（REQ-47939a t5 / ports.ts UserQuestionPort）——`deps.userQuestions` 接缝。
 *
 * reqboard_ask_confirm / accept_sheet 需要向用户弹框；服务可能未注入（子代理/无 UI/服务缺失）。
 * available() 给出可用性判定，ask() 在不可用时抛带 code 的错误（调用方据此返回 fallback=board）。
 *
 * @module dsh-pmboard/adapters/UserQuestionsAdapter
 */
import type { AskAnswer, AskQuestion, UserQuestionPort } from '../application/ports.js'

interface RawQuestionService {
  ask?: (req: unknown) => Promise<{ answers?: AskAnswer[] }>
}

export class UserQuestionsAdapter implements UserQuestionPort {
  private readonly resolve: () => unknown

  constructor(resolve: () => unknown) {
    this.resolve = resolve
  }

  available(): boolean {
    const svc = this.resolve() as RawQuestionService | undefined
    return typeof svc?.ask === 'function'
  }

  async ask(
    questions: readonly AskQuestion[],
    opts: { agent?: unknown; signal?: unknown },
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
    return result.answers ?? []
  }
}
