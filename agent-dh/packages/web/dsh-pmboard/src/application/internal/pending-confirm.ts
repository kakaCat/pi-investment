/**
 * 弹框非阻塞投递（REQ-260924213231-b1c4 T-6 · serves: FR-3）——宽限赛跑 / 挂起登记 / 后台落章与唤醒。
 *
 * 为什么单独一个模块：AskConfirm 用例只保留「校验 → 投递 → 同步作答或登记挂起」的编排；
 * 计时器与后台续跑是**副作用机制**，与「响应体形状」无关。抽出来之后 AskConfirm 的每个
 * `return` 都是响应字面量——output-contract 的静态扫描因此能逐键对账（少一个键=绑定层拒收）。
 *
 * 语义（design/architecture.md L102）：
 * ```
 *   questions.ask ──赛跑──► 宽限内作答 = 同步落章（调用方直接拿 confirmed，旧语义逐字一致）
 *                     └──超宽限──► 登记 ticket + 立即返回 pending=true（**不判失败**）
 *                                 后台：作答到达 → settle（落章/推进）→ 回填回执 → 唤醒窗口
 * ```
 *
 * 后台失败纪律：调用方早已返回，**绝不上抛**（未捕获 rejection 会污染调用方回合）；
 * 失败时回填 confirmed=false，回执仍可读台账 confirmedAt 复核（以台账为准，不伪造）。
 *
 * @module dsh-pmboard/application/internal/pending-confirm
 */
import type { AskAnswer, UseCaseDeps } from '../ports.js'
import type { ArtifactKind, PendingConfirmationOutcome } from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'

/** 一次已投递的确认请求（同步作答与后台续跑共用同一形状）。 */
export interface ConfirmSubmitted {
  requirementId: string
  windowKey: string
  target: 'artifact' | 'plan'
  kind: string
  question: string
  /** 选项标签（首个 = 肯定项；判定肯定/否定与改造前同源） */
  optionLabels: readonly string[]
  advance: boolean
}

/** 赛跑结果：作答 / 弹框抛错 / 超宽限（三分支都有明确去向，不留悬空 promise）。 */
export type AskRace =
  | { kind: 'answered'; answers: readonly AskAnswer[] }
  | { kind: 'rejected'; err: unknown }
  | { kind: 'timeout' }

/**
 * `questions.ask` 与宽限计时器赛跑：谁先到算谁。
 *
 * 计时器 unref：等人不应把进程/测试收尾吊住（超宽限后由后台续跑接管）。作答/抛错分支
 * 一律 clearTimeout，避免留下悬挂定时器（测试里表现为用例跑完进程不退出）。
 */
export function raceAsk(ask: Promise<readonly AskAnswer[]>, graceMs: number): Promise<AskRace> {
  return new Promise<AskRace>((resolve) => {
    const timer = setTimeout(() => resolve({ kind: 'timeout' }), graceMs)
    const handle = timer as unknown as { unref?: () => void }
    if (typeof handle.unref === 'function') handle.unref()
    ask.then(
      (answers) => { clearTimeout(timer); resolve({ kind: 'answered', answers }) },
      (err: unknown) => { clearTimeout(timer); resolve({ kind: 'rejected', err }) },
    )
  })
}

/** 后台续跑响应体里可回填进回执的字段（缺省项不写，保持 PendingConfirmationOutcome 契约不增键）。 */
type SettledBody = Record<string, unknown>

/** 响应体 → 回执 outcome（confirmed/advanced 取严格 true；用户选择/意见可选）。 */
function outcomeOf(body: SettledBody): PendingConfirmationOutcome {
  const userChoice = body.user_choice
  const userFeedback = body.user_feedback
  return {
    confirmed: body.confirmed === true,
    advanced: body.advanced === true,
    ...(typeof userChoice === 'string' ? { userChoice } : {}),
    ...(typeof userFeedback === 'string' ? { userFeedback } : {}),
  }
}

/**
 * 超宽限：登记挂起 ticket 并**立即返回**（success=true、confirmed=false、pending=true——
 * 不判失败），同时把「作答到达 → 落章/留痕 → 回填回执 → 唤醒窗口」挂到 ask 的后台续跑上。
 *
 * `settle` 由 AskConfirm 注入（同步/后台共用同一实现，见 internal/confirm-settle.ts）。
 */
export function suspendConfirm(
  deps: UseCaseDeps,
  ask: Promise<readonly AskAnswer[]>,
  s: ConfirmSubmitted,
  settle: (answers: readonly AskAnswer[]) => Promise<SettledBody>,
): unknown {
  const port = deps.pendingConfirms!
  const ticket = port.register({
    windowKey: s.windowKey,
    requirementId: s.requirementId,
    target: s.target,
    ...(s.target === 'artifact' ? { kind: s.kind as ArtifactKind } : {}),
  }).ticket

  void ask.then(
    (answers) => {
      void settle(answers)
        .then((body) => {
          port.settle(ticket, outcomeOf(body))
          wake(deps, s.windowKey, ticket, body)
        })
        .catch(() => { port.settle(ticket, { confirmed: false, advanced: false }) })
    },
    () => { port.settle(ticket, { confirmed: false, advanced: false }) },
  )

  return {
    success: true,
    confirmed: false,
    advanced: false,
    pending: true,
    ticket,
    requirement_id: s.requirementId,
    note: '弹框已投递，超宽限仍未作答：已登记挂起确认（不判失败）。人作答后会后台自动落章/推进；'
      + '请稍后调 reqboard_confirm_receipt(ticket="' + ticket + '") 取回执，或调 reqboard_status 读确认态',
  }
}

/** 唤醒窗口（AgentDeliveryPort）：告知作答已落地与取回执的唯一命令；投递失败不阻断后台落章。 */
function wake(deps: UseCaseDeps, windowKey: string, ticket: string, body: SettledBody): void {
  const text = body.confirmed === true
    ? fmt('用户已在确认弹框作答（ticket {t}）：已落章{adv}。请调 reqboard_confirm_receipt(ticket="{t}") 取回执', {
        t: ticket,
        adv: body.advanced === true ? '并推进' : '（未推进）',
      })
    : fmt('用户已在确认弹框作答（ticket {t}）：未确认，节点未推进。按用户意见处理后可重新发起确认', { t: ticket })
  deps.delivery?.deliver(windowKey, { text })
}
