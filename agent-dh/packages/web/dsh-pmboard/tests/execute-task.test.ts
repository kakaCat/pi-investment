/**
 * ExecuteTask 用例测试（REQ-4842fe t5）——对应 design/test-cases.md §3.3/3.4/3.5/3.6。
 *
 * 口径：子卡凭证三项任一不过 → 子卡不 done；存在未 done 子卡 → 父卡不得 done；
 * 改了页面插件源码但 client 产物未更新 → 凭证不过。
 */
import { describe, it, expect } from 'vitest'
import { executeSubtask, parseSubtaskOutput, isNonEmptyValue, buildSubtaskPrompt } from '../src/application/use-cases/ExecuteTask.js'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { checkSubtaskEvidence } from '../src/application/internal/subtask-evidence.js'
import { STAGE_EVIDENCE_KIND, STAGE_KINDS } from '../src/domain/task/SubtaskTemplate.js'
import type { WorkflowRunner, WorkflowRunOutcome } from '../src/application/ports.js'
import { makeHarness, task, req } from './application/harness.js'

const SRC = 'packages/pages/dsh-pmboard/src/domain/task/TaskStatus.ts'
const CLIENT = 'packages/pages/dsh-pmboard/lib/client.js'

class FakeRunner implements WorkflowRunner {
  calls: unknown[] = []
  constructor(private readonly outcome: WorkflowRunOutcome) {}
  async start(input: unknown): Promise<WorkflowRunOutcome> {
    this.calls.push(input)
    return this.outcome
  }
}

const okRun = (payload: unknown): WorkflowRunOutcome => ({ ok: true, value: { ok: true, output: payload } })

function seed() {
  const h = makeHarness()
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing' })]
  h.seedTasks('REQ-000001', [
    task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', claimedAt: h.clock.t, title: '父卡' }),
    task({ id: 't-s', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'dev' as never, title: '研发', acceptance: '改动落盘并跑通测试' }),
  ])
  return h
}

const exec = { agent: { id: 'session-w-001' } }

describe('子卡闭环（3.4 凭证三项）', () => {
  it('全通过：run completed + 产出含 filesChanged + 文件 mtime≥开工 → 子卡 done', async () => {
    const h = seed()
    h.docs.put(SRC, 'x')
    h.docs.put(CLIENT, 'x')
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完状态机'], evidence: ['vitest 绿'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(true)
    const t = (await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!
    expect(t.status).toBe('done')
    expect(t.lastRun?.ok).toBe(true)
    expect(t.lastRun?.stopReason).toBe('completed')
    expect(t.lastReport?.filesChanged).toEqual([SRC])
    expect(t.executions[0]?.outcome).toBe('succeeded')
  })

  it('③ run 未完成（stopReason=error）→ 子卡不 done', async () => {
    const h = seed()
    h.docs.put(SRC, 'x')
    h.deps.workflow = new FakeRunner({ ok: false, reason: 'error: child failed' })
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!.status).not.toBe('done')
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!.lastRun?.ok).toBe(false)
  })

  it('② 文件证据不过（mtime 早于链出身）→ 子卡不 done', async () => {
    const h = seed()
    // L1 基准单调化后「开工」= 链出身（createdAt 最小值）。harness 默认 createdAt=1 会让
    // 任何文件都"新鲜"，故此例显式钉住链出身，保持原断言（早于基准的交付仍被拒）非空转。
    const birth = h.clock.t - 5_000
    h.repo.ledger.requirements[0]!.createdAt = birth
    await h.setTaskFields('t-p', { createdAt: birth })
    await h.setTaskFields('t-s', { createdAt: birth })
    h.docs.put(SRC, 'x', birth - 5_000)
    h.docs.put(CLIENT, 'x')
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_SUBTASK_GATE')
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!.status).not.toBe('done')
  })

  it('D17 回归：交付落在父卡窗口内、却早于子卡本次 run 起点 → 子卡仍可 done', async () => {
    const h = seed()
    // 父卡（链）窗口起点 = clock.t - 5000；交付文件落在窗口内（clock.t - 1000），
    // 但早于子卡本次 run 起点（startedAt = clock.t）。
    // 旧口径 since=子卡 claimedAt(=clock.t) → 判「mtime 早于开工」恒不过门（D17 实测）。
    // 新口径 since=父卡 claimedAt(=clock.t-5000) → 交付在链窗口内，过门。
    await h.setTaskFields('t-p', { claimedAt: h.clock.t - 5_000 })
    h.docs.put(SRC, 'x', h.clock.t - 1_000)
    h.docs.put(CLIENT, 'x') // pages 源改动需配套构建产物（构建新鲜度分支）
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(true)
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!.status).toBe('done')
  })

  it('① 汇报无改动文件（子代理只回文本）→ 子卡不 done（不猜文件）', async () => {
    const h = seed()
    h.deps.workflow = new FakeRunner(okRun('我做完了，功能正常'))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_SUBTASK_GATE')
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!.status).not.toBe('done')
  })

  it('3.6 页面插件构建新鲜度：改了 src 但 client.js 陈旧 → 凭证不过', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    h.docs.put(CLIENT, 'x', h.clock.t - 10_000)
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_SUBTASK_GATE')
  })

  it('3.3 引擎缺失 → 子卡显式失败（不静默成功）', async () => {
    const h = seed()
    h.docs.put(SRC, 'x')
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.reason).toContain('engine_unavailable')
  })

  it('幂等：已 done 的子卡重入直接返回 ok（不重复执行）', async () => {
    const h = seed()
    await h.setTaskFields('t-s', { status: 'done' })
    const runner = new FakeRunner(okRun('{}'))
    h.deps.workflow = runner
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(true)
    expect(runner.calls).toHaveLength(0)
  })
})

describe('父卡收尾门（3.5 / INV-5）', () => {
  it('存在未 done 子卡 → 父卡 done 被拒（REQBOARD_SUBTASK_GATE）', async () => {
    const h = seed()
    h.docs.put('src/x.ts', 'x')
    await h.setTaskFields('t-p', { lastReport: { at: h.clock.t, reportIndex: 1, filesChanged: ['src/x.ts'], completed: ['父卡完成'] } })
    let code: string | undefined
    try {
      await executeMoveTask(h.deps, { task_id: 't-p', to: 'done' }, exec)
    } catch (err) { code = (err as { code?: string }).code }
    expect(code).toBe('REQBOARD_SUBTASK_GATE')
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-p')!.status).not.toBe('done')
  })

  it('全部子卡 done → 父卡可通过（四重校验照旧）', async () => {
    const h = seed()
    h.docs.put('src/x.ts', 'x')
    const p = (await h.tasksOf('REQ-000001')).find(x => x.id === 't-p')!
    expect(p.status).toBe('in_progress') // 前置锚：确实读到了父卡（否则下面的写是空转）
    await h.setTaskFields('t-p', { lastReport: { at: h.clock.t, reportIndex: 1, filesChanged: ['src/x.ts'], completed: ['父卡完成'] } })
    await h.setTaskFields('t-s', { status: 'done' })
    const r = await executeMoveTask(h.deps, { task_id: 't-p', to: 'done' }, exec) as { to?: string }
    expect(r.to).toBe('done')
  })
})

describe('产出解析与空值判定（防"看起来在工作"）', () => {
  it('JSON 对象直接读；文本尝试 parse；否则整段作为一条完成项且 filesChanged 为空', () => {
    expect(parseSubtaskOutput(JSON.stringify({ filesChanged: ['a.ts'], completed: ['x'] })).filesChanged).toEqual(['a.ts'])
    expect(parseSubtaskOutput('not json').filesChanged).toEqual([])
    expect(parseSubtaskOutput('not json').completed).toHaveLength(1)
    expect(parseSubtaskOutput({ filesChanged: ['b.ts'] }).filesChanged).toEqual(['b.ts'])
  })

  it('isNonEmptyValue：null/空串/空对象/空数组都算空', () => {
    expect(isNonEmptyValue(null)).toBe(false)
    expect(isNonEmptyValue('')).toBe(false)
    expect(isNonEmptyValue({})).toBe(false)
    expect(isNonEmptyValue([])).toBe(false)
    expect(isNonEmptyValue({ ok: true })).toBe(true)
  })
})

/**
 * D17 凭证门修复（L1 基准单调化 + L2 证据形态分流）。
 *
 * 病根：①链窗口基准取父卡 claimedAt——ExecuteTask 每次重跑都重写它，基准随重跑向后漂移，
 * 同一份交付前后判成不同结论；②凭证门只认「有 filesChanged 且文件新鲜」，而 review/test/verify
 * 天然不产 diff → 结论族子卡 100% 死在凭证门、链必停。
 */
describe('D17 修复：L1 基准单调化（链出身） + L2 证据形态分流', () => {
  /** 把「链出身」拉早到 birth，并把会漂移的 claimedAt 全部推到 run 起点（模拟重跑）。 */
  async function pinChainBirth(h: ReturnType<typeof seed>, birth: number): Promise<void> {
    h.repo.ledger.requirements[0]!.createdAt = birth
    // 任务字段改动一律走真实写路径（v9：任务在队列，台账无 tasks）
    // claimedAt = 漂移源：重跑把它推到本次 run 起点
    await h.setTaskFields('t-p', { createdAt: birth, claimedAt: h.clock.t })
    await h.setTaskFields('t-s', { createdAt: birth })
  }

  it('L1：文件早于子卡本次 run 起点、但 ≥ 链出身 → 子卡 done', async () => {
    const h = seed()
    const birth = h.clock.t - 8_000
    await pinChainBirth(h, birth)
    // 交付落在链窗口内（birth + 1000），但早于子卡本次 run 起点（clock.t）。
    // 旧口径 since=父卡 claimedAt(=clock.t) 必拒；新口径 since=链出身(=birth) 应放行。
    h.docs.put(SRC, 'x', birth + 1_000)
    h.docs.put(CLIENT, 'x', h.clock.t)
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(true)
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!.status).toBe('done')
  })

  it('L1 反例：文件早于链出身 → 仍拒（窗口有界，不是无脑放行）', async () => {
    const h = seed()
    const birth = h.clock.t - 8_000
    await pinChainBirth(h, birth)
    h.docs.put(SRC, 'x', birth - 1_000)
    h.docs.put(CLIENT, 'x', h.clock.t)
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({ filesChanged: [SRC], completed: ['改完'] })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_SUBTASK_GATE')
    expect((await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!.status).not.toBe('done')
  })

  it('L2 结论族：review filesChanged=[] 且 completed 非空 → 子卡 done（天然无 diff）', async () => {
    const h = seed()
    await h.setTaskFields('t-s', { stageKind: 'review' })
    h.deps.workflow = new FakeRunner(okRun(JSON.stringify({
      completed: ['逐条复核完毕：设计与实现无偏离'],
      evidence: ['无 diff（本轮只做判断）'],
    })))
    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })
    expect(r.ok).toBe(true)
    const t = (await h.tasksOf('REQ-000001')).find(x => x.id === 't-s')!
    expect(t.status).toBe('done')
    expect(t.lastReport?.filesChanged).toEqual([])
    expect(t.lastReport?.completed.length).toBeGreaterThan(0)
  })

  it('L2 结论族但无结论：review filesChanged=[] 且 completed=[] → 拒', () => {
    const verdict = checkSubtaskEvidence({
      hasReport: true,
      reportFilesChanged: [],
      reportCompleted: [],
      run: { ok: true, stopReason: 'completed', valueNonEmpty: true },
      since: 1,
      stageKind: 'review',
      fileMtimes: {},
      pagesSrcFiles: [],
      clientBuildExists: false,
      clientBuildMtime: 0,
      newestPagesSrcMtime: 0,
    })
    expect(verdict.ok).toBe(false)
    if (!verdict.ok) {
      expect(verdict.code).toBe('REQBOARD_SUBTASK_GATE')
      expect(verdict.reason).toContain('缺少完工汇报')
    }
  })

  it('L2 写入族边界：dev filesChanged=[] 即便有结论也拒（没落盘=没干活）', () => {
    const verdict = checkSubtaskEvidence({
      hasReport: true,
      reportFilesChanged: [],
      reportCompleted: ['我改完了，功能正常'],
      run: { ok: true, stopReason: 'completed', valueNonEmpty: true },
      since: 1,
      stageKind: 'dev',
      fileMtimes: {},
      pagesSrcFiles: [],
      clientBuildExists: false,
      clientBuildMtime: 0,
      newestPagesSrcMtime: 0,
    })
    expect(verdict.ok).toBe(false)
    if (!verdict.ok) expect(verdict.code).toBe('REQBOARD_SUBTASK_GATE')
  })

  it('STAGE_EVIDENCE_KIND 与 STAGE_KINDS 全量对齐（新增阶段漏登记即缺口）', () => {
    expect(Object.keys(STAGE_EVIDENCE_KIND).sort()).toEqual([...STAGE_KINDS].sort())
    for (const k of STAGE_KINDS) expect(['file', 'verdict']).toContain(STAGE_EVIDENCE_KIND[k])
    // 结论族口径（D17 收口）：这些阶段天然无 diff
    for (const k of ['review', 'test', 'regress', 'verify', 'analyze', 'probe', 'collect', 'dryrun'] as const) {
      expect(STAGE_EVIDENCE_KIND[k]).toBe('verdict')
    }
  })

  // REQ-260927144541-0481 根因修复：凭证门的证据形态必须**提前写进工作要求**——
  // 否则 integrate（写入族）Worker 只交联调结论、被门退回，同一张卡重跑仍复现。
  it('buildSubtaskPrompt 如实转述本阶段凭证形态（写入族要产出 / 结论族要判断）', () => {
    const parent = task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', title: '父卡' })
    const writeStage = task({ id: 't-s1', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'integrate' as never, title: '联调', acceptance: '联调通过' })
    const verdictStage = task({ id: 't-s2', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'review' as never, title: '复核', acceptance: '逐条结论' })
    const writePrompt = buildSubtaskPrompt(parent, writeStage, '联调')
    const verdictPrompt = buildSubtaskPrompt(parent, verdictStage, '复核')
    expect(writePrompt).toContain('写入族')
    expect(writePrompt).toContain('REQBOARD_SUBTASK_GATE')
    expect(verdictPrompt).toContain('结论族')
    expect(verdictPrompt).not.toContain('写入族')
  })
})
