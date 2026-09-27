/**
 * FR-11 路线 A：子卡实施段的**团队派发助手**（Lead 侧）。
 *
 * 设计约束（实测，见 docs/architecture/agent-teams-subtask-execution.md §4.1）：
 * 任务板只承载"状态"——`TeamTaskView` 没有产出字段，`TeamService` 也没有可查询的收件箱
 * （消息投递进目标会话，插件读不到）。所以**产出必须由 Worker 自己写台账**
 * （调 `reqboard_task_report`），链只等"completed"信号。本模块因此只负责三件事：
 * 给 Worker 起个能认出来的名字、**幂等**确保它在跑、事件驱动地等任务完成。
 *
 * @module dsh-pmboard/application/internal/team-dispatch
 */
import type { AgentTeamsPort, TeamMemberViewLike } from '../ports.js'

/** Worker 名（同一父卡一条链共用同一个 Worker；名字即可寻址）。 */
export function teamWorkerName(parentId: string): string {
  return 'reqboard-' + parentId
}

/** 共享任务标题（人可读 + 带阶段）；stageKind 缺失时回退 'task'。 */
export function teamTaskSubject(stageKind: string | undefined, title: string): string {
  const kind = stageKind === undefined || stageKind.length === 0 ? 'task' : stageKind
  return '[' + kind + '] ' + title
}

/**
 * **父卡标记**——"一个父卡 = 一个团队"的机器可读边界。
 *
 * 原生 TeamService 的 TeamId = 根 Session（一个会话只有一个隐式团队），所以"父卡级团队"只能落成
 * **逻辑分区**：每个父卡一个 Worker + 该父卡全部 team task 都带这个标记；Worker 只认领本队的任务，
 * 不碰别的父卡的（否则 N 个父卡 N 个 Worker 会互相抢活）。
 */
export function parentMarker(parentId: string): string {
  return '[reqboard:parent=' + parentId + ']'
}

/** 任务是否属于该父卡的队（description 首段带父卡标记）。 */
export function belongsToParent(description: string, parentId: string): boolean {
  return typeof description === 'string' && description.startsWith(parentMarker(parentId))
}

/**
 * 调用者是不是**该卡的合法认领人**（FR-11 路线 A 的台账写回授权）。
 *
 * 为什么需要它：Worker 是 spawn 出的独立会话，窗口码 ≠ 需求 `sourceSessionId`，
 * 于是 `ReportTask` 原有的"窗口绑定"越权校验对 Worker **恒拒**
 * （实测：`REQBOARD_NOT_BOUND_TO_WINDOW`）——而路线 A 的设计恰恰要求 Worker 自己写台账，
 * 不修则第二张卡起链必停。
 *
 * **授权只取自 live TeamService + 任务自身的 teamTaskId，不取自用户输入**：
 *   ① 调用者必须是该 team 的成员（按会话 id / 名字命中名册）；
 *   ② 该 team task 的 `ownerName` 必须正是这个成员（"你认领的卡，你来汇报"）。
 * 任何一步不成立 → false（调用方回落到原窗口绑定校验，照旧拒绝）。
 */
export function ownsTeamTask(
  teams: AgentTeamsPort,
  callerAgent: unknown,
  callerWindowKey: string,
  teamTaskId: string | undefined,
): boolean {
  if (teamTaskId === undefined || callerAgent === undefined) return false
  try {
    const me = teams.listMembers(callerAgent).find((m) => m.id === callerWindowKey || m.name === callerWindowKey)
    if (me === undefined) return false
    const tt = teams.listTasks(callerAgent).find((t) => t.id === teamTaskId)
    return tt !== undefined && tt.ownerName === me.name
  } catch {
    // 服务未装配 / 调用者不是团队成员 / 任务不存在 —— 一律不放行（保守方向：拒绝 > 误放）
    return false
  }
}

/** 成员是否"活着"（可继续接活）。failed/inactive 视为已死，需重起。 */
export function isAliveMember(m: TeamMemberViewLike): boolean {
  return m.status === 'running' || m.status === 'idle' || m.status === 'provisioning'
}

/**
 * 幂等确保 Worker 在跑（三态，名字 = 幂等键）：
 *   ① 无名册成员        → spawnWorker 起一个；
 *   ② 有名册成员且活着  → 直接复用；
 *   ③ 有名册成员但已停  → **唤醒**（sendMessage），**绝不重起**。
 *
 * 为什么 ③ 只能唤醒：TeamService 的 teammate 名字**唯一且不可复用**——实测同名重起被拒
 * （teammate name "reqboard-t-3e3ebb" was already used in this Team），重起会让链直接报错、
 * 再也起不来。teammate 是 durable/continuable 的，inactive 成员 sendMessage 即 cold-resume。
 *
 * 为什么必须幂等：链是"状态即事实"的——若每次推进都起一个，任务会被多个 Worker 重复认领。
 */
export async function ensureWorker(
  teams: AgentTeamsPort,
  caller: unknown,
  parentId: string,
  prompt: string,
): Promise<TeamMemberViewLike> {
  const name = teamWorkerName(parentId)
  const existing = teams.listMembers(caller).find((m) => m.name === name)
  if (existing !== undefined) {
    if (isAliveMember(existing)) return existing
    await teams.sendMessage(caller, { target: name, content: prompt })
    return existing
  }
  return teams.spawnWorker(caller, {
    name,
    description: 'reqboard 实施链 Worker（' + parentId + '）',
    prompt,
  })
}

/**
 * 等 team task 到 completed；超时返回 'timeout'（调用方决定降级/失败，**绝不静默成功**）。
 *
 * 事件驱动：`waitForChange` 到点即醒，不做忙轮询；每轮先查一次状态，避免"刚做完就睡 20s"。
 */
export async function awaitTeamTask(
  teams: AgentTeamsPort,
  caller: unknown,
  teamTaskId: string,
  opts: { deadlineMs: number; now: () => number; waitMs?: number },
): Promise<'completed' | 'timeout'> {
  const end = opts.now() + opts.deadlineMs
  for (;;) {
    if (teams.getTask(caller, teamTaskId).status === 'completed') return 'completed'
    const left = end - opts.now()
    if (left <= 0) return 'timeout'
    await teams.waitForChange(caller, Math.min(opts.waitMs ?? 20_000, left))
  }
}
