/**
 * FR-11 路线 A：子卡**团队执行驱动**（executeSubtask 在团队服务可用且调用方是 live agent 时调它）。
 *
 * 职责边界刻意很窄：建/复用 team task → 幂等确保 Worker 在跑 → 事件驱动等 completed →
 * **把 Worker 写进台账的 lastReport 读回来**，交回调用方合成 workflow 同款产出形状。
 * 下游（解析 / 跨卡检测 / 落账 / 凭证门）逐字复用既有路径，本文件不重复实现。
 *
 * 为什么产出要从台账读：`TeamTaskView` 只有状态，`TeamService` 没有可查询收件箱
 * （消息投递进目标会话，插件读不到）——Worker 只能经 `reqboard_task_report` 把产出写进台账。
 * 见 docs/architecture/agent-teams-subtask-execution.md §4.1。
 *
 * @module dsh-pmboard/application/use-cases/SubtaskTeamRun
 */
import type { AgentTeamsPort, UseCaseDeps } from '../ports.js'
import type { TaskRecord } from '../../shared/protocol.js'
import { teamTaskSubject, ensureWorker, awaitTeamTask, parentMarker } from '../internal/team-dispatch.js'
import { taskStoreOf } from './queue-access.js'

/** 单张子卡的团队等待上限；超时按失败处理（绝不静默成功）。 */
const TEAM_DEADLINE_MS = 30 * 60_000

export interface SubtaskTeamRunInput {
  task: TaskRecord
  parent: TaskRecord
  /** live Lead Agent 句柄（TeamService 的 authority credential）。 */
  caller: unknown
  /** 交给 Worker 的完整工作要求（buildSubtaskPrompt 的产出）。 */
  prompt: string
  /** 为**同队其它子卡**构造工作要求（一次性建全队任务时用；避免本文件反向 import ExecuteTask）。 */
  promptFor: (t: TaskRecord) => string
}

export interface SubtaskTeamRunOutcome {
  ok: boolean
  reason?: string
  filesChanged: string[]
  summary: string
}

/**
 * team task 描述：**首段必须是父卡标记**（"一个父卡 = 一个团队"的边界，Worker 据此只认本队任务），
 * 且**必须带台账子卡 id**——Worker 只有拿到它才能把产出写回台账。
 */
export function teamTaskDescription(task: TaskRecord, parent: TaskRecord, prompt: string): string {
  return [
    parentMarker(parent.id) + '  【reqboard 台账子卡 id】' + task.id + '（父卡 ' + parent.id + '，阶段 ' + String(task.stageKind ?? '') + '）',
    '【产出必须写台账】干完必须调 reqboard_task_report(task_id="' + task.id + '", summary/completed/files_changed)；',
    '链读不到团队收件箱，**只有台账能带回结果**——漏写＝这张子卡判没干活。',
    '',
    prompt,
  ].join('\n')
}

/** Worker 常驻循环提示词：claim → 干活 → 写台账 → complete → 回到 1。 */
export function buildWorkerLoopPrompt(parent: TaskRecord): string {
  return [
    '你是 reqboard 实施链的**持久 Worker**（Team Worker），常驻接活，不要自行扩大范围。',
    '',
    '工作循环（每轮）：',
    '0) **只认领本队任务**：本队 = 父卡 ' + parent.id + '，标记 ' + parentMarker(parent.id),
    '   ——description 不以该标记开头的任务一律不碰（那是别的父卡的队）；',
    '1) team_task_list 看共享任务板；挑 status=pending、ready=true、且 description 带本队标记的任务；',
    '2) team_task_get 读全文——description 里是这一张子卡的完整工作要求与**台账子卡 id**；',
    '3) team_task_update(action=claim, expected_revision=刚读到的 revision)；',
    '4) 严格按该卡验收标准干活（改代码 / 跑测试 / 给出结论）；',
    '5) **调 reqboard_task_report(task_id=<台账子卡 id>, summary, completed, files_changed)**',
    '   把产出写进 reqboard 台账——这是链唯一能读到结果的通道；',
    '6) team_task_update(action=complete) 收口，回到 1)。',
    '',
    '纪律：一次只 claim 一张；只改你那张卡写范围内的文件；本链父卡 = ' + parent.id + '（' + parent.title + '）。',
  ].join('\n')
}

/**
 * 确保**该父卡（一队）的全部子卡 team task 就位**（幂等），并返回本张子卡的 teamTaskId。
 *
 * 为什么一次建全队：FR-11 要的是"原生 DAG + Worker 自 claim"——只有把整条子卡链一次性放上任务板、
 * 用 `blockedBy` 串起来，`TeamService` 才会**自动算 ready**（依赖未完成的卡 ready=false），
 * Worker 才能自己挑 ready 卡并天然获得负载均衡。逐张建＝调度权还在链手里，就退化成"远程执行"。
 *
 * 链序 = 台账数组顺序（`expandSubtasks` 按阶段序创建，数组序即链序）。
 */
export async function ensureParentTeamTasks(
  deps: UseCaseDeps,
  teams: AgentTeamsPort,
  caller: unknown,
  parent: TaskRecord,
  selfTaskId: string,
  promptFor: (t: TaskRecord) => string,
): Promise<string> {
  const store = taskStoreOf(deps)
  // 任务已迁出台账（v9）：同队子卡清单从队列取（父子树由 parentId 表达）。
  const siblings = (await store.listByRequirement(parent.requirementId)).filter((t) => t.parentId === parent.id)
  const links = new Map<string, string>()
  for (const s of siblings) if (s.teamTaskId !== undefined) links.set(s.id, s.teamTaskId)
  let prev: string | undefined
  for (const s of siblings) {
    // 已完成/已取消的卡不再建任务（避免把收口过的活重新放回板上被 Worker 再认领一次）；
    // 若它有既有 teamTaskId，仍作为下一张的 blockedBy（它已完成 → 不阻塞）。
    if (s.status === 'done' || s.status === 'canceled') {
      const doneTid = links.get(s.id)
      if (doneTid !== undefined) prev = doneTid
      continue
    }
    let tid = links.get(s.id)
    if (tid === undefined) {
      const created = await teams.createTask(caller, {
        subject: teamTaskSubject(s.stageKind, s.title),
        description: teamTaskDescription(s, parent, promptFor(s)),
        ...(prev !== undefined ? { blockedBy: [prev] } : {}),
        ...(s.scope?.files !== undefined && s.scope.files.length > 0 ? { writeScopes: [...s.scope.files] } : {}),
      })
      tid = created.id
      links.set(s.id, tid)
      await store.mutate(s.requirementId, (tasks) => {
        const t = tasks.find((x) => x.id === s.id)
        if (t === undefined) return undefined
        t.teamTaskId = tid
        return tasks
      })
    }
    prev = tid
  }
  return links.get(selfTaskId) ?? ''
}

export async function runSubtaskViaTeam(deps: UseCaseDeps, input: SubtaskTeamRunInput): Promise<SubtaskTeamRunOutcome> {
  const store = taskStoreOf(deps)
  const teams = deps.teams
  if (teams === undefined) return { ok: false, reason: 'team_unavailable', filesChanged: [], summary: '' }
  const { task, parent, caller } = input
  const dispatchedAt = deps.clock.now()
  try {
    // 1) 一次性建好**本队全部** team task（幂等）→ 原生 DAG（blockedBy）上板 → DSH 自动算 ready
    const teamTaskId = await ensureParentTeamTasks(deps, teams, caller, parent, task.id, input.promptFor)
    if (teamTaskId.length === 0) {
      return { ok: false, reason: 'team_task_missing', filesChanged: [], summary: '' }
    }
    // 2) 幂等确保 Worker 在跑（名字 = 幂等键，重复事件不得堆 Worker）
    await ensureWorker(teams, caller, parent.id, buildWorkerLoopPrompt(parent))
    // 3) 事件驱动等 completed
    const settled = await awaitTeamTask(teams, caller, teamTaskId, {
      deadlineMs: TEAM_DEADLINE_MS,
      now: () => deps.clock.now(),
    })
    if (settled !== 'completed') {
      return { ok: false, reason: 'team_wait_timeout', filesChanged: [], summary: '' }
    }
    // 4) 把 Worker 写进队列的产出读回来（队列是唯一结果通道；台账 v9 已无 tasks）
    const rep = (await store.get(task.id))?.lastReport
    const files = [...(rep?.filesChanged ?? [])]
    const done = [...(rep?.completed ?? [])]
    // 两道诚实门（2026-09-27 E2E 实测发现）：
    // ① **没写台账**时不得合成"格式合法的空产出"——否则结论族（review/test）会拿链路合成的
    //    JSON 信封串当"结论非空"而**假通过**；
    // ② 台账必须是**本次派发之后**写的——否则早前直接执行留下的历史报告会让本卡侥幸通过
    //    （t-c42bc0 就是这么过的），等于把"Worker 干没干"又退化回推断。
    if (rep === undefined || (files.length === 0 && done.length === 0)) {
      return { ok: false, reason: 'team_report_missing', filesChanged: [], summary: '' }
    }
    if (rep.at < dispatchedAt) {
      return { ok: false, reason: 'team_report_stale', filesChanged: [], summary: '' }
    }
    return { ok: true, filesChanged: files, summary: done.join(' / ') }
  } catch (err) {
    const code = (err as { code?: string }).code
    return {
      ok: false,
      reason: (code ?? 'team_error') + ': ' + String((err as Error).message ?? err),
      filesChanged: [],
      summary: '',
    }
  }
}
