/**
 * isolation-log 只读端点测试（REQ-260923134706-e72f / t2，TC-9）。
 *
 * 用假 req/res 直连 createReqboardHandler（不起真服务器），断言：
 *  1. k 非 1..200 整数 → 400（badInput 口径与 injection-log 一致）；
 *  2. 端口未装配 → 200 + available=false + 空清单（看板不红）；
 *  3. window 过滤生效（只回该窗口的留痕，total 正确）；
 *  4. 留痕文件损坏（readAll 抛错）→ 降级 available=false + 空清单，不 500；
 *  5. 正常路径：写入顺序旧→新、取最近 k 条、available=true。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import type { IsolationTraceEntry } from '../src/application/use-cases/IsolateNodeContext.js'

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-isolation-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function fakeReq(url: string): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = 'GET'
  return req
}
function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.payload = undefined
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}
async function get(handler: any, url: string) {
  const res = fakeRes()
  await handler(fakeReq(`/dashboard/api/reqboard${url}`), res)
  return res
}

function entry(over: Partial<IsolationTraceEntry>): IsolationTraceEntry {
  return {
    at: 1000, windowKey: 'w-a', stage: 'implementing', status: 'replaced',
    reason: '节点结算替换', routeKey: 'implementing/heavy/feature', packageChars: 4200,
    range: { start: 10, end: 20 }, ...over,
  }
}

function stubLog(entries: IsolationTraceEntry[] | 'throw') {
  return {
    readAll: async () => {
      if (entries === 'throw') throw new Error('node-isolation-log.json 损坏')
      return entries
    },
  }
}

describe('GET /isolation-log', () => {
  it('k 非法 → 400', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now(), isolationLog: stubLog([]) })
    for (const bad of ['k=0', 'k=201', 'k=abc', 'k=1.5', 'k=-3']) {
      const res = await get(handler, `/isolation-log?${bad}`)
      expect(res.statusCode, bad).toBe(400)
      expect(res.payload.success).toBe(false)
    }
  })

  it('端口未装配 → available=false + 空清单（不报错）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/isolation-log')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.available).toBe(false)
    expect(res.payload.data.entries).toEqual([])
    expect(res.payload.data.total).toBe(0)
  })

  it('window 过滤生效：只回该窗口留痕，total 为过滤后条数', async () => {
    const log = stubLog([
      entry({ at: 1, windowKey: 'w-a', stage: 'draft' }),
      entry({ at: 2, windowKey: 'w-b', stage: 'brainstorming' }),
      entry({ at: 3, windowKey: 'w-a', stage: 'design' }),
      entry({ at: 4, windowKey: 'w-c', stage: 'implementing' }),
    ])
    const handler = createReqboardHandler({ store, now: () => Date.now(), isolationLog: log })
    const res = await get(handler, '/isolation-log?window=w-a')
    expect(res.statusCode).toBe(200)
    const d = res.payload.data
    expect(d.available).toBe(true)
    expect(d.total).toBe(2)
    expect(d.entries.map((e: IsolationTraceEntry) => e.stage)).toEqual(['draft', 'design'])
    expect(d.window).toBe('w-a')
  })

  it('留痕文件损坏（readAll 抛错）→ 降级 available=false，不 500', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now(), isolationLog: stubLog('throw') })
    const res = await get(handler, '/isolation-log')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.available).toBe(false)
    expect(res.payload.data.entries).toEqual([])
  })

  it('正常路径：旧→新顺序、取最近 k 条、available=true', async () => {
    const log = stubLog([
      entry({ at: 1, stage: 'draft' }),
      entry({ at: 2, stage: 'brainstorming' }),
      entry({ at: 3, stage: 'design' }),
      entry({ at: 4, stage: 'decomposing' }),
      entry({ at: 5, stage: 'implementing' }),
    ])
    const handler = createReqboardHandler({ store, now: () => Date.now(), isolationLog: log })
    const res = await get(handler, '/isolation-log?k=2')
    expect(res.statusCode).toBe(200)
    const d = res.payload.data
    expect(d.available).toBe(true)
    expect(d.total).toBe(5)
    expect(d.entries.map((e: IsolationTraceEntry) => e.stage)).toEqual(['decomposing', 'implementing'])
  })

  it('window 缺省 = 全量最近 k 条', async () => {
    const log = stubLog([
      entry({ at: 1, windowKey: 'w-a' }),
      entry({ at: 2, windowKey: 'w-b' }),
    ])
    const handler = createReqboardHandler({ store, now: () => Date.now(), isolationLog: log })
    const res = await get(handler, '/isolation-log')
    expect(res.payload.data.total).toBe(2)
    expect(res.payload.data.window).toBe(null)
  })
})
