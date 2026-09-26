/**
 * Dive 回合驱动器（REQ-260926215013-1568 T-2 · serves: FR-1 … FR-11）。
 * 照 dsh-goal-round-driver 自实现：一 agent 一状态机；五条纪律 + reservation→admission + 上限终态；零框架依赖。
 * @module dsh-pmboard/application/dive/round-driver
 */
import type { ReqboardRepository, DiveRoundDeliveryPort } from '../ports.js'
import type { RequirementRecord } from '../../shared/protocol.js'
import { isDiveRoundSource } from '../../shared/protocol.js'
import {
  isDrivableRequirement, roundLimitFor, roundReservationValid, sameQueued, sameRound,
  agentIdOf, agentStatusOf, inboxOf, messageIdOf, sourceOf, contentOf,
  type DriverState, type RoundAttempt,
} from './round-state.js'

export interface DiveRoundLogger {
  info(message: string): void
  debug(message: string): void
  warn(message: string, err?: unknown): void
}

/** 外部依赖全部经端口注入（实现在组合根/adapters）。 */
export interface DiveRoundPorts {
  repo: ReqboardRepository
  agents: { get(id: string): unknown | undefined; withoutInitiator<T>(operation: () => T): T }
  /** 驱动所在插件 fiber 是否 active（对齐 Goal 的 ctx.fiber.state === 2）。 */
  fiberActive(): boolean
  delivery: DiveRoundDeliveryPort
  cancel(agent: unknown, cause: 'parent'): void
  whenIdle(agent: unknown): Promise<void>
  /** 耐久检查点：兑现台账写队列排空（= repo.read(() => undefined)）。 */
  checkpoint(): Promise<void>
  renderRoundText(input: { requirementId: string; round: number; status: string }): string
  now(): number
  logger: DiveRoundLogger
}

export type PreStepDecision =
  | { kind: 'reject' }
  | { kind: 'enter'; messages: unknown[]; startsRequestSeries?: true }

export interface DiveRoundDriver {
  onIdle(agent: unknown, captureTick: () => void): void
  onPreStep(agent: unknown, messages: unknown[], signal: { aborted: boolean }, next: () => Promise<PreStepDecision>): Promise<PreStepDecision>
  onInboxInserted(agent: unknown, message: unknown): void
  onInboxClaimed(agent: unknown, message: unknown): void
  onInboxDiscarded(agent: unknown, message: unknown): void
  onAgentError(agent: unknown): void
  onAgentDisposed(agent: unknown): void
  onRequirementMoved(requirementId: string): void
  onSessionEvent(session: unknown, event: unknown): void
  requestDrive(agent: unknown): void
  teardown(): Promise<void>
  whenQuiet(): Promise<void>
}

export function createDiveRoundDriver(ports: DiveRoundPorts): DiveRoundDriver {
  const log = ports.logger
  const states = new Map<unknown, DriverState>()
  const writes = new Set<Promise<unknown>>()
  /** teardown 后全局关闭准入（状态表会被清空，故不能只靠 per-state stopping）。 */
  let stopped = false

  function stateFor(agent: unknown): DriverState {
    const existing = states.get(agent)
    if (existing !== undefined) return existing
    const state: DriverState = {
      agent, attempt: undefined, competingQueued: false,
      needsCheckpoint: false, requested: false, run: undefined, stopping: false,
    }
    states.set(agent, state)
    return state
  }
  function track<T>(p: Promise<T>): Promise<T> {
    writes.add(p)
    const done = (): void => { writes.delete(p) }
    p.then(done, done)
    return p
  }
  function requirementById(id: string): RequirementRecord | undefined {
    return ports.repo.snapshot().requirements.find(r => r.id === id)
  }
  function requirementFor(state: DriverState): RequirementRecord | undefined {
    if (state.attempt !== undefined) return requirementById(state.attempt.requirementId)
    const id = agentIdOf(state.agent)
    return id === undefined ? undefined : ports.repo.snapshot().requirements.find(r => r.sourceSessionId === id)
  }
  function agentLive(state: DriverState): boolean {
    const id = agentIdOf(state.agent)
    return id !== undefined && ports.agents.get(id) === state.agent
  }
  function readyToDrive(state: DriverState): boolean {
    return ports.fiberActive() && !state.stopping && agentLive(state)
      && agentStatusOf(state.agent) === 'idle' && !state.competingQueued
  }

  /** 解除武装（保留 phase）；写失败只告警。 */
  function disarm(state: DriverState, reason: string): void {
    let req: RequirementRecord | undefined
    try { req = requirementFor(state) } catch (err) { log.warn('dive: disarm 查需求失败（不冒泡）——' + reason, err); return }
    if (req === undefined) { log.warn('dive: disarm 跳过（无绑定需求）——' + reason); return }
    const id = req.id
    const p = ports.repo.mutate('dive-disarm', (ledger) => {
      const r = ledger.requirements.find(x => x.id === id)
      if (r === undefined || r.dive === undefined || r.dive.activation !== 'armed') return undefined
      r.dive.activation = 'disarmed'
      r.dive.lastActiveAt = ports.now()
      r.version += 1
      r.updatedAt = ports.now()
      return { requirements: [r] }
    })
    p.catch(err => log.warn('dive: 解除武装写失败——' + reason, err))
    track(p)
  }

  /** 回合上限终态（FR-8）。 */
  function terminalBlock(req: RequirementRecord, limit: number): void {
    if (req.dive?.phase === 'paused') return
    const p = ports.repo.mutate('dive-terminal-block', (ledger) => {
      const r = ledger.requirements.find(x => x.id === req.id)
      if (r === undefined || r.dive === undefined || r.dive.phase === 'paused') return undefined
      r.dive.phase = 'paused'
      r.dive.pausedReason = 'round-limit'
      r.comments.push({
        id: 'c-dive-' + r.id + '-' + ports.now(),
        body: '[Dive 回合上限] 阶段 ' + r.status + ' 达上限 ' + limit + ' 回合（roundsInStage=' + (r.dive.roundsInStage ?? 0) + '）→ 终态暂停 paused/round-limit。人工 reqboard_clear_pause 可解锁。',
        createdAt: ports.now(), createdBy: { kind: 'system' },
      })
      r.version += 1
      r.updatedAt = ports.now()
      return { requirements: [r] }
    })
    p.catch(err => log.warn('dive: 终态阻塞写失败', err))
    track(p)
    log.warn('dive: 回合上限达终态（阶段=' + req.status + '，上限=' + limit + '，需求=' + req.id + '）')
  }

  /** 准入计数（FR-7）：消息真正进入 history 才 roundsInStage = round（恰好一次）。 */
  function persistAdmission(attempt: RoundAttempt): void {
    const p = ports.repo.mutate('dive-round-admitted', (ledger) => {
      const r = ledger.requirements.find(x => x.id === attempt.requirementId)
      if (r === undefined || r.dive === undefined) return undefined
      if ((r.dive.roundsInStage ?? 0) >= attempt.round) return undefined
      r.dive.roundsInStage = attempt.round
      r.dive.lastActiveAt = ports.now()
      r.version += 1
      r.updatedAt = ports.now()
      return { requirements: [r] }
    })
    p.catch(err => log.warn('dive: 准入计数写失败（需求=' + attempt.requirementId + '）', err))
    track(p)
  }

  /** 空闲时把已取消的预留落成终态暂停（FR-9 aborted 后半）。 */
  function pauseAborted(state: DriverState): void {
    const attempt = state.attempt
    if (attempt === undefined || !attempt.cancelled) return
    const req = requirementById(attempt.requirementId)
    state.attempt = undefined
    if (!isDrivableRequirement(req)) return
    const p = ports.repo.mutate('dive-aborted-pause', (ledger) => {
      const r = ledger.requirements.find(x => x.id === attempt.requirementId)
      if (r === undefined || r.dive === undefined || r.dive.phase === 'paused') return undefined
      r.dive.phase = 'paused'
      r.dive.pausedReason = 'aborted'
      r.comments.push({ id: 'c-dive-abort-' + ports.now(), body: '[Dive] 回合被中止（aborted）→ 终态暂停。', createdAt: ports.now(), createdBy: { kind: 'system' } })
      r.version += 1
      r.updatedAt = ports.now()
      return { requirements: [r] }
    })
    p.catch(err => log.warn('dive: aborted 终态写失败', err))
    track(p)
    log.warn('dive: 回合被中止 → 需求终态暂停（' + attempt.requirementId + '，pausedReason=aborted）')
  }

  /** 同批中非本回合的已认领消息按原顺序放回 next-step（幂等）。 */
  function restoreOtherClaimed(agent: unknown, messages: unknown[], messageId: string | undefined): void {
    const inbox = inboxOf(agent)
    if (inbox?.prepend === undefined) return
    for (const m of [...messages.filter(x => messageIdOf(x) !== messageId)].reverse()) {
      const id = messageIdOf(m)
      if (id === undefined) continue
      if ((inbox.nextStep ?? []).some(c => c.id === id) || (inbox.nextTurn ?? []).some(c => c.id === id)) continue
      inbox.prepend('next-step', m)
    }
  }

  async function drive(state: DriverState): Promise<void> {
    if (!readyToDrive(state)) return
    if (state.needsCheckpoint) {
      state.needsCheckpoint = false
      try { await ports.checkpoint() } catch (err) { log.warn('dive: 耐久检查点失败 → 解除武装', err); disarm(state, 'checkpoint-failed'); return }
      if (!readyToDrive(state) || state.needsCheckpoint) return
    }
    // 已有预留 → 不叠加执行：清预留、置检查点与请求，下一拍重来（对齐 Goal）。
    if (state.attempt !== undefined) { state.attempt = undefined; state.needsCheckpoint = true; state.requested = true; return }
    const id = agentIdOf(state.agent)
    if (id === undefined) return
    const bound = (): RequirementRecord | undefined =>
      ports.repo.snapshot().requirements.find(r => r.sourceSessionId === id)
    let req = bound()
    if (!isDrivableRequirement(req)) return
    const limit = roundLimitFor(req!.status)
    if ((req!.dive?.roundsInStage ?? 0) >= limit) { terminalBlock(req!, limit); return }
    // FR-3 排队点屏障：排队前必须先落盘；await 之后重查一切。
    try { await ports.checkpoint() } catch (err) { log.warn('dive: 排队点检查点失败 → 解除武装', err); disarm(state, 'checkpoint-failed'); return }
    if (!readyToDrive(state) || state.needsCheckpoint || state.attempt !== undefined) return
    req = bound()
    if (!isDrivableRequirement(req)) return
    const round = (req!.dive?.roundsInStage ?? 0) + 1
    const text = ports.renderRoundText({ requirementId: req!.id, round, status: req!.status })
    const built = ports.delivery.createRoundMessage({ requirementId: req!.id, revision: req!.version, round, text })
    state.attempt = {
      requirementId: req!.id, revision: req!.version, round, messageId: built.messageId,
      content: contentOf(built.message), phase: 'queued', cancelled: false, stale: false,
    }
    const res = ports.delivery.deliverMessage(id, built.message)
    if (res.delivered) { log.info('dive: 起轮 queued（需求=' + req!.id + '，第 ' + round + '/' + limit + ' 回合，窗口=' + id + '）'); return }
    state.attempt = undefined
    log.warn('dive: 回合投递失败 → 解除武装（需求=' + req!.id + '）：' + (res.reason ?? '未知原因'))
    disarm(state, 'queue-failed')
  }

  /** 合并触发 → 单 agent 串行链（FR-4）。 */
  function requestDrive(state: DriverState): void {
    if (stopped || state.stopping) return
    state.requested = true
    if (state.run !== undefined) return
    let run: Promise<void>
    try {
      run = ports.agents.withoutInitiator(async () => {
        while (state.requested && !state.stopping) {
          state.requested = false
          try { await drive(state) } catch (err) { log.warn('dive: 驱动体异常 → 解除武装', err); disarm(state, 'driver-failed') }
        }
      })
    } catch (err) { log.warn('dive: 无法启动驱动链 → 解除武装', err); disarm(state, 'driver-start-failed'); return }
    state.run = run
    const retire = (): void => { state.run = undefined; if (state.requested && !state.stopping) requestDrive(state) }
    run.then(retire, (err) => { log.warn('dive: 驱动链 reject → 解除武装', err); disarm(state, 'driver-rejected'); retire() })
  }

  function rejectReason(state: DriverState, source: { requirementId: string; revision: number; round: number }, req: RequirementRecord | undefined): string {
    const a = state.attempt
    if (a === undefined) return '无预留（attempt 缺失）'
    if (a.phase !== 'claimed') return '预留相位=' + a.phase + '（未认领）'
    if (a.stale) return '预留已 stale'
    if (a.cancelled) return '预留已取消'
    if (!sameRound(source as never, a)) return '来源与预留不符（req/revision/round）'
    if (req === undefined) return '需求不存在'
    if (req.version !== source.revision) return '需求 revision 已变（' + source.revision + ' → ' + req.version + '）'
    if (req.dive?.activation !== 'armed' || req.dive?.phase !== 'active') return '需求非 armed+active'
    if (source.round !== (req.dive.roundsInStage ?? 0) + 1) return '回合号不是 roundsInStage+1'
    return '内容与登记不一致'
  }

  return {
    onIdle(agent, captureTick) {
      const state = stateFor(agent)
      if (agentStatusOf(agent) === 'idle') state.competingQueued = false
      try { captureTick() } catch (err) { log.warn('dive: idle 采集跑批异常', err) }
      pauseAborted(state)
      requestDrive(state)
    },

    onInboxInserted(agent, message) {
      const inbox = inboxOf(agent)
      if (!(inbox?.nextTurn ?? []).some(c => c.id === messageIdOf(message))) return
      const state = stateFor(agent)
      if (state.attempt !== undefined && sameQueued(contentOf(message), sourceOf(message), state.attempt)) return
      state.competingQueued = true
      if (state.attempt?.phase === 'queued') state.attempt.stale = true
      log.debug('dive: 检测到竞争输入 → 让位到下次空闲')
    },
    onInboxClaimed(agent, message) {
      const state = states.get(agent)
      if (state?.attempt !== undefined && sameQueued(contentOf(message), sourceOf(message), state.attempt)) state.attempt.phase = 'claimed'
    },
    onInboxDiscarded(agent, message) {
      const state = states.get(agent)
      if (state?.attempt !== undefined && sameQueued(contentOf(message), sourceOf(message), state.attempt)) state.attempt.cancelled = true
    },

    onAgentError(agent) { disarm(stateFor(agent), 'agent-error') },
    onAgentDisposed(agent) { states.delete(agent) },

    onRequirementMoved(requirementId) {
      const id = requirementById(requirementId)?.sourceSessionId
      if (id === undefined) return
      const agent = ports.agents.get(id)
      if (agent === undefined) return
      const state = stateFor(agent)
      state.needsCheckpoint = true
      requestDrive(state)
    },

    onSessionEvent(session, event) {
      const sid = (session as { id?: unknown } | undefined)?.id
      if (typeof sid !== 'string') return
      const agent = ports.agents.get(sid)
      if (agent === undefined) return
      const state = stateFor(agent)
      const evt = (event ?? {}) as { type?: unknown; data?: unknown }
      const data = (evt.data ?? {}) as { id?: unknown; reason?: { kind?: unknown } }
      if (evt.type === 'user/message') {
        const attempt = state.attempt
        if (attempt !== undefined && data.id === attempt.messageId && attempt.phase !== 'admitted') {
          attempt.phase = 'admitted'
          persistAdmission(attempt)
          log.info('dive: 回合已准入 history（需求=' + attempt.requirementId + '，第 ' + attempt.round + ' 回合）')
        }
        return
      }
      if (evt.type !== 'turn/end') return
      const kind = data.reason?.kind
      if (kind === 'max-tokens') { log.warn('dive: 回合因 max-tokens 结束 → 解除武装'); disarm(state, 'max-tokens'); return }
      if (kind !== 'aborted') return
      if (state.attempt?.phase === 'claimed' || state.attempt?.phase === 'admitted') state.attempt.cancelled = true
      else disarm(state, 'aborted')
    },

    async onPreStep(agent, messages, signal, next) {
      const submitted = messages.find(m => isDiveRoundSource(sourceOf(m)))
      if (submitted === undefined) return next()
      const content = contentOf(submitted)
      const source = sourceOf(submitted) as { requirementId: string; revision: number; round: number }
      const state = stateFor(agent)
      const validate = (): boolean => roundReservationValid({
        state, content, source: source as never,
        req: requirementById(source.requirementId), fiberActive: ports.fiberActive(), agentLive: agentLive(state),
      })
      let valid = false
      try { valid = validate() } catch (err) { log.warn('dive: pre-step 校验抛错 → 解除武装', err); disarm(state, 'pre-step-error') }
      if (!valid) {
        log.warn('dive: pre-step 拒绝（前）：' + rejectReason(state, source, requirementById(source.requirementId)))
        if (state.attempt !== undefined && sameRound(source as never, state.attempt)) { state.attempt.stale = true; state.attempt = undefined }
        restoreOtherClaimed(agent, messages, messageIdOf(submitted))
        requestDrive(state)
        return { kind: 'reject' }
      }
      let decision: PreStepDecision
      try { decision = await next() } catch (err) {
        if (signal.aborted) throw err
        state.attempt = undefined
        requestDrive(state)
        throw err
      }
      if (signal.aborted) {
        if (decision.kind === 'enter') restoreOtherClaimed(agent, decision.messages, messageIdOf(submitted))
        return decision
      }
      if (decision.kind === 'reject') {
        log.warn('dive: pre-step 被下游拒绝（prompt-rejected）→ 解除武装')
        state.attempt = undefined
        disarm(state, 'prompt-rejected')
        return decision
      }
      let valid2 = false
      try { valid2 = validate() } catch (err) { log.warn('dive: post-decision 校验抛错 → 解除武装', err); disarm(state, 'pre-step-error') }
      if (!valid2) {
        log.warn('dive: pre-step 拒绝（后）：' + rejectReason(state, source, requirementById(source.requirementId)))
        state.attempt = undefined
        restoreOtherClaimed(agent, decision.messages, messageIdOf(submitted))
        requestDrive(state)
        return { kind: 'reject' }
      }
      return { ...decision, startsRequestSeries: true }
    },

    requestDrive(agent) { requestDrive(stateFor(agent)) },

    async teardown() {
      stopped = true
      const waits: Promise<unknown>[] = []
      let cancelled = 0
      for (const state of states.values()) {
        state.stopping = true
        disarm(state, 'teardown')
        if (state.attempt !== undefined) {
          state.attempt.stale = true
          if (agentStatusOf(state.agent) === 'running') { ports.cancel(state.agent, 'parent'); cancelled += 1; waits.push(ports.whenIdle(state.agent)) }
        }
        if (state.run !== undefined) waits.push(state.run)
      }
      log.info('dive: teardown —— ' + states.size + ' 个 agent 状态、' + cancelled + ' 个在飞回合被取消')
      states.clear()
      await Promise.allSettled([...waits, ...writes])
    },

    async whenQuiet() {
      for (let i = 0; i < 20; i += 1) {
        const waits: Promise<unknown>[] = [...writes]
        for (const s of states.values()) if (s.run !== undefined) waits.push(s.run)
        if (waits.length === 0) return
        await Promise.allSettled(waits)
        if (writes.size === 0 && [...states.values()].every(s => s.run === undefined)) return
      }
    },
  }
}
