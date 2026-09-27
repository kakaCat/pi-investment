/**
 * FR-11 路线 A：executeSubtask 的**团队分支**用例（executeSubtaskTeam）。
 *
 * 口径：团队服务可用且 caller 是 live agent → 派给 Worker；Worker 经 reqboard_task_report 写台账，
 * 链把产出读回来合成 workflow 同款形状 → 下游（解析/落账/凭证门）逐字复用。
 * 服务不可用 → 仍走 workflow 兼容路径（既有 execute-task 18 例覆盖，这里只断言"没被团队抢走"）。
 */
import { describe, it, expect } from 'vitest'
import { executeSubtask } from '../src/application/use-cases/ExecuteTask.js'
import type { AgentTeamsPort, SpawnWorkerInput, TeamMemberViewLike, TeamTaskCreateInput, TeamTaskUpdateInput, TeamTaskViewLike, WorkflowRunner, WorkflowRunOutcome } from '../src/application/ports.js'
import { makeHarness, task, req, type Harness } from './application/harness.js'

const SRC = 'packages/pages/dsh-pmboard/src/domain/task/TaskStatus.ts'
/** pages 源改动会触发构建新鲜度分支 → 必须同时放构建产物。 */
const CLIENT = 'packages/pages/dsh-pmboard/lib/client.js'

function member(name: string, status: TeamMemberViewLike['status']): TeamMemberViewLike {
  return { id: 'sess-' + name, name, role: 'teammate', status, diagnostics: [] }
}
function view(id: string, status: TeamTaskViewLike['status']): TeamTaskViewLike {
  return { id, revision: 1, subject: 's', description: 'd', status, blockedBy: [], writeScopes: [], ready: true, writeScopeWarnings: [] }
}

/** 假团队：createTask 记下；waitForChange 里让"Worker"写台账并把任务推 completed。 */
class FakeTeams implements AgentTeamsPort {
  created: TeamTaskCreateInput[] = []
  spawns: SpawnWorkerInput[] = []
  members: TeamMemberViewLike[] = []
  availableFlag = true
  failCreate = false
  private status: TeamTaskViewLike['status'] = 'pending'
  private seq = 0
  constructor(private readonly h: Harness, private readonly work?: (h: Harness) => void | Promise<void>) {}
  available(): boolean { return this.availableFlag }
  async spawnWorker(_c: unknown, i: SpawnWorkerInput): Promise<TeamMemberViewLike> {
    this.spawns.push(i)
    const m = member(i.name, 'running')
    this.members.push(m)
    return m
  }
  listMembers(): readonly TeamMemberViewLike[] { return this.members }
  async createTask(_c: unknown, i: TeamTaskCreateInput): Promise<TeamTaskViewLike> {
    if (this.failCreate) throw Object.assign(new Error('teams boom'), { code: 'DSH_TEAMS_UNAVAILABLE' })
    this.created.push(i)
    this.seq += 1
    return view('tt-' + this.seq, 'pending')
  }
  listTasks(): readonly TeamTaskViewLike[] { return [] }
  getTask(_c: unknown, id: string): TeamTaskViewLike { return view(id, this.status) }
  async updateTask(_c: unknown, i: TeamTaskUpdateInput): Promise<TeamTaskViewLike> {
    this.updates.push({ taskId: i.taskId, action: i.action, expectedRevision: i.expectedRevision })
    if (i.action === 'reopen') this.status = 'pending'
    return view(i.taskId, i.action === 'reopen' ? 'pending' : 'completed')
  }
  async waitForChange(): Promise<{ timedOut: boolean }> {
    await this.work?.(this.h)
    this.status = 'completed'
    return { timedOut: false }
  }
  sent: { target: string; content: string }[] = []
  async sendMessage(_c: unknown, i: { target: string; content: string }): Promise<{ messageId: string; status: string }> {
    this.sent.push(i)
    return { messageId: 'msg-1', status: 'accepted' }
  }
  interrupt(): { previousStatus: string } { return { previousStatus: 'running' } }
  updates: { taskId: string; action: string; expectedRevision: number }[] = []
}

/** 记调用次数的 workflow 假引擎：团队分支下必须**一次都不被调**。 */
class CountingRunner implements WorkflowRunner {
  calls = 0
  async start(_i: unknown): Promise<WorkflowRunOutcome> { this.calls += 1; return { ok: false, reason: 'should_not_be_called' } }
}

function seed(): Harness {
  const h = makeHarness()
  h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing' })]
  h.seedTasks('REQ-000001', [
    task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', title: '父卡' }),
    task({ id: 't-s', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'dev' as never, title: '研发', acceptance: '改动落盘并跑通测试' }),
  ])
  return h
}
const exec = { agent: { id: 'session-w-001' } }

/**
 * Worker 的"写产出"动作（链读不到团队收件箱，队列是唯一结果通道）。
 * v9：任务不在台账 → 改走真实 `TaskStore` 写路径（`setTaskFields`），故本 helper 变 async。
 */
async function workerWritesReport(h: Harness): Promise<void> {
  await h.setTaskFields('t-s', { lastReport: { at: h.clock.t, reportIndex: 1, filesChanged: [SRC], completed: ['改完'] } })
}

describe('团队分支：executeSubtask 走 Agent Teams', () => {
  it('团队可用 + live agent → 派 Worker → 读回台账产出 → 子卡 done，且 workflow 一次未被调', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    h.docs.put(CLIENT, 'x', h.clock.t)
    const runner = new CountingRunner()
    h.deps.workflow = runner
    const teams = new FakeTeams(h, workerWritesReport)
    h.deps.teams = teams

    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001', exec })

    expect(r.ok).toBe(true)
    const t = (await h.tasksOf('REQ-000001')).find((x) => x.id === 't-s')!
    expect(t.status).toBe('done')
    expect(t.teamTaskId).toBe('tt-1')                 // team task ↔ 子卡 的持久映射
    expect(runner.calls).toBe(0)                      // 团队优先，workflow 不被触碰
    expect(teams.spawns).toHaveLength(1)              // 起了一次 Worker
    expect(teams.spawns[0]!.name).toBe('reqboard-t-p')// 名字 = 幂等键
    expect(teams.created).toHaveLength(1)
    expect(teams.created[0]!.description).toContain('t-s')          // 必须带台账子卡 id，否则 Worker 写不回来
    expect(teams.created[0]!.description.startsWith('[reqboard:parent=t-p]')).toBe(true)  // 一个父卡 = 一个团队
    expect(teams.spawns[0]!.prompt).toContain('[reqboard:parent=t-p]')                    // Worker 只认本队
  })

  it('父卡 = 一个团队：派第 N 张卡时一次性建全队任务并串 blockedBy（原生 DAG，DSH 自动算 ready）', async () => {
    const h = makeHarness()
    h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing' })]
    h.seedTasks('REQ-000001', [
      task({ id: 't-p', requirementId: 'REQ-000001', status: 'in_progress', title: '父卡' }),
      task({ id: 't-1', requirementId: 'REQ-000001', status: 'done', parentId: 't-p', stageKind: 'dev' as never, title: '研发' }),
      task({ id: 't-2', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'review' as never, title: '复核' }),
      task({ id: 't-3', requirementId: 'REQ-000001', status: 'todo', parentId: 't-p', stageKind: 'test' as never, title: '测试' }),
    ])
    h.docs.put(SRC, 'x', h.clock.t)
    h.docs.put(CLIENT, 'x', h.clock.t)
    const teams = new FakeTeams(h, async (hh) => {
      await hh.setTaskFields('t-2', { lastReport: { at: hh.clock.t, reportIndex: 1, filesChanged: [], completed: ['复核完毕：无偏离'] } })
    })
    h.deps.teams = teams

    const r = await executeSubtask(h.deps, { subtaskId: 't-2', windowKey: 'session-w-001', exec })

    expect(r.ok).toBe(true)
    // 只建未收口的 2 张（t-1 已 done → 不重放回板上），链序 = [review, test]
    expect(teams.created.map((c) => c.subject)).toEqual(['[review] 复核', '[test] 测试'])
    expect(teams.created[0]!.blockedBy).toBeUndefined()      // 队首无前置
    expect(teams.created[1]!.blockedBy).toEqual(['tt-1'])    // test blockedBy review → 原生 DAG
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-2')!.teamTaskId).toBe('tt-1')
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-3')!.teamTaskId).toBe('tt-2')
    // review 属结论族：无 diff 但有结论 → L2 放行（与 D17 修复咬合）
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-2')!.status).toBe('done')
  })

  it('团队服务 available()=false → 不抢活，走 workflow 兼容路径', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    const runner = new CountingRunner()
    h.deps.workflow = runner
    const teams = new FakeTeams(h, workerWritesReport)
    teams.availableFlag = false
    h.deps.teams = teams

    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001' })

    expect(runner.calls).toBe(1)                      // 交给 workflow
    expect(r.ok).toBe(false)                          // 假引擎返回 should_not_be_called
    expect(teams.created).toHaveLength(0)
  })

  it('无 caller（system 驱动）→ 不抢活，走 workflow 兼容路径', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    const runner = new CountingRunner()
    h.deps.workflow = runner
    h.deps.teams = new FakeTeams(h, workerWritesReport)

    await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'system' })   // 无 exec.agent

    expect(runner.calls).toBe(1)
  })

  it('Worker 没写台账 → team_report_missing（不得合成"格式合法的空产出"，否则结论族假通过）', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    h.docs.put(CLIENT, 'x', h.clock.t)
    // Worker 把任务 complete 了，但**没有**调 reqboard_task_report（无 work 回调）
    const teams = new FakeTeams(h)
    h.deps.teams = teams

    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001', exec })

    expect(r.ok).toBe(false)
    expect(r.reason).toContain('team_report_missing')
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-s')!.status).not.toBe('done')
  })

  it('台账报告早于本次派发（历史报告）→ team_report_stale（不让早前交付侥幸通过）', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    h.docs.put(CLIENT, 'x', h.clock.t)
    // 预置一份"早前直接执行"留下的历史报告（t-c42bc0 真实事故的同款）
    await h.setTaskFields('t-s', { lastReport: {
      at: h.clock.t - 10_000, reportIndex: 1, filesChanged: [SRC], completed: ['早前交付'],
    } })
    const teams = new FakeTeams(h)   // 本次 Worker 没再写
    h.deps.teams = teams

    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001', exec })

    expect(r.ok).toBe(false)
    expect(r.reason).toContain('team_report_stale')
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-s')!.status).not.toBe('done')
  })

  it('凭证门拒绝 → 团队任务被 reopen（堵住"completed 空转"死循环）', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    h.docs.put(CLIENT, 'x', h.clock.t)
    // Worker 对 dev（写入族）报了空 filesChanged → L2 判"没落盘" → 门拒
    const teams = new FakeTeams(h, async (hh) => {
      await hh.setTaskFields('t-s', { lastReport: { at: hh.clock.t, reportIndex: 1, filesChanged: [], completed: ['我做完了'] } })
    })
    h.deps.teams = teams

    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001', exec })

    expect(r.ok).toBe(false)
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-s')!.status).not.toBe('done')
    expect(teams.updates.map((u) => u.action)).toContain('reopen')   // ← 不放回板上就死循环
  })

  it('团队建任务抛错 → 子卡不 done（失败要响亮，不静默成功）', async () => {
    const h = seed()
    h.docs.put(SRC, 'x', h.clock.t)
    const teams = new FakeTeams(h, workerWritesReport)
    teams.failCreate = true
    h.deps.teams = teams

    const r = await executeSubtask(h.deps, { subtaskId: 't-s', windowKey: 'session-w-001', exec })

    expect(r.ok).toBe(false)
    expect(r.reason).toContain('DSH_TEAMS_UNAVAILABLE')
    expect((await h.tasksOf('REQ-000001')).find((x) => x.id === 't-s')!.status).not.toBe('done')
  })
})
