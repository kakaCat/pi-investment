/**
 * TC-15：Dive 在人工门主动弹框（有边界重弹）——REQ-260927100007-b8ba FR-14 / design I-10。
 *
 * 覆盖（test-cases.md TC-15 逐条）：
 *  ① 门已满足未推进 → Dive 经 `GatePromptPort` 弹「推进确认」（kind='plan'）；
 *  ② 人点肯定 → **同一条**人工门路径推进（`transitionRequirement(actor=human)`）+ 门后置链照常；
 *  ③ 同一次等待（弹框在途）只弹 1 次；
 *  ④ 跨回合：冷却（≥5min）内不弹、超冷却再弹 1 次、到顶（上限 2）写台账 comment 并停手；
 *  ⑤ `GatePromptPort` 未装配 → 行为与改动前逐字一致（零弹框/零投递/零留痕）；
 *  ⑥ 弹框通道不可用 → 降级投递提醒，**绝不替代人推进**。
 *
 * @module dsh-pmboard/tests/dive-gate-prompt
 */
import { describe, it, expect, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createDiveSessionDriver } from '../src/application/dive/session-driver.js'
import {
  createGatePromptPort,
  gatePromptFor,
  GATE_PROMPT_COOLDOWN_MS,
  GATE_PROMPT_MAX_POPS,
  type GatePromptExhausted,
} from '../src/application/dive/gate-prompt.js'
import { assembleDiveSessionDriver } from '../src/wiring/pm-capture-root.js'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'
import { DEFAULT_CONFIRM_OPTIONS } from '../src/domain/text/labels.js'
import { makeHarness, req as reqFixture, FixedClock, type Harness } from './application/harness.js'
import type { AskAnswer, AskQuestion, GatePromptPort, UserQuestionPort } from '../src/application/ports.js'
import type { StageArtifact } from '../src/shared/protocol.js'

const W = 'session-dive-gate-001'
const T0 = 1_700_000_000_000
const ARTIFACT_PATH = 'docs/requirements/REQ-gate01/requirement.md'

/** 记录弹框次数/门声明/题干的假弹框通道（工具层的 UserQuestionPort）。 */
class RecordingQuestions implements UserQuestionPort {
  prompts = 0
  gates: Array<string | undefined> = []
  questions: AskQuestion[] = []
  constructor(private readonly behavior: 'yes' | 'no' | 'empty' | 'unavailable') {}
  available(): boolean { return this.behavior !== 'unavailable' }
  async ask(questions: readonly AskQuestion[], opts: Parameters<UserQuestionPort['ask']>[1]): Promise<readonly AskAnswer[]> {
    this.prompts += 1
    this.gates.push(opts.gate)
    this.questions = [...questions]
    if (this.behavior === 'empty') return []
    return [{ id: 'gate-prompt', selected: [this.behavior === 'yes' ? DEFAULT_CONFIRM_OPTIONS[0] : '需要修改'] }]
  }
}

/** 当前阶段产物（已登记；confirmed=true 时已落章）。 */
function stageArtifact(confirmed: boolean): StageArtifact {
  return {
    stage: 'brainstorming',
    kind: 'requirement',
    path: ARTIFACT_PATH,
    registeredAt: T0,
    registeredBy: { kind: 'human' },
    ...(confirmed ? { confirmedAt: T0 - 1000, confirmedBy: { kind: 'human' }, confirmedVia: 'board' as const } : {}),
  }
}

const tmpDirs: string[] = []
function tmpDir(): string {
  const d = mkdtempSync(join(tmpdir(), 'pmboard-gate-prompt-'))
  tmpDirs.push(d)
  return d
}
afterEach(() => { while (tmpDirs.length > 0) rmSync(tmpDirs.pop()!, { recursive: true, force: true }) })

/** 内存用例依赖 + 文档根兜底到临时目录（RTM 写入绝不落进仓库，同 tests/helpers/tool-deps.ts 纪律）。 */
function makeUc(artifactConfirmed: boolean, behavior: RecordingQuestions['behavior']) {
  const h: Harness = makeHarness()
  h.clock.t = T0
  const questions = new RecordingQuestions(behavior)
  h.deps.questions = questions
  const root = tmpDir()
  ;(h.docs as unknown as { workspaceRoot: () => string }).workspaceRoot = () => root
  h.repo.ledger.requirements.push(reqFixture({
    id: 'REQ-gate01',
    status: 'brainstorming',
    sourceSessionId: W,
    artifacts: [stageArtifact(artifactConfirmed)],
  }))
  return { h, questions }
}

interface Scenario {
  h: Harness
  questions: RecordingQuestions
  deliveries: Array<{ windowKey: string; text: string }>
  exhausted: GatePromptExhausted[]
  idle: () => void
  flush: () => Promise<void>
  advanceClock: (ms: number) => void
  status: () => string
  comments: () => string[]
}

/** 驱动器级场景（TC-15 的主体：门状态判定 + 有边界重弹 + 肯定项落地）。 */
function scenario(opts: { artifactConfirmed: boolean; behavior: RecordingQuestions['behavior']; wirePort: boolean }): Scenario {
  const { h, questions } = makeUc(opts.artifactConfirmed, opts.behavior)
  const deliveries: Array<{ windowKey: string; text: string }> = []
  const exhausted: GatePromptExhausted[] = []
  // 受信端口 = 生产参考实现（createGatePromptPort）→ 肯定项走 applyConfirmDecision，
  // 即与三条既有确认通道**同一条** transitionRequirement(actor=human) 路径。
  const port: GatePromptPort | undefined = opts.wirePort
    ? createGatePromptPort({
        useCaseDeps: () => h.deps,
        deliver: (windowKey, text) => { deliveries.push({ windowKey, text }) },
        logger: { info: () => {} },
      })
    : undefined
  const driver = createDiveSessionDriver({
    snapshot: () => h.repo.ledger,
    // v9：driver 结算节点要读队列任务（DiveSessionDriverDeps.taskStore 为必填）
    taskStore: h.taskStore,
    pending: new Map(),
    now: () => h.clock.t,
    ...(port === undefined ? {} : { gatePrompt: port }),
    onGatePromptExhausted: (info) => { exhausted.push(info) },
    logger: { info: () => {}, debug: () => {} },
  })
  return {
    h, questions, deliveries, exhausted,
    idle: () => driver.onAgentStatus({ id: W, session: { id: W } }, 'idle'),
    flush: async () => { for (let i = 0; i < 5; i += 1) await new Promise((r) => setTimeout(r, 0)) },
    advanceClock: (ms) => { h.clock.t += ms },
    status: () => h.repo.snapshot().requirements[0]!.status,
    comments: () => h.repo.snapshot().requirements[0]!.comments.map((c) => c.body),
  }
}

// ────────────────────────────────────────────────────────────────────────────
// 门状态投影（纯函数；design I-10 的分支表）
// ────────────────────────────────────────────────────────────────────────────

describe('gatePromptFor：人工门状态投影（design I-10）', () => {
  it('(a) 门产物已登记未确认 → 弹「确认产物」（kind=artifact）', () => {
    const d = gatePromptFor(reqFixture({ status: 'brainstorming', artifacts: [stageArtifact(false)] }))
    expect(d).toBeDefined()
    expect(d!.gate).toBe('G1')
    expect(d!.kind).toBe('artifact')
    expect(d!.artifactKind).toBe('requirement')
    expect(d!.fingerprint).toContain('unconfirmed')
  })

  it('(b) 门产物已确认但状态未推进 → 弹「推进确认」（kind=plan）', () => {
    const d = gatePromptFor(reqFixture({ status: 'brainstorming', artifacts: [stageArtifact(true)] }))
    expect(d).toBeDefined()
    expect(d!.gate).toBe('G1')
    expect(d!.kind).toBe('plan')
    expect(d!.question).toMatch(/门已满足/)
  })

  it('产物指纹随落章状态变化（(a) ≠ (b)）→ 门状态变了是新一次等待', () => {
    const a = gatePromptFor(reqFixture({ status: 'brainstorming', artifacts: [stageArtifact(false)] }))!
    const b = gatePromptFor(reqFixture({ status: 'brainstorming', artifacts: [stageArtifact(true)] }))!
    expect(a.fingerprint).not.toBe(b.fingerprint)
  })

  it('产物未登记 / 该阶段无门（design 无 design 产物）/ G4 验收门（无可自动推进目标）→ 不弹', () => {
    expect(gatePromptFor(reqFixture({ status: 'brainstorming', artifacts: [] }))).toBeUndefined()
    expect(gatePromptFor(reqFixture({ status: 'design', artifacts: [] }))).toBeUndefined()
    expect(gatePromptFor(reqFixture({
      status: 'accepting',
      artifacts: [{ ...stageArtifact(false), stage: 'accepting', kind: 'verification' }],
    }))).toBeUndefined()
  })
})

// ────────────────────────────────────────────────────────────────────────────
// TC-15：Dive 在人工门主动弹框（有边界重弹）
// ────────────────────────────────────────────────────────────────────────────

describe('TC-15 Dive 在人工门主动弹框（有边界重弹）', () => {
  it('门已满足未推进 → 弹「推进确认」（kind=plan）；肯定 → 同一条人工门路径推进', async () => {
    const s = scenario({ artifactConfirmed: true, behavior: 'yes', wirePort: true })
    s.idle()
    expect(s.questions.prompts).toBe(1)
    expect(s.questions.gates).toEqual(['G1'])
    expect(s.questions.questions[0]!.question).toMatch(/门已满足/)
    // 同一次等待（弹框在途）→ 不重弹。
    s.idle()
    expect(s.questions.prompts).toBe(1)
    // 人点肯定 → 落章保留 + 人工门 transitionRequirement(actor=human) 推进。
    await s.flush()
    expect(s.status()).toBe('design')
    const history = s.h.repo.snapshot().requirements[0]!.statusHistory ?? []
    expect(history[history.length - 1]!.status).toBe('design')
    expect(history[history.length - 1]!.by.kind).toBe('human')
    // 推进后门换了一道（G2 无 design 产物）→ 不再弹（不刷屏）。
    s.advanceClock(GATE_PROMPT_COOLDOWN_MS * 3)
    s.idle()
    await s.flush()
    expect(s.questions.prompts).toBe(1)
  })

  it('同一次等待只弹 1 次；冷却内不弹、超冷却再弹 1 次到顶，之后留痕停手', async () => {
    const s = scenario({ artifactConfirmed: true, behavior: 'empty', wirePort: true })
    s.idle()
    await s.flush()
    expect(s.questions.prompts).toBe(1)
    // 跨回合但在冷却窗内（+1min）→ 不弹。
    s.advanceClock(60_000)
    s.idle()
    await s.flush()
    expect(s.questions.prompts).toBe(1)
    // 超冷却（再 +5min）→ 第 2 次；到顶（上限 2）→ 留痕一次。
    s.advanceClock(GATE_PROMPT_COOLDOWN_MS)
    s.idle()
    await s.flush()
    expect(s.questions.prompts).toBe(GATE_PROMPT_MAX_POPS)
    expect(s.exhausted).toHaveLength(1)
    expect(s.exhausted[0]!.pops).toBe(GATE_PROMPT_MAX_POPS)
    expect(s.exhausted[0]!.gate).toBe('G1')
    // 到顶后停手：再多的 idle 不再弹、不再重复留痕。
    s.advanceClock(GATE_PROMPT_COOLDOWN_MS * 3)
    s.idle()
    await s.flush()
    s.idle()
    await s.flush()
    expect(s.questions.prompts).toBe(GATE_PROMPT_MAX_POPS)
    expect(s.exhausted).toHaveLength(1)
  })

  it('未装配 GatePromptPort → 与改动前逐字一致（零弹框/零投递/零留痕/状态不变）', async () => {
    const s = scenario({ artifactConfirmed: true, behavior: 'yes', wirePort: false })
    s.idle()
    await s.flush()
    s.advanceClock(GATE_PROMPT_COOLDOWN_MS * 3)
    s.idle()
    await s.flush()
    expect(s.questions.prompts).toBe(0)
    expect(s.deliveries).toHaveLength(0)
    expect(s.exhausted).toHaveLength(0)
    expect(s.status()).toBe('brainstorming')
    expect(s.comments()).toHaveLength(0)
  })

  it('弹框通道不可用 → 降级为提醒消息，绝不替代人推进', async () => {
    const s = scenario({ artifactConfirmed: true, behavior: 'unavailable', wirePort: true })
    s.idle()
    await s.flush()
    expect(s.questions.prompts).toBe(0)
    expect(s.deliveries).toHaveLength(1)
    expect(s.deliveries[0]!.windowKey).toBe(W)
    expect(s.deliveries[0]!.text).toMatch(/人工门提醒/)
    expect(s.status()).toBe('brainstorming')
  })

  it('到顶 → 组合根写台账 comment 并停手（响亮不静默）', async () => {
    const dir = tmpDir()
    const store = new JsonLedgerRepository({ file: join(dir, 'dsh-reqboard.json') })
    const seed = reqFixture({
      id: 'REQ-gate02',
      status: 'brainstorming',
      sourceSessionId: W,
      artifacts: [stageArtifact(true)],
    })
    await store.mutate('seed', (l) => { l.requirements.push(seed); return { requirements: [seed] } })

    const clock = new FixedClock(T0)
    const h = makeHarness()
    ;(h.docs as unknown as { workspaceRoot: () => string }).workspaceRoot = () => dir
    let statusHandler: ((a: unknown, st: unknown) => void) | undefined
    let prompts = 0
    const fakePort: GatePromptPort = {
      prompt: async () => { prompts += 1; return { answered: false, affirmative: false } },
    }
    assembleDiveSessionDriver({
      store,
      runtime: {
        pendingCapture: new Map(),
        toolTrace: new Map(),
        recentUserMsgs: new Map(),
        deliverer: { deliver: () => ({ delivered: true }) },
      },
      now: () => clock.t,
      injectionLog: { record: () => {} },
      gateChain: { enqueue: () => {}, runPending: async () => ({ ran: false }) },
      onNodeSettled: () => {},
      useCaseDeps: () => h.deps,
      logger: { info: () => {}, debug: () => {}, warn: () => {} },
      plugin: 'test',
      attachSessionDriver: () => () => {},
      attachAgentStatus: (handler: (a: unknown, st: unknown) => void) => { statusHandler = handler; return () => {} },
      gatePrompt: fakePort,
    } as never)

    const idle = (): void => statusHandler!({ id: W, session: { id: W } }, 'idle')
    const flush = async (): Promise<void> => { for (let i = 0; i < 5; i += 1) await new Promise((r) => setTimeout(r, 0)) }

    idle(); await flush()
    clock.t += GATE_PROMPT_COOLDOWN_MS + 1000
    idle(); await flush()
    expect(prompts).toBe(GATE_PROMPT_MAX_POPS)
    await flush()
    const bodies = store.snapshot().requirements.find((r) => r.id === 'REQ-gate02')!.comments.map((c) => c.body)
    expect(bodies.some((b) => b.includes('Dive 弹框停手') && b.includes('G1'))).toBe(true)

    // 到顶后不再弹，也不重复写 comment。
    clock.t += GATE_PROMPT_COOLDOWN_MS * 3
    idle(); await flush()
    expect(prompts).toBe(GATE_PROMPT_MAX_POPS)
    const after = store.snapshot().requirements.find((r) => r.id === 'REQ-gate02')!.comments
      .filter((c) => c.body.includes('Dive 弹框停手'))
    expect(after).toHaveLength(1)
  })
})
