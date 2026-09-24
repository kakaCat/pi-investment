// serves: FR-1
/**
 * 设计阶段交接端到端复跑（REQ-260924213231-b1c4 T-13 · serves: FR-1）——test-cases.md TC-19。
 *
 * 复跑 REQ-260924162957-2cd3 的**设计阶段死锁**场景：agent 只调工具、不打开看板——
 *   ① 落盘 5 份 design/*.md；
 *   ② reqboard_submit(kind=design) 登记（本次修复新增的 agent 可触发入口，FR-1）；
 *   ③ reqboard_ask_confirm(target=artifact, kind=design) 请人确认（kind=design 成组落章）；
 *   ④ reqboard_move(to=decomposing) 推进。
 * 一次通过，**全程不出现 REQBOARD_MISSING_ARTIFACT**（A1）。
 *
 * 兼容边界（同卡 acceptance）：legacy（artifacts 空/undefined）存量需求照旧放行。
 *
 * 本文件走**真实工具**（defineSubmitTool / defineAskConfirmTool / defineMoveTool）+ 真实适配器
 * （JsonLedgerRepository / FileDocRepository）落临时目录；断言可观察终态（登记条数 / 台账
 * confirmedAt / 需求状态），而不是「函数被调用过」。旧序回归（migration.test.ts /
 * consistency.test.ts 等）与本文件同批跑绿。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { SystemClock } from '../src/adapters/SystemClock.js'
import { RandomIdFactory } from '../src/adapters/RandomIdFactory.js'
import { SessionProbeAdapter } from '../src/adapters/SessionProbeAdapter.js'
import { UserQuestionsAdapter } from '../src/adapters/UserQuestionsAdapter.js'
import { defineSubmitTool, defineAskConfirmTool, defineMoveTool } from '../src/tools/index.js'
import type { UseCaseDeps } from '../src/application/ports.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-e2e-design-001'
const REQ = 'REQ-e2e001'
const REQUIREMENT_PATH = 'docs/requirements/' + REQ + '/requirement.md'
const DESIGN_DIR = 'docs/requirements/' + REQ + '/design'
/** feature 类型的五份必交设计文档（category-doc-sets.CATEGORY_DELTAS）。 */
const DESIGN5 = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
/** 弹框选项：首个 = 肯定项（与 ask_confirm 的判定同源）。 */
const AFFIRM = '确认，进入拆分'
const ASK_OPTIONS = [AFFIRM, '需要修改']
const EXEC = { agent: { id: W } }

let root: string
let store: JsonLedgerRepository

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'pmboard-e2e-design-'))
  store = new JsonLedgerRepository({ file: join(root, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

/** 需求根文档：feature 类型的必填节（边界 / 产品定义 / 用户与角色 / 功能点）齐全。 */
const REQ_MD = [
  '# 设计阶段交接 E2E',
  '',
  '## 边界',
  '',
  '只验证设计阶段交接，不做别的。',
  '',
  '## 产品定义',
  '',
  'E2E 测试夹具。',
  '',
  '## 用户与角色',
  '',
  '执行窗口 agent。',
  '',
  '## 功能点',
  '',
  '### FR-1 设计产物登记入口',
  '',
  'agent 可调 reqboard_submit(kind=design) 登记。',
  '',
].join('\n')

/** 单份设计文档：每个二级章节带 serves 标注，且不含任务表/拆分章节（不触发拆分内容门禁）。 */
function designDoc(name: string): string {
  const title = name.replace(/\.md$/, '')
  return [
    '# ' + title,
    '',
    '## 目标 <!-- serves: FR-1 -->',
    '',
    '本份设计只写方向与边界，不含任务表。',
    '',
    '## 约束 <!-- serves: FR-1 -->',
    '',
    '拆分内容归 decomposing 阶段。',
    '',
  ].join('\n')
}

function writeRequirementDoc(): void {
  mkdirSync(join(root, 'docs/requirements', REQ), { recursive: true })
  writeFileSync(join(root, REQUIREMENT_PATH), REQ_MD)
}

function writeDesign5(): void {
  mkdirSync(join(root, DESIGN_DIR), { recursive: true })
  for (const name of DESIGN5) writeFileSync(join(root, DESIGN_DIR, name), designDoc(name))
}

/** 假弹框通道：记录被问的弹框，按注入选项作答（证明走的是弹框路径，不是文字证据路径）。 */
function makeQuestions(selected: string[]): { svc: { ask: (req: unknown) => Promise<{ answers: { id: string; selected: string[] }[] }> }; asked: unknown[] } {
  const asked: unknown[] = []
  const svc = {
    ask: async (req: unknown): Promise<{ answers: { id: string; selected: string[] }[] }> => {
      asked.push(req)
      return { answers: [{ id: 'confirm', selected }] }
    },
  }
  return { svc, asked }
}

function makeTools(selected: string[] = [AFFIRM]) {
  const { svc, asked } = makeQuestions(selected)
  const deps: UseCaseDeps = {
    repo: store,
    docs: new FileDocRepository({ workspaceRoot: root }),
    clock: new SystemClock(),
    ids: new RandomIdFactory(),
    session: new SessionProbeAdapter({}),
    questions: new UserQuestionsAdapter(() => svc),
    doneThrottleMs: 0,
  }
  return {
    // 工具壳 execute 返回值按用例/kind 各不同，测试侧只按字段读（与既有工具测试同款）。
    submit: defineSubmitTool(deps) as any,
    ask: defineAskConfirmTool(deps) as any,
    move: defineMoveTool(deps) as any,
    asked,
  }
}

/** brainstorming 阶段已确认的需求文档产物——代表真实需求进 design 时的产物簿（非 legacy）。 */
function requirementArtifact(): StageArtifact {
  return {
    stage: 'brainstorming',
    kind: 'requirement',
    path: REQUIREMENT_PATH,
    registeredAt: 1,
    registeredBy: { kind: 'agent', sessionId: W },
    confirmedAt: 1,
    confirmedBy: { kind: 'human' },
  }
}

function reqRecord(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: REQ,
    title: '设计阶段交接 E2E',
    description: '',
    category: 'feature',
    status: 'design',
    blocked: false,
    sourceSessionId: W,
    comments: [],
    version: 1,
    createdAt: 1,
    updatedAt: 1,
    createdBy: { kind: 'human' },
    updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'design', at: 1, by: { kind: 'human' } }],
    artifacts: [requirementArtifact()],
    ...over,
  } as unknown as RequirementRecord
}

async function seed(over: Partial<RequirementRecord> = {}): Promise<void> {
  const r = reqRecord(over)
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const designArtifacts = (): StageArtifact[] =>
  (store.snapshot().requirements[0]!.artifacts ?? []).filter(a => a.kind === 'design')

describe('TC-19 E2E：设计阶段死锁复跑（登记 → 确认 → 推进，不打开看板）', () => {
  it('登记前 move 仍被产物存在门拦住：REQBOARD_MISSING_ARTIFACT（修的是入口，不是闸门）', async () => {
    await seed(); writeRequirementDoc(); writeDesign5()
    const t = makeTools()
    // 文档已落盘但产物簿没有 kind=design（事故现场）——旧闸门照旧拦
    await expect(t.move.execute({ to: 'decomposing' }, EXEC)).rejects.toThrow(/REQBOARD_MISSING_ARTIFACT/)
    expect(store.snapshot().requirements[0]!.status).toBe('design')
  })

  it('登记 ≠ 落章：submit 后未确认时 move 报 REQBOARD_ARTIFACT_NOT_CONFIRMED（两态文案分叉）', async () => {
    await seed(); writeRequirementDoc(); writeDesign5()
    const t = makeTools()
    const reg = await t.submit.execute({ kind: 'design' }, EXEC)
    expect(reg.registered_count).toBe(5)
    await expect(t.move.execute({ to: 'decomposing' }, EXEC)).rejects.toThrow(/REQBOARD_ARTIFACT_NOT_CONFIRMED/)
    expect(store.snapshot().requirements[0]!.status).toBe('design')
  })

  it('一次通过（A1）：submit(kind=design) → ask_confirm（默认自动推进）→ 需求直接进入 decomposing，全程无 REQBOARD_MISSING_ARTIFACT', async () => {
    await seed(); writeRequirementDoc(); writeDesign5()
    const t = makeTools()

    // ② 登记：agent 可触发的入口（FR-1）
    const reg = await t.submit.execute({ kind: 'design' }, EXEC)
    expect(reg.success).toBe(true)
    expect(reg.requirement_id).toBe(REQ)
    expect(reg.registered_count).toBe(5)
    expect(reg.design_docs).toHaveLength(5)
    for (const d of reg.design_docs) {
      expect(d.on_disk).toBe(true)
      expect(d.registered).toBe(true)
      expect(d.confirmed).toBe(false)
    }
    expect(designArtifacts()).toHaveLength(5)

    // ③ 弹框确认：肯定项 → 成组落章 + 自动推进
    const ask = await t.ask.execute(
      { target: 'artifact', kind: 'design', question: '设计文档已完成，是否确认进入拆分？', options: ASK_OPTIONS },
      EXEC,
    )
    expect(t.asked).toHaveLength(1) // 弹框路径确实被走到（非文字证据路径）
    expect(ask.success).toBe(true)
    expect(ask.confirmed).toBe(true)
    expect(ask.advanced).toBe(true)
    expect(ask.to).toBe('decomposing')

    // 终态：5 份全部落章 + 需求进入拆分
    const arts = designArtifacts()
    expect(arts).toHaveLength(5)
    for (const a of arts) expect(a.confirmedAt).toBeDefined()
    expect(store.snapshot().requirements[0]!.status).toBe('decomposing')
  })

  it('字面三步链（卡面顺序）：落盘 5 份 → submit(design) → ask_confirm(advance:false) → move(decomposing) 一次通过', async () => {
    await seed(); writeRequirementDoc(); writeDesign5()
    const t = makeTools()

    const reg = await t.submit.execute({ kind: 'design' }, EXEC)
    expect(reg.registered_count).toBe(5)

    // advance:false —— 本步只落章，推进留给显式 move，逐字复跑卡面三步
    const ask = await t.ask.execute(
      { target: 'artifact', kind: 'design', question: '设计文档已完成，是否确认进入拆分？', options: ASK_OPTIONS, advance: false },
      EXEC,
    )
    expect(ask.confirmed).toBe(true)
    expect(ask.advanced).toBe(false)
    expect(store.snapshot().requirements[0]!.status).toBe('design')
    for (const a of designArtifacts()) expect(a.confirmedAt).toBeDefined()

    const mv = await t.move.execute({ to: 'decomposing', reason: '设计文档已确认' }, EXEC)
    expect(mv.success).toBe(true)
    expect(mv.to).toBe('decomposing')
    expect(store.snapshot().requirements[0]!.status).toBe('decomposing')
  })

  it('迁移兼容：legacy（artifacts 空）存量需求 design→decomposing 仍放行，不要求登记/确认', async () => {
    await seed({ artifacts: undefined }); writeRequirementDoc(); writeDesign5()
    const t = makeTools()
    const mv = await t.move.execute({ to: 'decomposing', reason: '存量需求照旧放行' }, EXEC)
    expect(mv.success).toBe(true)
    expect(mv.to).toBe('decomposing')
    expect(store.snapshot().requirements[0]!.status).toBe('decomposing')
    // 放行不等于伪造：产物簿保持为空，闸门未凭空造产物
    expect(store.snapshot().requirements[0]!.artifacts ?? []).toHaveLength(0)
  })
})
