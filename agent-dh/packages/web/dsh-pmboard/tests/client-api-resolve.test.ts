/**
 * client 文档批量解析 helper 契约单测（REQ-b63a7d t4）。
 *
 * 锁定：resolveReqDocs 打 POST /dashboard/api/reqboard/docs/resolve，请求体 {paths:[...]}，
 * 响应经 unwrap（success!==true 抛错）后返回 results。前端「文档记录」区不再逐条打 /file，
 * 故这条契约一旦漂移（路径/信封变了），控制台 403 刷屏会原样回归。
 */
import { describe, it, expect, afterEach } from 'vitest'
import { resolveReqDocs } from '../src/client/api.ts'

const realFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = realFetch })

interface Call { url: string; body: unknown }

function stubFetch(payload: unknown, ok = true, status = 200): Call[] {
  const calls: Call[] = []
  globalThis.fetch = (async (url: unknown, init: unknown) => {
    const i = (init ?? {}) as { body?: string }
    calls.push({ url: String(url), body: i.body === undefined ? undefined : JSON.parse(i.body) })
    return { ok, status, json: async () => payload } as unknown as Response
  }) as unknown as typeof fetch
  return calls
}

describe('resolveReqDocs 契约（REQ-b63a7d t4）', () => {
  it('打 POST /docs/resolve 且请求体为 {paths}', async () => {
    const calls = stubFetch({ success: true, data: { results: [{ path: 'a.md', normalized: 'a.md', form: 'workspace', exists: true, openable: true }] } })
    const data = await resolveReqDocs(['a.md', 'b.ts'])
    expect(calls.length).toBe(1)
    expect(calls[0]!.url).toBe('/dashboard/api/reqboard/docs/resolve')
    expect(calls[0]!.body).toEqual({ paths: ['a.md', 'b.ts'] })
    expect(data.results.length).toBe(1)
    expect(data.results[0]!.openable).toBe(true)
  })

  it('success=false → 抛错（不把失败当空结果）', async () => {
    stubFetch({ success: false, error: '坏了' })
    await expect(resolveReqDocs(['a.md'])).rejects.toThrow()
  })

  it('HTTP 非 2xx → 抛错', async () => {
    stubFetch({}, false, 500)
    await expect(resolveReqDocs(['a.md'])).rejects.toThrow()
  })
})
