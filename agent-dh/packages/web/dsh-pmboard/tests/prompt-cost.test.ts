import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import {
  injectionWindowsOf, summarizeInjections, summarizeSystemPrompt, unavailableSystemPromptCost,
} from '../src/application/internal/prompt-cost.js'
import { estimateTokensFromChars, type ReqboardLedger } from '../src/shared/protocol.js'

describe('REQ-a33899 t5 · 固定系统提示词折算', () => {
  it('逐段 chars = 文本长度；每回合 = sections + contexts + tools', () => {
    const assembly = {
      sections: [{ name: 'genome:rules', text: 'R-001'.repeat(4) }, { name: 'empty', text: '' }],
      contexts: [{ name: 'sandbox', text: 'abc' }],
      tools: [{ name: 'read' }, { name: 'write' }],
    }
    const cost = summarizeSystemPrompt(assembly, 0)
    expect(cost.source).toBe('assembled')
    expect(cost.sections).toHaveLength(1) // 空段不产生成本
    expect(cost.sections[0]!.name).toBe('genome:rules')
    expect(cost.sections[0]!.chars).toBe(20)
    expect(cost.sections[0]!.text).toBe('R-001'.repeat(4))
    expect(cost.contexts[0]!.chars).toBe(3)
    const toolsChars = JSON.stringify(assembly.tools).length
    expect(cost.toolsChars).toBe(toolsChars)
    expect(cost.perTurnChars).toBe(20 + 3 + toolsChars)
    expect(cost.perTurnEstTokens).toBe(estimateTokensFromChars(cost.perTurnChars))
  })

  it('回合数不可得（0）→ 不给累计（缺失 ≠ 0）', () => {
    const cost = summarizeSystemPrompt({ sections: [{ name: 'a', text: '12345' }] }, 0)
    expect(cost.cumulativeEstTokens).toBeUndefined()
    expect(cost.turns).toBe(0)
  })

  it('给了回合数 → 累计 = 每回合 × 回合', () => {
    const cost = summarizeSystemPrompt({ sections: [{ name: 'a', text: '12345678' }] }, 3)
    expect(cost.cumulativeEstTokens).toBe(cost.perTurnEstTokens * 3)
  })

  it('装配结果非法/不可得 → unavailable（全 0、不猜）', () => {
    expect(summarizeSystemPrompt(undefined, 5).source).toBe('unavailable')
    expect(summarizeSystemPrompt({}, 0).source).toBe('assembled')
    expect(unavailableSystemPromptCost()).toMatchObject({ source: 'unavailable', perTurnChars: 0, turns: 0 })
  })
})

describe('REQ-a33899 t5 · 注入提示词折算', () => {
  const entry = (over: any = {}) => ({
    at: 100, windowKey: 'w-abc12345', stage: 'brainstorming', routeKey: 'brainstorming/light/feature',
    fragmentIds: ['f1'], charCount: 400, ...over,
  })

  it('只统计窗口匹配的留痕；chars = 各条 charCount 之和', () => {
    const windows = injectionWindowsOf(['session-abc12345-0000'])
    expect(windows.has('w-abc12345')).toBe(true)
    const cost = summarizeInjections([
      entry(),
      entry({ at: 200, stage: 'design', charCount: 600 }),
      entry({ windowKey: 'w-other999', charCount: 9999 }),
    ], windows)
    expect(cost.count).toBe(2)
    expect(cost.chars).toBe(1000)
    expect(cost.estTokens).toBe(estimateTokensFromChars(1000))
    expect(cost.byStage.map(s => s.name).sort()).toEqual(['brainstorming', 'design'])
  })

  it('没有可匹配窗口 → 不归因（空，不张冠李戴）', () => {
    const cost = summarizeInjections([entry()], new Set())
    expect(cost.count).toBe(0)
    expect(cost.chars).toBe(0)
  })
})

function seededLedger(): ReqboardLedger {
  return {
    schemaVersion: 7, revision: 1,
    requirements: [{
      id: 'REQ-abc123', title: 'T', description: 'd', category: 'feature', status: 'brainstorming',
      blocked: false, sourceSessionId: 'session-abc12345-0000', comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    }],
    tasks: [], triages: [],
  }
}

let dir: string
let store: ReqboardStore
beforeEach(async () => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-pcost-'))
  store = new ReqboardStore({ file: join(dir, 'l.json') })
  await store.replaceAll('seed', seededLedger())
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.payload = undefined
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}
async function get(handler: any, url: string) {
  const req = new EventEmitter() as any
  req.url = '/dashboard/api/reqboard' + url; req.method = 'GET'
  req[Symbol.asyncIterator] = async function* () { /* GET 无体 */ }
  const res = fakeRes()
  await handler(req, res)
  return res
}

describe('REQ-a33899 t5 · 接口接线', () => {
  it('无 systemPrompt 服务 → systemPrompt.source=unavailable（不猜数字）', async () => {
    const handler = createReqboardHandler({ store, now: () => Date.now() })
    const res = await get(handler, '/requirements/REQ-abc123/token')
    expect(res.statusCode).toBe(200)
    expect(res.payload.data.systemPrompt.source).toBe('unavailable')
    expect(res.payload.data.injections.count).toBe(0)
  })

  it('有 systemPrompt + 注入留痕端口 → 两块成本就位', async () => {
    const handler = createReqboardHandler({
      store,
      now: () => Date.now(),
      systemPrompt: () => ({ assemble: async () => ({ sections: [{ name: 'genome:rules', text: 'abcd' }], contexts: [], tools: [] }) }),
      injectionLog: {
        readAll: async () => ([{
          at: 1, windowKey: 'w-abc12345', stage: 'brainstorming', difficulty: 'light', category: 'feature',
          routeKey: 'brainstorming/light/feature', hitLevel: 'exact', fragmentIds: ['f1'], charCount: 800, trimmed: [],
        }]),
      },
    })
    const res = await get(handler, '/requirements/REQ-abc123/token')
    expect(res.payload.data.systemPrompt.source).toBe('assembled')
    expect(res.payload.data.systemPrompt.perTurnChars).toBe(4)
    expect(res.payload.data.injections.count).toBe(1)
    expect(res.payload.data.injections.chars).toBe(800)
  })
})
