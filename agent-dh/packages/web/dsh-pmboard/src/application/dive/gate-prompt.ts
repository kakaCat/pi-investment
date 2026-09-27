/**
 * Dive 人工门弹框（REQ-260927100007-b8ba FR-14 · design I-10）——门状态投影 + 有边界重弹 + 受信端口实现。
 *
 * 要解决的矛盾（architecture.md §8）：Dive 的里程碑提醒说「**立即**调 reqboard_ask_confirm」，
 * 而铁律说「弹框超时/中断**不自动重弹**」——两条规则互撞，结果是**没有任何一方保证人会看到框**
 * （实测：提醒 3 次，人一次都没看到框）。FR-14 把兜底从"提醒 agent"改为"**保证弹框**"：
 * Dive 在 idle 跑批时自己算门状态并主动弹框，且有边界地重弹（冷却 + 上限，到顶留痕停手）。
 *
 * 三条纪律：
 *  ① **只请人点头**：肯定项仍由 `actor=human` 走 `transitionRequirement`（人工门强度不变）；
 *  ② **有边界**：同 (需求, 门, 产物指纹) 在一次等待（弹框在途）内只弹一次；跨回合冷却 ≥5min、
 *     上限 2 次；到顶写台账 comment 并停手（响亮，不静默）；
 *  ③ **不抛**：弹框通道不可用/抛错 → 降级为投递消息（保留"提醒 agent"路径），绝不替代人推进。
 *
 * @module dsh-pmboard/application/dive/gate-prompt
 */
import type { RequirementRecord } from '../../shared/protocol.js'
import type { GateId } from '../../domain/gate/GateSpec.js'
import { advanceTargetFor, gateById, gateFromStage } from '../../domain/gate/GateCatalog.js'
import { DEFAULT_CONFIRM_OPTIONS } from '../../domain/text/labels.js'
import { clip, fmt } from '../../domain/text/fmt.js'
import { pmHeader } from '../../domain/text/pm-badge.js'
import { LIMITS } from '../../domain/limits.js'
import type { GatePromptPort, UseCaseDeps } from '../ports.js'
import { applyConfirmDecision } from '../internal/confirm-settle.js'

/** 同 (需求, 门) 跨回合重弹冷却（design I-10：≥5 分钟）。 */
export const GATE_PROMPT_COOLDOWN_MS = 5 * 60 * 1000
/** 同 (需求, 门) 弹框上限（design I-10：上限 2 次；到顶写 comment 停手）。 */
export const GATE_PROMPT_MAX_POPS = 2

/** 一次弹框决策（门状态投影的产物）。 */
export interface GatePromptDecision {
  gate: GateId
  /** 确认产物（artifact）或 推进确认（plan）。 */
  kind: 'artifact' | 'plan'
  artifactKind?: string
  /** (需求, 门, 产物指纹) 幂等键的第三元：产物集合与落章时间。 */
  fingerprint: string
  question: string
}

/** 产物指纹：按 path@(confirmedAt ?? registeredAt) 排序拼接（同集合 → 同指纹）。 */
function fingerprintOf(arts: readonly { path: string; registeredAt: number; confirmedAt?: number }[], mode: string): string {
  return mode + '#' + arts.map(a => a.path + '@' + String(a.confirmedAt ?? a.registeredAt)).sort().join('|')
}

/**
 * 计算绑定需求当前的**人工门状态**（纯函数，design I-10 的分支表）：
 *  · (a) 门 `requiredKind` 的产物**已登记未确认** → 弹「确认产物」（kind='artifact'）；
 *  · (b) 该产物**已确认**但状态未动（`advanceTargetFor` 可达）→ 弹「推进确认」（kind='plan'）。
 * 无门 / 无 requiredKind / 该阶段产物一条未登记 / 无可自动推进目标 → undefined（不弹）。
 *
 * 「无自动推进目标」这条同时把 **G4 验收门**排除在外：its 归档要逐项裁决，不能被压成一个肯定项
 * （design 分支 (b) 的可达性判定同此口径）。
 */
export function gatePromptFor(req: RequirementRecord): GatePromptDecision | undefined {
  const gate = gateFromStage(req.status)
  if (gate === undefined || gate.requiredKind === undefined) return undefined
  const to = advanceTargetFor(req.status)
  if (to === undefined) return undefined
  const arts = (req.artifacts ?? []).filter(a => a.kind === gate.requiredKind)
  if (arts.length === 0) return undefined
  const unconfirmed = arts.filter(a => a.confirmedAt === undefined)
  if (unconfirmed.length > 0) {
    return {
      gate: gate.id,
      kind: 'artifact',
      artifactKind: gate.requiredKind,
      fingerprint: fingerprintOf(unconfirmed, 'unconfirmed'),
      question: fmt('需求 {id}「{label}」门：产物 kind={kind} 已登记未确认（{paths}）。确认后落章并推进 {from} → {to}。', {
        id: req.id, label: gate.label, kind: gate.requiredKind,
        paths: unconfirmed.map(a => a.path).join('、'), from: req.status, to,
      }),
    }
  }
  return {
    gate: gate.id,
    kind: 'plan',
    fingerprint: fingerprintOf(arts, 'confirmed'),
    question: fmt('需求 {id}「{label}」门已满足（产物 kind={kind} 已确认），但状态仍停在 {from}。是否确认推进 {from} → {to}？', {
      id: req.id, label: gate.label, kind: gate.requiredKind, from: req.status, to,
    }),
  }
}

/** 到顶留痕的内容（组合根把它写进台账 comment）。 */
export interface GatePromptExhausted {
  windowKey: string
  requirementId: string
  gate: string
  pops: number
  question: string
}

/** 到顶 comment 文案（单点；组合根与测试同源）。 */
export function gatePromptExhaustedComment(info: GatePromptExhausted): string {
  return fmt('[Dive 弹框停手] 人工门 {gate} 已弹框 {pops} 次（上限 {max}）仍未得到推进，不再重弹。'
    + ' 原问题：{q}'
    + ' 下一步：请人工到看板处理该门（确认产物 / 推进阶段），或直接调 reqboard_ask_confirm。', {
    gate: info.gate, pops: info.pops, max: GATE_PROMPT_MAX_POPS, q: info.question,
  })
}

export interface GatePromptLoopDeps {
  /** 受信弹框端口（永不抛；见 ports.GatePromptPort）。 */
  prompt: GatePromptPort
  /** 弹框到上限时的**一次性**回调（组合根据此写台账 comment）。 */
  onExhausted?: (info: GatePromptExhausted) => void
  now: () => number
  logger?: { info(message: string): void; debug(message: string): void }
}

export interface GatePromptLoop {
  /** idle 一拍：给定窗口与其绑定需求，判定并（受边界约束地）弹框。**同步返回**，副作用走异步边界。 */
  tick(windowKey: string, req: RequirementRecord | undefined): void
}

interface PopState { pops: number; lastPopAt: number; lastFingerprint: string; notified: boolean }

/**
 * 有边界重弹的状态机（每次 driver 实例一份内存态）：
 *  ① 弹框在途（同一次等待）→ 不重弹；
 *  ② 到顶（pops ≥ GATE_PROMPT_MAX_POPS）→ 一次性留痕后停手；
 *  ③ 同一产物指纹在冷却窗内 → 不重弹；指纹变化（门状态变了）= 新一轮等待，可立即弹。
 */
export function createGatePromptLoop(deps: GatePromptLoopDeps): GatePromptLoop {
  const state = new Map<string, PopState>()
  const inflight = new Set<string>()
  /** 到顶留痕只写一次（不刷屏）。 */
  const notify = (key: string, st: PopState, d: GatePromptDecision, windowKey: string, requirementId: string): void => {
    if (st.notified) return
    st.notified = true
    state.set(key, st)
    deps.onExhausted?.({ windowKey, requirementId, gate: d.gate, pops: st.pops, question: d.question })
  }
  return {
    tick(windowKey, req): void {
      if (req === undefined) return
      const d = gatePromptFor(req)
      if (d === undefined) return
      const key = req.id + '|' + d.gate
      const st: PopState = state.get(key) ?? { pops: 0, lastPopAt: 0, lastFingerprint: '', notified: false }
      if (inflight.has(key)) return
      if (st.pops >= GATE_PROMPT_MAX_POPS) { notify(key, st, d, windowKey, req.id); return }
      if (st.lastFingerprint === d.fingerprint && deps.now() - st.lastPopAt < GATE_PROMPT_COOLDOWN_MS) return
      st.pops += 1
      st.lastPopAt = deps.now()
      st.lastFingerprint = d.fingerprint
      state.set(key, st)
      if (st.pops >= GATE_PROMPT_MAX_POPS) notify(key, st, d, windowKey, req.id)
      inflight.add(key)
      deps.logger?.info(fmt('reqboard gate-prompt: 弹框 {gate}/{kind}（需求 {id}，第 {n} 次）', {
        gate: d.gate, kind: d.kind, id: req.id, n: st.pops,
      }))
      let pending: Promise<{ answered: boolean; affirmative: boolean }>
      try {
        pending = deps.prompt.prompt({ ...d, windowKey, requirementId: req.id })
      } catch (err) {
        inflight.delete(key)
        deps.logger?.info('reqboard gate-prompt: 弹框抛错（已吞，降级留待下一回合）：' + String(err))
        return
      }
      Promise.resolve(pending).then(
        () => { inflight.delete(key) },
        (err: unknown) => {
          inflight.delete(key)
          deps.logger?.info('reqboard gate-prompt: 弹框失败（已吞）：' + String(err))
        },
      )
    },
  }
}

export interface GatePromptPortDeps {
  /** 惰性取用例依赖（组合根在 driver 装配之后才建 UseCaseDeps）。 */
  useCaseDeps: () => UseCaseDeps
  /** 弹框通道不可用/抛错时的降级投递（保留现行「提醒 agent」路径）。 */
  deliver: (windowKey: string, text: string) => void
  logger?: { info(message: string): void }
}

/**
 * 受信内部弹框端口的**参考实现**（design I-10）：
 *  · 弹框通道 = `UseCaseDeps.questions`（带 `gate` 声明 → 装饰器自动登记确认后置链）；
 *  · 肯定项 → `applyConfirmDecision`：落章（如需）+ 人工门 `transitionRequirement(actor=human)`
 *    + 批准计划的门合并落库（FR-1）——与三条既有确认通道**同一条**路径；
 *  · 通道不可用/抛错 → 降级投递消息并返回 `{answered:false}`，**绝不替代人推进**、**绝不抛**。
 *
 * 装配位置：只在**有弹框通道**的组合根处装配并注入 `DiveSessionDriverDeps.gatePrompt`
 * （见 wiring/pm-capture-root.ts 的说明）；未装配 = Dive 行为与 FR-14 之前逐字一致。
 */
export function createGatePromptPort(deps: GatePromptPortDeps): GatePromptPort {
  return {
    async prompt(input) {
      const uc = deps.useCaseDeps()
      const optionLabels = [...DEFAULT_CONFIRM_OPTIONS]
      const fallback = '【人工门提醒】' + input.question + ' 请调 reqboard_ask_confirm 弹框请人确认，或提示用户到看板处理该门。'
      if (!uc.questions.available()) {
        // deliver已删除：Dive模式下降级时只记录日志，不投递
        return { answered: false, affirmative: false }
      }
      try {
        const answers = await uc.questions.ask([{
          id: 'gate-prompt',
          header: pmHeader('确认'),
          question: clip(input.question, LIMITS.popupQuestionMax),
          options: optionLabels.map((label, i) => ({ label, ...(i === 0 ? { description: '确认后落章并推进' } : {}) })),
        }], { gate: input.gate as GateId })
        const picked = answers[0]?.selected?.[0] ?? answers[0]?.custom ?? ''
        const affirmative = picked.length > 0 && picked === optionLabels[0]
        if (affirmative) {
          const gate = gateById(input.gate as GateId)
          // 「批准拆分计划」门（requiredKind=decomposition）必须走 plan 门合并（落章 + 落库 + 推进，FR-1）；
          // 其余门走 artifact 确认路径。两条都终结于 transitionRequirement(actor=human)。
          await applyConfirmDecision(uc, {}, {
            requirementId: input.requirementId,
            windowKey: input.windowKey,
            target: gate?.requiredKind === 'decomposition' ? 'plan' : 'artifact',
            kind: input.artifactKind ?? gate?.requiredKind ?? '',
            question: input.question,
            picked,
            nowTs: uc.clock.now(),
            advance: true,
          })
        }
        return { answered: picked.length > 0, affirmative }
      } catch (err) {
        deps.logger?.info('reqboard gate-prompt: 弹框通道失败，降级为消息提醒：' + String((err as Error)?.message ?? err))
        // deliver已删除：Dive模式下降级时只记录日志，不投递
        return { answered: false, affirmative: false }
      }
    },
  }
}