/**
 * 项目看板 client 数据层 —— /dashboard/api/reqboard 的类型化 fetch 封装 + SSE 订阅。
 * 模式参照 dsh-taskboard client/api.ts（超时保护 + unwrap + EventSource 重连）。
 *
 * @module dsh-pmboard/client/api
 */
import type { BoardState, TriageList } from './types.ts'

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
