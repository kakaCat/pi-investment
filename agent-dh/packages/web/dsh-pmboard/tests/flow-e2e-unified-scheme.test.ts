/**
 * 端到端流程验证（REQ-260928185112-e20d 统一方案）——**造数据 + mock 引擎**，一次投递跑完整条链。
 *
 * 为什么要有这篇：前面的用例是**分片**验证（阶段解析/脚本契约/提示词/泳道/重试各自单测），
 * 但"从队列领任务 → 逐步跑完 → 父卡收尾 → rollup 进验收"这条**整链**从未端到端跑过。
 * 本文件用真实 QueueTaskStore + 真实 AdvanceChain + mock 的 workflow 引擎与 jobs 端口，
 * 把下面六件事在同一次运行里一起钉住：
 *   ① 步骤计划按卡性质生成（implement/frontend 保守 4 段；doc 卡 2 段）；
 *   ② 每一步的脚本带 \`phase(步名)\`（进度事件）且 schema 按证据族分流；
 *   ③ 子卡提示词带【本步边界】（验收切片：dev 段不得跑父卡终态验收命令）；
 *   ④ run 的取消权来自**后台 job**（不是派发它的 turn）；
 *   ⑤ 证据门 → 父卡收尾 → 需求 rollup 进 accepting，全程无人工介入；
 *   ⑥ 瞬断一次能自动重试并跑完（无需人工续跑）。
 */
import { describe, it, expect } from 'vitest'
import { advanceRequirement } from '../src/application/use-cases/AdvanceChain.js'
import { STAGE_EVIDENCE_KIND } from '../src/domain/task/SubtaskTemplate.js'
import { makeHarness, task, req } from './application/harness.js'
import type {
  JobsPort,
  JobStartSpec,
  WorkflowRunOutcome,
  WorkflowRunner,
  WorkflowStartInput,
} from '../src/application/ports.js'
import type { TaskRecord } from '../src/shared/protocol.js'

/** 写入族证据要求的真实落盘文件（凭证门会 stat 它）。 */
const FILE = 'src/domain/x.ts'

/** mock 引擎：按 args.stageKind 的**证据族**回不同产出；可选"首次瞬断"。 */
class MockEngine implements WorkflowRunner {
  readonly runs: Array<{ stageKind: string; script: string; signal?: AbortSignal; parent?: unknown }> = []
  constructor(private readonly abortFirst = false) {}
  private calls = 0
  async start(input: WorkflowStartInput): Promise<WorkflowRunOutcome> {
    this.calls += 1
    const kind = String((input.args as { stageKind?: string } | undefined)?.stageKind ?? '')
    this.runs.push({ stageKind: kind, script: input.script, signal: input.signal, parent: input.parent })
    if (this.abortFirst && this.calls === 1) {
      return { ok: false, reason: 'cancelled: workflow run cancelled: workflow signal aborted' }
    }
    const output = STAGE_EVIDENCE_KIND[kind as never] === 'verdict'
      ? { verdict: 'pass', summary: kind + ' 通过', evidence: ['mock 命令 exit 0'] }
      : { filesChanged: [FILE], summary: kind + ' 完成', evidence: ['mock 测试绿'] }
    return { ok: true, value: { ok: true, output: JSON.stringify(output) } }
  }
}

/** jobs 桩：同步 await 执行（走**投递路径**，以便验证 runSignal 来自 job 而非 turn）。 */
class SyncJobs implements JobsPort {
  jobSignal?: AbortSignal
  async start(spec: JobStartSpec): Promise<string> {
    const controller = new AbortController()
    this.jobSignal = controller.signal
    await spec.run(controller.signal)
    return 'job-e2e-1'
  }
  async get(): Promise<null> { return null }
  available(): boolean { return true }
}

function seedFlow() {
  const h = makeHarness()
  h.docs.put(FILE, 'x')
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: true })]
  h.seedTasks('REQ-000001', [
    // 父卡一：代码实现卡（frontend，未声明接口面 → 保守保留联调段，需计划显式声明才删）
    task({ id: 't-impl', requirementId: 'REQ-000001', status: 'todo', title: '实现卡', phase: 'implement' as never, side: 'frontend' as never }),
    // 父卡二：纯文档卡（side=doc → 只落 dev+review）
    task({ id: 't-doc', requirementId: 'REQ-000001', status: 'todo', title: '文档卡', phase: 'implement' as never, side: 'doc' as never, dependsOn: ['t-impl'] }),
  ])
  const engine = new MockEngine()
  const jobs = new SyncJobs()
  h.deps.workflow = engine
  h.deps.jobs = jobs
  return { h, engine, jobs }
}

const tasksRaw = (h: ReturnType<typeof seedFlow>['h']): readonly TaskRecord[] => {
  const raw = h.queueRepo.rawOf('REQ-000001')
  return raw === undefined ? [] : (JSON.parse(raw) as { tasks: TaskRecord[] }).tasks
}

describe('E2E：从队列领任务跑完整条链（统一新方案）', () => {
  it('步骤计划按卡性质 → 逐步跑完 → 父卡收尾 → 需求进验收；脚本/提示词/取消权全部符合新口径', async () => {
    const { h, engine, jobs } = seedFlow()
    const execAgent = { id: 'session-w-001' }
    const turnSignal = AbortSignal.abort('turn 已结束') // 故意先掐：不应影响 chain 内的子卡 run

    const out = await advanceRequirement(h.deps, 'REQ-000001', { agent: execAgent, signal: turnSignal })

    const tasks = tasksRaw(h)
    const subsOf = (pid: string) => tasks.filter(t => t.parentId === pid)

    // ① 步骤计划按卡性质生成
    expect(subsOf('t-impl').map(s => s.stageKind)).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(subsOf('t-doc').map(s => s.stageKind)).toEqual(['dev', 'review'])

    // ⑤ 逐步跑完 + 父卡收尾 + rollup（无人工介入、无 RETRY）
    expect(subsOf('t-impl').every(s => s.status === 'done')).toBe(true)
    expect(subsOf('t-doc').every(s => s.status === 'done')).toBe(true)
    expect(tasks.find(t => t.id === 't-impl')!.status).toBe('done')
    expect(tasks.find(t => t.id === 't-doc')!.status).toBe('done')
    // 投递路径的返回体只给回执（steps/stopped 恒空），链的真实结局看状态与 advance.history
    expect(out.dispatched).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('accepting')
    const hist = h.repo.ledger.requirements[0]!.advance?.history ?? []
    expect(hist.some(r => r.event === 'RETRY')).toBe(false)
    expect(hist.filter(r => r.event === 'RUN_SUBTASK' && r.outcome === 'ok').length).toBe(6)

    // ② 脚本：phase(步名) 是进度事件；schema 按证据族分流
    const devRun = engine.runs.find(r => r.stageKind === 'dev')!
    expect(devRun.script).toContain('phase("研发")')
    expect(devRun.script).toContain('"filesChanged"')
    const reviewRun = engine.runs.find(r => r.stageKind === 'review')!
    expect(reviewRun.script).toContain('phase("复核")')
    expect(reviewRun.script).toContain('"verdict"')
    expect(reviewRun.script).not.toContain('"filesChanged"')

    // ③ 提示词带本步边界（验收切片）
    expect(devRun.script).toContain('【本步边界】')
    expect(devRun.script).toContain('不要')

    // ④ 取消权来自 job（turn 已 abort，但子卡 run 收到的不是它）
    expect(jobs.jobSignal).toBeDefined()
    expect(engine.runs.length).toBeGreaterThan(0)
    expect(engine.runs.every(r => r.signal === jobs.jobSignal)).toBe(true)
    expect(engine.runs.every(r => r.signal !== turnSignal)).toBe(true)

    // 子代理归属仍是调用者 agent（design/architecture §3 parent: exec.agent）
    expect(engine.runs.every(r => r.parent === execAgent)).toBe(true)
  })

  it('首次瞬断（abort 族）→ 自动重试一次后跑完整条链，无需人工续跑', async () => {
    const h = makeHarness()
    h.docs.put(FILE, 'x')
    h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: true })]
    h.seedTasks('REQ-000001', [task({ id: 't-impl', requirementId: 'REQ-000001', status: 'todo', title: '实现卡' })])
    const engine = new MockEngine(true) // 首次瞬断
    const jobs = new SyncJobs()
    h.deps.workflow = engine
    h.deps.jobs = jobs

    const out = await advanceRequirement(h.deps, 'REQ-000001', { agent: { id: 'session-w-001' } })

    expect(out.dispatched).toBe(true)
    const hist = h.repo.ledger.requirements[0]!.advance?.history ?? []
    expect(hist.some(r => r.event === 'RETRY')).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('accepting')
    expect(h.repo.ledger.requirements[0]!.autoRun).toBe(true)
    expect(tasksRaw(h).filter(t => t.parentId === 't-impl').every(s => s.status === 'done')).toBe(true)
  })
})
