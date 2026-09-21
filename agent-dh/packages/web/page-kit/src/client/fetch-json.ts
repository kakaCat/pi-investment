/**
 * Fetch JSON 包装 —— 所有 DSH GUI page 共享。
 * 统一处理 fetch → json → success 检查 → 抛出结构化错误。
 *
 * @module page-kit/client/fetch-json
 */

export interface FetchJsonOptions {
  url: string
  method?: 'GET' | 'POST'
  headers?: Record<string, string>
  body?: unknown
}

export interface FetchJsonResult<T = unknown> {
  success: boolean
  data?: T
  error?: string
}

/** GET 请求 JSON 并校验 success 标志 */
export async function fetchJson<T = unknown>(url: string, init?: RequestInit): Promise<FetchJsonResult<T>> {
  const res = await fetch(url, init)
  if (!res.ok) return { success: false, error: 'HTTP ' + res.status }
  const json = (await res.json().catch(() => ({}))) as any
  if (json.success !== true) return { success: false, error: json.error ?? json.message ?? 'API 返回失败' }
  return { success: true, data: json.data }
}

/** POST JSON 并返回结果 */
export async function postJson<T = unknown>(url: string, body: unknown): Promise<FetchJsonResult<T>> {
  return fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}
