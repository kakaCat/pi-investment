/**
 * 注入留痕单测（REQ-422af1 t6，INV-6）。
 *
 * 覆盖：十字段完整且值与写入一致、ring buffer 有界（N+100 → N）、缺文件读取返回空数组
 * 且不抛、删除留痕文件后功能正常（无硬依赖）、只读查询、原子写不留临时文件、
 * 以及两个注入点确实在注入后调用记录。
 */
import { describe, it, expect } from 'vitest'
import { mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import {
  INJECTION_LOG_CAP,
  INJECTION_LOG_FIELDS,
  appendToInjectionLog,
  isInjectionLogEntry,
  queryInjectionLog,
  injectionLogInputFromResolved,
  type InjectionLogEntry,
  type InjectionLogInput,
} from '../src/application/internal/injection-log.js'
import { InjectionLogFile } from '../src/adapters/InjectionLogFile.js'
import { boundSectionText } from '../src/application/internal/capture-section.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'
import { emptyLedger, type ReqboardLedger, type RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-log-test-0001'

function entry(over: Partial<InjectionLogEntry> = {}): InjectionLogEntry {
  return {
    at: 1000, windowKey: W, stage: 'brainstorming', difficulty: 'light', category: 'feature',
    routeKey: 'brainstorming/light/feature', hitLevel: 'exact', fragmentIds: ['a'], charCount: 1, trimmed: [],
    ...over,
  }
}

function makeDir(): string {
  return mkdtempSync(join(tmpdir(), 'dsh-injlog-'))
}

describe('纯逻辑：ring buffer / 查询 / 校验', () => {
  it('十字段字段名固定（单点，防漂移）', () => {
    expect([...INJECTION_LOG_FIELDS]).toEqual([
      'at', 'windowKey', 'stage', 'difficulty', 'category', 'routeKey', 'hitLevel', 'fragmentIds', 'charCount', 'trimmed',
    ])
  })

  it('ring buffer 有界：写入 N+100 条只保留最近 N 条', () => {
    let all: InjectionLogEntry[] = []
    for (let i = 0; i < INJECTION_LOG_CAP + 100; i++) all = appendToInjectionLog(all, entry({ at: i }))
    expect(all.length).toBe(INJECTION_LOG_CAP)
    expect(all[0]!.at).toBe(100)
    expect(all[all.length - 1]!.at).toBe(INJECTION_LOG_CAP + 99)
  })

  it('cap 非法 → 响亮抛错（不静默截断）', () => {
    expect(() => appendToInjectionLog([], entry(), 0)).toThrow(/cap/)
  })

  it('只读查询返回最近 k 条（保持写入顺序）', () => {
    const all = [entry({ at: 1 }), entry({ at: 2 }), entry({ at: 3 })]
    expect(queryInjectionLog(all, 2).map((e) => e.at)).toEqual([2, 3])
    expect(queryInjectionLog(all, 10).length).toBe(3)
  })

  it('isInjectionLogEntry 拒绝残缺记录', () => {
    expect(isInjectionLogEntry(entry())).toBe(true)
    expect(isInjectionLogEntry({ ...entry(), charCount: undefined })).toBe(false)
    expect(isInjectionLogEntry({ ...entry(), fragmentIds: 'x' })).toBe(false)
  })

  it('injectionLogInputFromResolved 从 routeKey 拆出 stage/difficulty/category', () => {
    const resolved = resolveStagePrompt({ stage: 'design', difficulty: 'heavy', category: 'bug' })
    const input = injectionLogInputFromResolved(resolved, W)
    expect(input.stage).toBe('design')
    expect(input.difficulty).toBe('heavy')
    expect(input.category).toBe('bug')
    expect(input.routeKey).toBe('design/heavy/bug')
    expect(input.charCount).toBe(resolved.charCount)
    expect(input.fragmentIds).toEqual([...resolved.fragmentIds])
    expect(['exact', '②', '③', '④', '⑤']).toContain(input.hitLevel)
  })
})

describe('文件适配器：写入 / 读回 / 有界 / 缺文件', () => {
  it('记录十项且值与写入一致', async () => {
    const dir = makeDir()
    const file = join(dir, 'state/prompt-injection-log.json')
    const log = new InjectionLogFile(file, () => 777)
    const input: InjectionLogInput = injectionLogInputFromResolved(
      resolveStagePrompt({ stage: 'brainstorming', difficulty: 'light', category: 'feature' }), W,
    )
    log.record(input)
    await log.flush()
    const all = await log.readAll()
    expect(all.length).toBe(1)
    const got = all[0]!
    expect(Object.keys(got).sort()).toEqual([...INJECTION_LOG_FIELDS].sort())
    expect(got.at).toBe(777)
    expect(got.windowKey).toBe(W)
    expect(got.routeKey).toBe('brainstorming/light/feature')
    expect(got.stage).toBe('brainstorming')
    expect(got.difficulty).toBe('light')
    expect(got.category).toBe('feature')
    expect(got.charCount).toBe(input.charCount)
    expect(got.fragmentIds).toEqual(input.fragmentIds)
    expect(got.trimmed).toEqual([])
    rmSync(dir, { recursive: true, force: true })
  })

  it('ring buffer 有界：文件条数 = N（写入 N+100）', async () => {
    const dir = makeDir()
    const file = join(dir, 'prompt-injection-log.json')
    const log = new InjectionLogFile(file, (() => { let n = 0; return () => n++ })())
    const input = injectionLogInputFromResolved(resolveStagePrompt({ stage: 'accepting' }), W)
    for (let i = 0; i < INJECTION_LOG_CAP + 100; i++) log.record(input)
    await log.flush()
    const onDisk = JSON.parse(readFileSync(file, 'utf8')) as unknown[]
    expect(onDisk.length).toBe(INJECTION_LOG_CAP)
    rmSync(dir, { recursive: true, force: true })
  }, 60_000)

  it('缺文件：读取返回空数组且不抛错', async () => {
    const dir = makeDir()
    const log = new InjectionLogFile(join(dir, 'none.json'), () => 1)
    await expect(log.readAll()).resolves.toEqual([])
    rmSync(dir, { recursive: true, force: true })
  })

  it('删除留痕文件后功能仍正常（无硬依赖）', async () => {
    const dir = makeDir()
    const file = join(dir, 'prompt-injection-log.json')
    const first = new InjectionLogFile(file, () => 1)
    first.record(injectionLogInputFromResolved(resolveStagePrompt({ stage: 'design' }), W))
    await first.flush()
    rmSync(file, { force: true })
    const second = new InjectionLogFile(file, () => 2)
    await expect(second.readAll()).resolves.toEqual([])
    second.record(injectionLogInputFromResolved(resolveStagePrompt({ stage: 'design' }), W))
    await second.flush()
    expect((await second.readAll()).length).toBe(1)
    rmSync(dir, { recursive: true, force: true })
  })

  it('原子写：不残留临时文件；queryLatest 返回最近 k 条', async () => {
    const dir = makeDir()
    const file = join(dir, 'prompt-injection-log.json')
    const log = new InjectionLogFile(file, (() => { let n = 0; return () => ++n })())
    for (let i = 0; i < 3; i++) log.record(injectionLogInputFromResolved(resolveStagePrompt({ stage: 'archived' }), W))
    await log.flush()
    expect(readdirSync(dir).filter((f) => f.endsWith('.tmp'))).toEqual([])
    expect((await log.queryLatest(2)).map((e) => e.at)).toEqual([2, 3])
    rmSync(dir, { recursive: true, force: true })
  })
})

describe('注入点确实在注入后留痕', () => {
  it('boundSectionText（capture-section）注入阶段提示词时调用 record', () => {
    const req = {
      id: 'REQ-000001', title: 't', description: '', status: 'brainstorming', blocked: false,
      version: 1, createdAt: 1, updatedAt: 1, sourceSessionId: W, category: 'feature',
    } as RequirementRecord
    const ledger: ReqboardLedger = { ...emptyLedger(), requirements: [req] }
    const recorded: InjectionLogInput[] = []
    const text = boundSectionText(ledger, { agent: { id: W } }, { record: (e) => recorded.push(e) })
    expect(text).toContain('REQ-000001')
    expect(recorded.length).toBe(1)
    expect(recorded[0]!.stage).toBe('brainstorming')
    expect(recorded[0]!.routeKey).toBe('brainstorming/light/feature')
    expect(recorded[0]!.charCount).toBeGreaterThan(0)
  })

  it('跳过阶段不注入 → 不留痕（bug 分类跳过 brainstorming）', () => {
    const req = {
      id: 'REQ-000002', title: 't', description: '', status: 'brainstorming', blocked: false,
      version: 1, createdAt: 1, updatedAt: 1, sourceSessionId: W, category: 'bug',
    } as RequirementRecord
    const ledger: ReqboardLedger = { ...emptyLedger(), requirements: [req] }
    const recorded: InjectionLogInput[] = []
    boundSectionText(ledger, { agent: { id: W } }, { record: (e) => recorded.push(e) })
    expect(recorded).toEqual([])
  })
})
