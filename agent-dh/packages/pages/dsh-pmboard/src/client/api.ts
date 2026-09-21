/**
 * 项目看板 client 数据层 —— /dashboard/api/reqboard 的类型化 fetch 封装 + SSE 订阅。
 * 模式参照 dsh-taskboard client/api.ts（超时保护 + unwrap + EventSource 重连）。
 *
 * @module dsh-pmboard/client/api
 */
import type { BoardState, TriageList } from './types.ts'
import type { RequirementMarksView, RequirementTokenView, StageDetail, StageOverview } from '../shared/protocol.ts'
import type { InjectionInfoResponse } from './injection-info.ts'

const BASE = '/dashboard/api/reqboard'
const TIMEOUT_MS = 8000

export class ApiError extends Error {
  constructor(message: string, readonly code?: string) { super(message) }
}

async function unwrap<T>(p: Promise<Response>): Promise<T> {
  const res = await p
  if (!res.ok) throw new ApiError('HTTP ' + res.status)
  const json = (await res.json().catch(() => ({}))) as { success?: boolean; data?: T; error?: string; code?: string }
  if (json.success !== true) throw new ApiError(json.error ?? 'API 返回失败', json.code)
  return json.data as T
}

const get = <T>(path: string): Promise<T> =>
  unwrap<T>(fetch(path, { signal: AbortSignal.timeout(TIMEOUT_MS) }))

const post = <T>(path: string, body: unknown): Promise<T> =>
  unwrap<T>(fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  }))

// -- 查询 -----------------------------------------------------------------

export const fetchState = (): Promise<BoardState> => get<BoardState>(BASE + '/')
export const fetchTriage = (): Promise<TriageList> => get<TriageList>(BASE + '/triage')

/**
 * 自动链控制面（REQ-4842fe FR-12 / t-3be71b）：人从看板暂停/继续。
 * 继续 = 服务端置 autoRun=true **并立即触发一次推进事件**（推进器未装配时服务端如实说明）。
 */
export const setAutoRun = (id: string, on: boolean, reason?: string): Promise<BoardState['requirements'][number]> =>
  post(BASE + '/req/autorun', { id, on, ...(reason !== undefined ? { reason } : {}) })

/**
 * 注入留痕只读回查（REQ-422af1 t11）：看板「本次注入了什么」的数据源。
 * windowKey 缺省（人工建卡无来源窗口）→ 不带 window 参数，由服务端返回全量最近 k 条。
 */
export function fetchInjectionInfo(windowKey: string | undefined, k = 20): Promise<InjectionInfoResponse> {
  const qs = new URLSearchParams({ k: String(k) })
  if (windowKey !== undefined && windowKey.length > 0) qs.set('window', windowKey)
  return get<InjectionInfoResponse>(BASE + '/injection-log?' + qs.toString())
}

// -- 需求操作 -------------------------------------------------------------

export function createReq(input: { title: string; description?: string }): Promise<unknown> {
  return post(BASE + '/req/create', input)
}

export function moveReq(input: { id: string; to: string; actor?: string; reason?: string }): Promise<unknown> {
  return post(BASE + '/req/move', input)
}

export function updateReq(input: { id: string; title?: string; description?: string; blocked?: boolean; blockedReason?: string; paused?: boolean }): Promise<unknown> {
  return post(BASE + '/req/update', input)
}

// -- 拆分计划（plan mode，仅人可裁决）--------------------------------------

export function approvePlan(input: { id: string }): Promise<unknown> {
  return post(BASE + '/req/plan/approve', input)
}

export function rejectPlan(input: { id: string; reason: string }): Promise<unknown> {
  return post(BASE + '/req/plan/reject', input)
}

// -- 验收 / 归档（仅人可裁决）----------------------------------------------

/**
 * 验收通过（人工门）。
 * REQ-a8d582 FR-4：有不合格项或尚无验收材料时，后端要求带 `confirm_override`（覆盖说明）；
 * 全过且材料齐全时**不要**传——那不是覆盖，传了会在台账留多余痕迹。
 */
export function verifyPass(input: { id: string; confirm_override?: string }): Promise<unknown> {
  return post(BASE + '/req/verify/pass', input)
}

export function verifyRework(input: { id: string; note: string }): Promise<unknown> {
  return post(BASE + '/req/verify/rework', input)
}

/** 验收单逐项裁决（REQ-2e9473 t14/W6）：逐项 passed/failed + 意见。 */
export function submitVerdicts(input: {
  id: string
  version: number
  verdicts: { itemId: string; status: 'passed' | 'failed'; opinion?: string }[]
}): Promise<unknown> {
  return post(BASE + '/req/verdicts', input)
}

export function archiveReq(input: { id: string }): Promise<unknown> {
  return post(BASE + '/req/archive', input)
}

// -- 节点详情（REQ-31e11f：会话框进度条/看板同源的消费端）-------------------

export function fetchStageDetail(reqId: string, stage: string): Promise<StageDetail> {
  return get<StageDetail>(BASE + '/requirements/' + encodeURIComponent(reqId) + '/stage/' + encodeURIComponent(stage))
}

/** 全流程一览（REQ-31e11f 重设计）：一次取全部节点详情，监控时间线一次渲染。 */
export function fetchStageOverview(reqId: string): Promise<StageOverview> {
  return get<StageOverview>(BASE + '/requirements/' + encodeURIComponent(reqId) + '/stages')
}

/**
 * 单需求 token 去向（REQ-a33899 t6）：详情页「🪙 Token」tab 的数据源。
 */
export function fetchRequirementToken(reqId: string): Promise<RequirementTokenView> {
  return get<RequirementTokenView>(BASE + '/requirements/' + encodeURIComponent(reqId) + '/token')
}

/**
 * 需求侧逐条接收状态（REQ-d3e61a T-5）：详情页「🏷 条款接收状态」块的数据源。
 * 判据（条款 + 任务↔条款绑定）都在文档里，client 拿不到，故由服务端装配。
 */
export function fetchRequirementMarks(reqId: string): Promise<RequirementMarksView> {
  return get<RequirementMarksView>(BASE + '/requirements/' + encodeURIComponent(reqId) + '/marks')
}

/** 读取产物/文档全文（工作区相对路径），供节点详情超链接点击展开。 */
export async function fetchReqFile(path: string): Promise<string> {
  const res = await fetch(BASE + '/file?path=' + encodeURIComponent(path), { signal: AbortSignal.timeout(TIMEOUT_MS) })
  if (!res.ok) throw new ApiError('HTTP ' + res.status)
  const json = (await res.json().catch(() => ({}))) as { success?: boolean; data?: { content?: string }; error?: string }
  if (json.success !== true) throw new ApiError(json.error ?? '读取文档失败')
  return json.data?.content ?? ''
}

/**
 * 文档可打开性批量解析（REQ-b63a7d t4）——「文档记录」区不再逐条打 /file 预检。
 * 旧实现每条路径一发 GET：不在 docs/ 内就被白名单判 403，控制台持续刷红（实测 142 条）。
 * 本端点由 host 单点判定（归一层 + fs），恒 200，且把不可打开的原因一并带回。
 */
export interface DocPathVerdictView {
  /** 原始路径（与请求一一对应，前端据此定位元素） */
  path: string
  normalized: string
  form: 'workspace' | 'outside' | 'pseudo'
  exists: boolean
  openable: boolean
  reason?: string
}

export function resolveReqDocs(paths: string[]): Promise<{ results: DocPathVerdictView[] }> {
  return post<{ results: DocPathVerdictView[] }>(BASE + '/docs/resolve', { paths })
}

/** 产物人工确认（五道人工确认门）：人在看板一键确认某 kind 的产物。 */
export function confirmArtifact(input: { id: string; kind: string }): Promise<unknown> {
  return post(BASE + '/req/artifact/confirm', input)
}

// -- 任务操作 -------------------------------------------------------------

export function createTask(input: Record<string, unknown>): Promise<unknown> {
  return post(BASE + '/task/create', input)
}

export function moveTask(input: { id: string; to: string; actor?: string; reason?: string; sessionId?: string }): Promise<unknown> {
  return post(BASE + '/task/move', input)
}

export function updateTask(input: Record<string, unknown>): Promise<unknown> {
  return post(BASE + '/task/update', input)
}

// -- 评论 -----------------------------------------------------------------

export function addComment(input: { target: 'req' | 'task'; id: string; body: string; actor?: string }): Promise<unknown> {
  return post(BASE + '/comment', input)
}

// -- 待归类操作 -----------------------------------------------------------

export function triageConfirm(input: {
  triageId: string
  action: 'create_req' | 'bind_req'
  targetId?: string
  /** create_req 人工编辑覆盖（可编辑建议卡） */
  title?: string
  category?: string
  description?: string
}): Promise<unknown> {
  return post(BASE + '/triage/confirm', input)
}

export function triageRebind(input: { triageId: string; targetId: string }): Promise<unknown> {
  return post(BASE + '/triage/rebind', input)
}

export function triageReject(input: { triageId: string }): Promise<unknown> {
  return post(BASE + '/triage/reject', input)
}

// -- SSE ------------------------------------------------------------------

/**
 * 订阅台账变更（revision + kind）。SSE 断开由调用方决定重连策略；
 * 返回退订函数。EventSource 自带重连，这里只包一层生命周期管理。
 */
export function subscribeEvents(onChange: (revision: number, kind: string) => void): () => void {
  const es = new EventSource(BASE + '/events')
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse((ev as MessageEvent).data as string) as { revision: number; kind: string }
      onChange(data.revision, data.kind)
    } catch { /* 忽略坏帧 */ }
  }
  return () => es.close()
}