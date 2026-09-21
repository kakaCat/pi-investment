/**
 * 看板「本次注入了什么」只读块——REQ-422af1 t11 / INV-6 的看板可见面。
 *
 * 三条验收（逐条可执行）：
 *   ① 字段与留痕一致：只读接口返回的条目与写入留痕逐字段相等；渲染文本含同样的值。
 *   ② 无留痕时渲染「尚无记录」（不是空白、不是报错）。
 *   ③ 注入 `<script>` 探针时输出被转义（含转义实体、无可执行标签）。
 * 另加：只读性（GET 不改留痕文件）、窗口过滤、k 边界。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { EventEmitter } from 'node:events'
import { mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { hasInjectionWindow, renderInjectionInfo, type InjectionInfoEntry } from '../src/client/injection-info.ts'
import { buildReqDetail } from '../src/client/view.ts'
import { fmtTime } from '../src/client/render/dom-utils.ts'
import { InjectionLogFile } from '../src/adapters/InjectionLogFile.js'
import {
  injectionLogInputFromResolved,
  type InjectionLogEntry,
} from '../src/application/internal/injection-log.js'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'
import type { RequirementRecord } from '../src/client/types.ts'

const W = 'session-injection-info-0001'
const W2 = 'session-injection-info-0002'

/** 由真实解析结果组装一条留痕（字段与写入路径同源，避免手抄漂移）。 */
function entryFor(at: number, windowKey: string, stage: 'brainstorming' | 'design' = 'brainstorming'): InjectionLogEntry {
  const input = injectionLogInputFromResolved(resolveStagePrompt({ stage, difficulty: 'light', category: 'feature' }), windowKey)
  return { ...input, at }
}

function makeReq(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-000001', title: '需求', description: '', status: 'brainstorming',
    blocked: false, comments: [], version: 1,
    createdAt: 1700000000000, updatedAt: 1700000000000,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  }
}

/** 假响应：收集 status + JSON。 */
function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.payload = undefined
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}

/** 假 GET 请求（分派器只读 url/method）。 */
function fakeGetReq(url: string): any {
  const req: any = new EventEmitter()
  req.url = '/dashboard/api/reqboard' + url
  req.method = 'GET'
  return req
}

// ---------------------------------------------------------------------------
// ②③ 纯渲染：空态与转义
// ---------------------------------------------------------------------------

describe('renderInjectionInfo（只读信息块）', () => {
  it('无留痕 → 明确的空态「尚无记录」（不是空白，也不是报错）', () => {
    const html = renderInjectionInfo([])
    expect(html).toContain('尚无记录')
    expect(html).toContain('dsh-pm-injection-info')
    expect(html).not.toContain('加载失败')
  })

  it('注入 <script> 探针：输出被转义（含转义实体、无可执行标签）', () => {
    const probe = '<script>alert(1)</script>'
    const bad: InjectionInfoEntry = { ...entryFor(1000, W), routeKey: 'brainstorming/light/feature' + probe, hitLevel: probe }
    const html = renderInjectionInfo([bad])
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('&lt;script&gt;')
    expect(html).not.toMatch(/<script[\s>]/)
    // 属性位（title）同样转义，不能靠 " 逃逸
    expect(html).not.toMatch(/title="[^"]*<script/)
  })

  it('③ 字段与留痕一致：渲染文本含六字段的留痕原值', () => {
    const e = entryFor(1_700_000_000_000, W)
    const html = renderInjectionInfo([e])
    expect(html).toContain('当前节点：需求分析') // STATUS_LABELS.brainstorming
    expect(html).toContain('routeKey：' + e.routeKey)
    expect(html).toContain('命中层级：' + e.hitLevel)
    expect(html).toContain('片段数量：' + e.fragmentIds.length)
    expect(html).toContain('字符数：' + e.charCount)
    expect(html).toContain('时间：' + fmtTime(e.at))
    expect(html).toContain('data-stage="brainstorming"')
  })
})

describe('回查边界：无来源窗口不冒充本需求的注入', () => {
  it('人工建卡（无 sourceSessionId）不回查；有窗口才回查', () => {
    expect(hasInjectionWindow(undefined)).toBe(false)
    expect(hasInjectionWindow('')).toBe(false)
    expect(hasInjectionWindow(W)).toBe(true)
  })
})

describe('需求详情出现只读信息块（t11 交付点）', () => {
  it('buildReqDetail 渲染注入留痕容器，初始空态为「尚无记录」', () => {
    const html = buildReqDetail(makeReq(), [])
    expect(html).toContain('id="dsh-pm-injection-info-container"')
    expect(html).toContain('尚无记录')
  })
})

// ---------------------------------------------------------------------------
// 服务端只读接口
// ---------------------------------------------------------------------------

let dir: string
beforeEach(() => { dir = mkdtempSync(join(tmpdir(), 'pmboard-inject-')) })
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function makeLogFile(): { file: string; log: InjectionLogFile } {
  const file = join(dir, 'state/prompt-injection-log.json')
  let n = 1_700_000_000_000
  const log = new InjectionLogFile(file, () => (n += 1000))
  return { file, log }
}

describe('GET /injection-log（只读查询接口）', () => {
  it('① 返回条目与写入留痕逐字段相等（含窗口过滤）', async () => {
    const { log } = makeLogFile()
    log.record(injectionLogInputFromResolved(resolveStagePrompt({ stage: 'brainstorming', difficulty: 'light', category: 'feature' }), W))
    log.record(injectionLogInputFromResolved(resolveStagePrompt({ stage: 'design', difficulty: 'heavy', category: 'bug' }), W))
    log.record(injectionLogInputFromResolved(resolveStagePrompt({ stage: 'accepting', difficulty: 'light', category: 'feature' }), W2))
    await log.flush()

    const store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
    const handler = createReqboardHandler({ store, now: () => Date.now(), injectionLog: log })

    const res = fakeRes()
    await handler(fakeGetReq('/injection-log?window=' + W + '&k=10'), res)
    expect(res.statusCode).toBe(200)
    const data = res.payload.data as { entries: InjectionLogEntry[]; total: number; available: boolean }
    const stored = await log.readAll()
    expect(data.available).toBe(true)
    expect(data.total).toBe(2)
    // 与写入留痕逐字段一致（同一路径同一字段名，无派生）
    expect(data.entries).toEqual(stored.filter((e) => e.windowKey === W))
    expect(data.entries.every((e) => e.windowKey === W)).toBe(true)

    // 缺省 window = 全量最近 k 条
    const all = fakeRes()
    await handler(fakeGetReq('/injection-log?k=2'), all)
    expect((all.payload.data as { entries: InjectionLogEntry[] }).entries).toEqual(stored.slice(-2))
  })

  it('查询是只读的：GET 前后留痕文件字节不变', async () => {
    const { file, log } = makeLogFile()
    log.record(injectionLogInputFromResolved(resolveStagePrompt({ stage: 'implementing' }), W))
    await log.flush()
    const before = { size: statSync(file).size, text: readFileSync(file, 'utf8') }

    const store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
    const handler = createReqboardHandler({ store, now: () => Date.now(), injectionLog: log })
    const res = fakeRes()
    await handler(fakeGetReq('/injection-log'), res)
    expect(res.statusCode).toBe(200)

    const after = { size: statSync(file).size, text: readFileSync(file, 'utf8') }
    expect(after).toEqual(before)
  })

  it('k 越界 → 400（响亮拒绝，不静默截断）', async () => {
    const { log } = makeLogFile()
    const store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
    const handler = createReqboardHandler({ store, now: () => Date.now(), injectionLog: log })
    for (const bad of ['0', '201', 'abc', '1.5']) {
      const res = fakeRes()
      await handler(fakeGetReq('/injection-log?k=' + bad), res)
      expect(res.statusCode, 'k=' + bad).toBe(400)
      expect(res.payload.code).toBe('invalid_input')
    }
  })

  it('留痕端口未装配 → 空清单 available=false（不抛错，看板不因此变红）', async () => {
    const store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = fakeRes()
    await handler(fakeGetReq('/injection-log'), res)
    expect(res.statusCode).toBe(200)
    expect(res.payload.data).toEqual({ entries: [], total: 0, available: false, window: null })
  })
})
