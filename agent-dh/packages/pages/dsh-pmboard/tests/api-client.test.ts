/**
 * client/api.ts 回归测试 —— 真实 fetch 语义防线。
 *
 * 背景（2026-09-10 事故）：unwrap 曾把 fetch 的 Promise<Response> 直接当 Response
 * 检查 res.ok（Promise.ok === undefined → 抛 'HTTP undefined'），真实浏览器必挂，
 * 但当时 mock fetch 返回同步对象（非 Promise）→ res.ok 有值 → 测试假通过。
 *
 * 本文件 mock 一律返回「真 Promise<Response>」，与浏览器 fetch 语义一致；
 * 在旧 buggy unwrap 下 fetchState 会抛 'HTTP undefined'，本测试即失败。
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

// 每个用例独立替换全局 fetch
const origFetch = globalThis.fetch

function mockFetchOnce(status: number, body: unknown): void {
  vi.stubGlobal('fetch', vi.fn(() =>
    Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })),
  ))
}

afterEach(() => {
  vi.unstubAllGlobals()
  if (origFetch) globalThis.fetch = origFetch
})

describe('client api unwrap（真实 Promise<Response> 语义）', () => {
  it('fetchState 解析成功响应', async () => {
    mockFetchOnce(200, { success: true, data: { revision: 1, requirements: [], tasks: [], ready: {} } })
    const { fetchState } = await import('../src/client/api.js')
    const state = await fetchState()
    expect(state.revision).toBe(1)
    expect(Array.isArray(state.requirements)).toBe(true)
  })

  it('fetchTriage 解析 pending 列表', async () => {
    mockFetchOnce(200, { success: true, data: { pending: [{ triageId: 't1' }] } })
    const { fetchTriage } = await import('../src/client/api.js')
    const triage = await fetchTriage()
    expect(triage.pending).toHaveLength(1)
  })

  it('HTTP 非 200 抛出 HTTP <status>（而非 HTTP undefined）', async () => {
    mockFetchOnce(503, { success: false })
    const { fetchState } = await import('../src/client/api.js')
    await expect(fetchState()).rejects.toThrow('HTTP 503')
  })

  it('success=false 抛出后端 error 文案', async () => {
    mockFetchOnce(200, { success: false, error: '看板未就绪' })
    const { fetchState } = await import('../src/client/api.js')
    await expect(fetchState()).rejects.toThrow('看板未就绪')
  })
})
