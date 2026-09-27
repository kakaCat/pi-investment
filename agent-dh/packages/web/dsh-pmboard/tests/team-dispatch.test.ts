/**
 * team-dispatch 单测（FR-11 路线 A）：幂等起 Worker + 事件驱动等任务完成。
 * 用假 port（纯内存）冻结入参，不搭真 I/O——沿用 advance-select / DoneEvidenceSpec 的同款纪律。
 */
import { describe, it, expect } from 'vitest'
import { teamWorkerName, teamTaskSubject, isAliveMember, ensureWorker, awaitTeamTask, parentMarker, belongsToParent, ownsTeamTask } from '../src/application/internal/team-dispatch.js'
import type { AgentTeamsPort, SpawnWorkerInput, TeamMemberViewLike, TeamTaskCreateInput, TeamTaskUpdateInput, TeamTaskViewLike } from '../src/application/ports.js'

function member(name: string, status: TeamMemberViewLike['status']): TeamMemberViewLike {
  return { id: 'sess-' + name, name, role: 'teammate', status, diagnostics: [] }
}
function taskLike(id: string, status: TeamTaskViewLike['status']): TeamTaskViewLike {
  return { id, revision: 1, subject: 's', description: 'd', status, blockedBy: [], writeScopes: [], ready: true, writeScopeWarnings: [] }
}

class FakeTeams implements AgentTeamsPort {
  members: TeamMemberViewLike[] = []
  spawns: SpawnWorkerInput[] = []
  taskStatus: TeamTaskViewLike['status'] = 'pending'
  waits = 0
  /** 每次 waitForChange 前把 taskStatus 推进一步（模拟 Worker 干活）。 */
  onWait?: (f: FakeTeams) => void
  available(): boolean { return true }
  async spawnWorker(_c: unknown, input: SpawnWorkerInput): Promise<TeamMemberViewLike> {
    this.spawns.push(input)
    const m = member(input.name, 'running')
    this.members.push(m)
    return m
  }
  listMembers(): readonly TeamMemberViewLike[] { return this.members }
  async createTask(_c: unknown, _i: TeamTaskCreateInput): Promise<TeamTaskViewLike> { return taskLike('tt-1', 'pending') }
  listTasks(): readonly TeamTaskViewLike[] { return [] }
  getTask(): TeamTaskViewLike { return taskLike('tt-1', this.taskStatus) }
  async updateTask(_c: unknown, _i: TeamTaskUpdateInput): Promise<TeamTaskViewLike> { return taskLike('tt-1', 'completed') }
  async waitForChange(): Promise<{ timedOut: boolean }> { this.waits += 1; this.onWait?.(this); return { timedOut: false } }
  interrupt(): { previousStatus: string } { return { previousStatus: 'running' } }
  sent: { target: string; content: string }[] = []
  async sendMessage(_c: unknown, i: { target: string; content: string }): Promise<{ messageId: string; status: string }> {
    this.sent.push(i)
    const m = this.members.find((x) => x.name === i.target)
    if (m !== undefined) m.status = 'running'
    return { messageId: 'msg-1', status: 'accepted' }
  }
}

const caller = { id: 'lead-agent' }

describe('命名与成员判活', () => {
  it('teamWorkerName 带父卡前缀；teamTaskSubject 带阶段', () => {
    expect(teamWorkerName('t-abc')).toBe('reqboard-t-abc')
    expect(teamTaskSubject('review', '复核')).toBe('[review] 复核')
    expect(teamTaskSubject(undefined, '卡')).toBe('[task] 卡')
    expect(teamTaskSubject('', '卡')).toBe('[task] 卡')
  })
  it('一个父卡 = 一个团队：标记界定本队边界', () => {
    expect(parentMarker('t-p1')).toBe('[reqboard:parent=t-p1]')
    expect(belongsToParent('[reqboard:parent=t-p1]  ...', 't-p1')).toBe(true)
    expect(belongsToParent('[reqboard:parent=t-p2]  ...', 't-p1')).toBe(false)
    expect(belongsToParent('随便写', 't-p1')).toBe(false)
  })
  it('isAliveMember：running/idle/provisioning 活着；inactive/failed 已死', () => {
    expect(isAliveMember(member('a', 'running'))).toBe(true)
    expect(isAliveMember(member('a', 'idle'))).toBe(true)
    expect(isAliveMember(member('a', 'provisioning'))).toBe(true)
    expect(isAliveMember(member('a', 'inactive'))).toBe(false)
    expect(isAliveMember(member('a', 'failed'))).toBe(false)
  })
})

describe('ensureWorker 幂等（状态即事实：重复事件不得堆 Worker）', () => {
  it('无成员 → spawn 一次，名字 = reqboard-<parentId>', async () => {
    const f = new FakeTeams()
    const m = await ensureWorker(f, caller, 't-p1', 'loop prompt')
    expect(m.name).toBe('reqboard-t-p1')
    expect(f.spawns).toHaveLength(1)
    expect(f.spawns[0]!.prompt).toBe('loop prompt')
  })
  it('已有同名且活着 → 不重起（spawns 仍为 1）', async () => {
    const f = new FakeTeams()
    f.members.push(member('reqboard-t-p1', 'running'))
    const m = await ensureWorker(f, caller, 't-p1', 'loop')
    expect(m.name).toBe('reqboard-t-p1')
    expect(f.spawns).toHaveLength(0)
  })
  it('同名但已停（inactive）→ **唤醒**，绝不重起（名字唯一不可复用）', async () => {
    const f = new FakeTeams()
    f.members.push(member('reqboard-t-p1', 'inactive'))
    const m = await ensureWorker(f, caller, 't-p1', 'loop')
    expect(m.name).toBe('reqboard-t-p1')
    expect(f.spawns).toHaveLength(0)                      // 关键：不 spawn（同名会被 TeamService 拒）
    expect(f.sent.map((s) => s.target)).toEqual(['reqboard-t-p1'])
    expect(f.members[0]!.status).toBe('running')          // 被唤醒
  })
})

describe('ownsTeamTask：团队 Worker 的台账写回授权（只取自 live TeamService）', () => {
  class BoardTeams extends FakeTeams {
    board: TeamTaskViewLike[] = []
    listTasks(): readonly TeamTaskViewLike[] { return this.board }
  }
  /** 名册里放一个 id=sess-8ae828f6 的成员；板上放一张 owner 可控的卡。 */
  function setup(owner: string | undefined): { f: BoardTeams; agent: unknown } {
    const f = new BoardTeams()
    f.members.push({ id: 'sess-8ae828f6', name: 'reqboard-t-p', role: 'teammate', status: 'running', diagnostics: [] })
    f.board = [{ ...taskLike('tt-9', 'completed'), ...(owner !== undefined ? { ownerName: owner } : {}) }]
    return { f, agent: { id: 'sess-8ae828f6' } }
  }
  it('认领人本人 → 放行', () => {
    const { f, agent } = setup('reqboard-t-p')
    expect(ownsTeamTask(f, agent, 'sess-8ae828f6', 'tt-9')).toBe(true)
  })
  it('卡被别的成员认领 → 拒（不给自己以外的卡背书）', () => {
    const { f, agent } = setup('reqboard-other')
    expect(ownsTeamTask(f, agent, 'sess-8ae828f6', 'tt-9')).toBe(false)
  })
  it('卡无 ownerName → 拒', () => {
    const { f, agent } = setup(undefined)
    expect(ownsTeamTask(f, agent, 'sess-8ae828f6', 'tt-9')).toBe(false)
  })
  it('无 teamTaskId（非团队卡）→ 拒', () => {
    const { f, agent } = setup('reqboard-t-p')
    expect(ownsTeamTask(f, agent, 'sess-8ae828f6', undefined)).toBe(false)
  })
  it('调用者不在名册（伪造会话码）→ 拒', () => {
    const { f, agent } = setup('reqboard-t-p')
    expect(ownsTeamTask(f, agent, 'sess-伪造', 'tt-9')).toBe(false)
  })
  it('服务抛错（未装配/非成员）→ 拒，不炸', () => {
    const f = new BoardTeams()
    f.listMembers = () => { throw new Error('not a team member') }
    expect(ownsTeamTask(f, { id: 'x' }, 'x', 'tt-9')).toBe(false)
  })
})

describe('awaitTeamTask 事件驱动等待', () => {
  it('已经是 completed → 立即返回，不等待', async () => {
    const f = new FakeTeams()
    f.taskStatus = 'completed'
    let t = 1000
    expect(await awaitTeamTask(f, caller, 'tt-1', { deadlineMs: 60_000, now: () => t })).toBe('completed')
    expect(f.waits).toBe(0)
  })
  it('pending → 一次 waitForChange 后 Worker 把任务推到 completed → 返回 completed', async () => {
    const f = new FakeTeams()
    f.onWait = (self) => { self.taskStatus = 'completed' }
    let t = 1000
    expect(await awaitTeamTask(f, caller, 'tt-1', { deadlineMs: 60_000, now: () => t, waitMs: 5 })).toBe('completed')
    expect(f.waits).toBe(1)
  })
  it('始终 pending → 到 deadline 返回 timeout（绝不静默成功）', async () => {
    const f = new FakeTeams()
    let t = 1000
    const now = (): number => t
    f.onWait = () => { t += 30_000 }
    expect(await awaitTeamTask(f, caller, 'tt-1', { deadlineMs: 60_000, now, waitMs: 30_000 })).toBe('timeout')
    expect(f.waits).toBeGreaterThan(0)
  })
})
