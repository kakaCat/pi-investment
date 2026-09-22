// serves: FR-4
/**
 * 文档路径绝对化（REQ-260922012924-2e29 FR-4 / TC-4）。
 *
 * 覆盖：①state 端点暴露 workspaceRoot（= deps.cwd ?? process.cwd()）与 homeDir；
 * ②客户端 absolutizeDocPath/displayDocPath（绝对化、~ 缩写、无根降级原样）；
 * ③sessionFileAddress 绝对路径构造（前导斜杠保留——dsh-resource 协议口径）。
 *
 * @module dsh-pmboard/tests/state-workspace-root
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { EventEmitter } from 'node:events'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import {
  setDocWorkspaceContext,
  absolutizeDocPath,
  displayDocPath,
} from '../src/client/open-doc.js'
import { sessionFileAddress } from '../src/client/file-address.js'

function fakeReq(url: string): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = 'GET'
  req[Symbol.asyncIterator] = async function* () { /* no body */ }
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

let dir: string
let store: ReqboardStore
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-wsroot-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

describe('state 端点暴露 workspaceRoot/homeDir（FR-4）', () => {
  it('显式 cwd → workspaceRoot 等于它；homeDir 为绝对路径', async () => {
    const ws = join(dir, 'fake-workspace')
    const handler = createReqboardHandler({ store, now: () => Date.now(), cwd: ws })
    const res = fakeRes()
    await handler(fakeReq('/dashboard/api/reqboard/state'), res)
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.workspaceRoot).toBe(ws)
    expect(typeof res.payload.data.homeDir).toBe('string')
    expect(res.payload.data.homeDir.startsWith('/')).toBe(true)
  })

  it('未传 cwd → workspaceRoot 回落 process.cwd()', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = fakeRes()
    await handler(fakeReq('/dashboard/api/reqboard/state'), res)
    expect(res.payload.data.workspaceRoot).toBe(process.cwd())
  })
})

describe('客户端绝对化（FR-4）', () => {
  const ROOT = '/Users/test/pi-investment/agent-dh'
  const HOME = '/Users/test'

  it('有缓存根：相对路径 → 根+相对；前导 ./ 剥掉', () => {
    setDocWorkspaceContext(ROOT, HOME)
    expect(absolutizeDocPath('docs/requirements/REQ-x/requirement.md')).toBe(ROOT + '/docs/requirements/REQ-x/requirement.md')
    expect(absolutizeDocPath('./docs/a.md')).toBe(ROOT + '/docs/a.md')
  })

  it('绝对路径原样返回（不再拼根）', () => {
    setDocWorkspaceContext(ROOT, HOME)
    expect(absolutizeDocPath('/etc/hosts')).toBe('/etc/hosts')
  })

  it('displayDocPath：homeDir 前缀缩写为 ~', () => {
    setDocWorkspaceContext(ROOT, HOME)
    expect(displayDocPath('docs/requirements/REQ-x/requirement.md')).toBe('~/pi-investment/agent-dh/docs/requirements/REQ-x/requirement.md')
  })

  it('无缓存根（旧服务端）→ 相对路径原样返回（显示降级，非失败）', () => {
    setDocWorkspaceContext(undefined, undefined)
    expect(absolutizeDocPath('docs/a.md')).toBe('docs/a.md')
    expect(displayDocPath('docs/a.md')).toBe('docs/a.md')
  })

  it('sessionFileAddress：绝对路径前导斜杠保留（Host 按绝对路径读，与会话工作区无关）', () => {
    const addr = sessionFileAddress('session-x', ROOT + '/docs/requirements/REQ-x/requirement.md')
    expect(addr).toBe('dsh-resource://file/session/session-x/' + ROOT + '/docs/requirements/REQ-x/requirement.md')
  })
})
