/**
 * Dive 模式服务（REQ-260926215013-1568 T-5 · serves: FR-5, FR-6, FR-9）。
 *
 * 职责收窄为**订阅持有者 + 端口提供者**：
 *   · 持有全部宿主订阅——session/event 与 agent/status（由组合根经 attach* 装配）、
 *     agent/pre-step、agent/inbox/*、agent/error、agent/disposed、reqboard/requirement-moved；
 *   · 后七个委托给 round 半（round-driver），本服务不自己判定续跑；
 *   · 暴露 roundDriver() 供 session-driver 在 idle 拍定序，暴露 teardown() 供组合根收尾。
 *
 * 为什么不再由状态事件直投：旧实现挂 requirement-moved 即投递，会打断正在跑的回合；现改为
 * **只置检查标志并请求一次驱动**，起轮时点由 round 半在整 agent 空闲时判定（对齐 Goal driver）。
 *
 * @module dsh-pmboard/application/dive/ReqboardDiveManager
 */
import { Context, Service } from '@deepseek-ai/cordis'
import type { DiveRoundDriver, DiveRoundPorts } from './round-driver.js'
import { createDiveRoundDriver } from './round-driver.js'
import { wireDiveRoundSubscriptions } from './round-subscriptions.js'

export default class ReqboardDiveManager extends Service {
  static inject = ['agents', 'reqboard']

  private readonly round: DiveRoundDriver
  private readonly unsubscribeRound: () => void

  constructor(ctx: Context, ports: DiveRoundPorts) {
    super(ctx, 'dive-manager')
    const logger = this.ctx.logger('dive-manager')
    this.round = createDiveRoundDriver(ports)
    this.unsubscribeRound = wireDiveRoundSubscriptions(this.ctx as never, this.round, {
      debug: (m) => logger.debug(m),
      warn: (m, e) => logger.warn(m, e),
    })
    logger.info('Dive 服务已装配：session/event + agent/status 两路 + 回合事件七路（pre-step/inbox/error/disposed/requirement-moved）')
  }

  /**
   * 订阅会话事件（session/event）——**Dive 是该订阅的持有者**（采集/簿记路）。
   *
   * 用户裁定（2026-09-26）：CaptureHook 废弃，会话驱动能力归 Dive。driver 只提供处理函数，
   * 订阅生命周期由本服务负责（谁拥有会话事件在调用方看得见，不藏在装配函数里）。
   * 宿主不提供 ctx.on → 返回 undefined（调用方按"订阅未成立"留痕）。
   */
  attachSessionDriver(handler: (session: unknown, event: unknown) => void): (() => void) | undefined {
    const ctx = this.ctx as unknown as {
      on?: (event: string, listener: (session: unknown, event: unknown) => void) => (() => void) | void
    }
    return ctx.on?.('session/event', handler) ?? undefined
  }

  /**
   * 订阅 agent 状态（agent/status）——**Dive 是该驱动点的持有者**。
   *
   * 对齐 `@deepseek-ai/dsh-goal-round-driver`（用户裁定 2026-09-26）：Goal 的 round driver 把
   * `agent/status === 'idle'`（整 agent 空闲）当唯一驱动点，session/event 只做簿记；
   * 本服务同款持有该订阅，driver 只提供处理函数。宿主不提供 ctx.on → 返回 undefined。
   */
  attachAgentStatus(
    handler: (agent: unknown, status: unknown) => void,
  ): (() => void) | undefined {
    const ctx = this.ctx as unknown as {
      on?: (
        event: string,
        listener: (payload: { agent?: unknown; status?: unknown }) => void,
      ) => (() => void) | void
    }
    return ctx.on?.('agent/status', (payload) => handler(payload?.agent, payload?.status)) ?? undefined
  }

  /** round 半句柄：session-driver 在 idle 拍定序用；组合根登记 teardown 用。 */
  roundDriver(): DiveRoundDriver { return this.round }

  /** 卸载/停用：先解绑回合事件，再 fail-closed 收尾（关准入 → 解除武装 → 取消在飞 → 等静默）。 */
  async teardown(): Promise<void> {
    try { this.unsubscribeRound() } catch { /* 解绑失败不抛 */ }
    await this.round.teardown()
  }
}
