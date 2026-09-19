/**
 * /reqboard/file 与 /docs/resolve 路由单测（REQ-b63a7d t3/t4）——真实临时目录，不 mock fs。
 *
 * 锁定口径（对应需求验收 A1/A2/A3 与伪路径/批量端点）：
 *   A1 仓库根相对（agent-dh/docs/...）与工作区相对（docs/...）读同一份文件都 200；
 *   A2 ../../etc/passwd 与 /etc/passwd 仍 403（穿越防护未因放宽 allowlist 而削弱）；
 *   A3 落工作区外的兄弟仓库路径 → 404 outside_workspace（不再冒充 403）；
 *   A4 伪路径（brace 汇总写法）→ 404 not_a_file；
 *   A5 批量端点一次返回全部结论且含原因（前端不再逐条预检）。
 *
 * 工作区目录名必须可预测（归一层按 basename 剥前缀），故临时目录下建 agent-dh/。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../../src/http/routes.js'

let base: string
let root: string
let store: ReqboardStore

beforeEach(() => {
  base = mkdtempSync(join(tmpdir(), 'pmboard-docs-'))
  root = join(base, 'agent-dh')
  mkdirSync(root, { recursive: true })
  mkdirSync(join(root, 'docs/architecture'), { recursive: true })
  mkdirSync(join(root, 'packages/pages'), { recursive: true })
  mkdirSync(join(root, 'docs/subdir'), { recursive: true })
  mkdirSync(join(base, 'quantsys-v2'), { recursive: true })
  writeFileSync(join(root, 'docs/architecture/documentation-standard.md'), '# doc')
  writeFileSync(join(root, 'packages/pages/x.ts'), 'export const x = 1')
  writeFileSync(join(base, 'quantsys-v2/main.py'), '# sibling repo file')
  store = new ReqboardStore({ file: join(root, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(base, { recursive: true, force: true }) })

/** 假请求：带 url/method，且可被 readBody 的 for await 消费。 */
function fakeReq(method: string, url: string, body?: unknown): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = method
  req[Symbol.asyncIterator] = async function* () {
    if (body !== undefined) yield Buffer.from(JSON.stringify(body), 'utf8')
  }
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

const newHandler = () => createReqboardHandler({ store, now: () => 1000, cwd: root })

async function readFile(path: string) {
  const res = fakeRes()
  await newHandler()(fakeReq('GET', '/dashboard/api/reqboard/file?path=' + encodeURIComponent(path)), res)
  return res
}

async function resolve(paths: string[]) {
  const res = fakeRes()
  await newHandler()(fakeReq('POST', '/dashboard/api/reqboard/docs/resolve', { paths }), res)
  return res
}

describe('A1 合法文件读取：前缀写法不再判为越界', () => {
  it('仓库根相对（agent-dh/docs/...）→ 200', async () => {
    const res = await readFile('agent-dh/docs/architecture/documentation-standard.md')
    expect(res.statusCode).toBe(200)
    expect(res.payload.success).toBe(true)
    expect(res.payload.data.path).toBe('docs/architecture/documentation-standard.md')
    expect(res.payload.data.content).toContain('doc')
  })

  it('工作区相对（docs/...）→ 200，与上一条同结果', async () => {
    const res = await readFile('docs/architecture/documentation-standard.md')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.path).toBe('docs/architecture/documentation-standard.md')
  })

  it('源码类产物（packages/...）→ 200（allowlist 已放宽到工作区根）', async () => {
    const res = await readFile('packages/pages/x.ts')
    expect(res.statusCode).toBe(200)
  })

  it('工作区内绝对路径 → 200（兼容存量记录）', async () => {
    const res = await readFile(join(root, 'packages/pages/x.ts'))
    expect(res.statusCode).toBe(200)
  })
})

describe('A2 穿越防护未被放宽', () => {
  it('../../etc/passwd → 403', async () => {
    const res = await readFile('../../etc/passwd')
    expect(res.statusCode).toBe(403)
    expect(res.payload.code).toBe('forbidden')
  })

  it('/etc/passwd（工作区外绝对路径）→ 403', async () => {
    const res = await readFile('/etc/passwd')
    expect(res.statusCode).toBe(403)
  })
})

describe('A3 跨仓路径 → 404 outside_workspace', () => {
  it('兄弟仓库文件不再冒充权限问题', async () => {
    const res = await readFile('quantsys-v2/main.py')
    expect(res.statusCode).toBe(404)
    expect(res.payload.code).toBe('outside_workspace')
  })

  it('目录路径（不是文件）→ 404 not_found', async () => {
    const res = await readFile('docs/subdir')
    expect(res.statusCode).toBe(404)
    expect(res.payload.code).toBe('not_found')
  })

  it('尾斜杠路径同样按"不是文件"处理', async () => {
    const res = await readFile('docs/subdir/')
    expect(res.statusCode).toBe(404)
  })

  it('工作区内缺失 → 404 not_found', async () => {
    const res = await readFile('docs/not-there.md')
    expect(res.statusCode).toBe(404)
    expect(res.payload.code).toBe('not_found')
  })
})

describe('A4/A5 伪路径与批量解析端点', () => {
  it('brace 汇总写法 → 404 not_a_file', async () => {
    const res = await readFile('quantsys-v2/tests/{a.py,b.py}')
    expect(res.statusCode).toBe(404)
    expect(res.payload.code).toBe('not_a_file')
  })

  it('批量端点恒 200，逐条给出 form/exists/openable/reason', async () => {
    const res = await resolve([
      'agent-dh/docs/architecture/documentation-standard.md',
      'packages/pages/x.ts',
      'quantsys-v2/main.py',
      'quantsys-v2/tests/{a.py,b.py}',
      'docs/not-there.md',
    ])
    expect(res.statusCode).toBe(200)
    const byPath = new Map<string, any>(res.payload.data.results.map((r: any): [string, any] => [r.path, r]))
    expect(byPath.get('agent-dh/docs/architecture/documentation-standard.md').openable).toBe(true)
    expect(byPath.get('packages/pages/x.ts').openable).toBe(true)
    expect(byPath.get('quantsys-v2/main.py').openable).toBe(false)
    expect(byPath.get('quantsys-v2/main.py').form).toBe('outside')
    expect(String(byPath.get('quantsys-v2/main.py').reason)).toContain('工作区之外')
    expect(byPath.get('quantsys-v2/tests/{a.py,b.py}').form).toBe('pseudo')
    expect(byPath.get('docs/not-there.md').openable).toBe(false)
  })

  it('批量端点：空数组不报错（诚实空结果）', async () => {
    const res = await resolve([])
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.results).toEqual([])
  })
})
