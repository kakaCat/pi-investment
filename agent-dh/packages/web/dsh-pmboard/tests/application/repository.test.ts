/**
 * L2 适配器测试 · JsonLedgerRepository / FileDocRepository / SystemClock / RandomIdFactory
 * （REQ-47939a t5）。
 *
 * 用**临时目录跑真实现**（非 mock）：台账串行写、原子写（temp+rename）、损坏隔离、
 * 深冻快照、replaceAll 备份；文档仓储读写/列目录/路径解析。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, writeFileSync, readFileSync, readdirSync, existsSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository, persistAtomic } from '../../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../../src/adapters/FileDocRepository.js'
import { SystemClock } from '../../src/adapters/SystemClock.js'
import { RandomIdFactory } from '../../src/adapters/RandomIdFactory.js'
import type { RequirementRecord } from '../../src/shared/protocol.js'

let dir: string
let file: string
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-repo-'))
  file = join(dir, 'ledger.json')
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function req(id: string): RequirementRecord {
  return {
    id, title: '需求', description: '', status: 'draft', blocked: false,
    comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [],
  } as RequirementRecord
}

describe('JsonLedgerRepository：加载 / 写 / 订阅', () => {
  it('缺文件 → 空台账（schemaVersion=7, revision=0），不抛', async () => {
    const repo = new JsonLedgerRepository({ file })
    await repo.load()
    const snap = repo.snapshot()
    expect(snap.requirements).toEqual([])
    expect(snap.revision).toBe(0)
    // C1：契约版本常量 4 → 5 → 6 → 7（常量必须与迁移后文件一致，否则写盘会把版本回退）
    expect(snap.schemaVersion).toBe(7)
  })

  it('mutate：写盘 + bump revision + 通知订阅者；返回的 changed 含触动的记录', async () => {
    const repo = new JsonLedgerRepository({ file })
    const seen: number[] = []
    repo.subscribe((c) => seen.push(c.revision))
    const out = await repo.mutate('requirement-created', (l) => { l.requirements.push(req('REQ-abc123')); return { requirements: [l.requirements[0]] } })
    expect(out.revision).toBe(1)
    expect(out.changed.requirements).toHaveLength(1)
    expect(seen).toEqual([1])
    const re = new JsonLedgerRepository({ file })
    await re.load()
    expect(re.snapshot().requirements.map(r => r.id)).toEqual(['REQ-abc123'])
    expect(re.snapshot().revision).toBe(1)
  })

  it('mutate 回调返回 undefined → 不写盘、不 bump revision', async () => {
    const repo = new JsonLedgerRepository({ file })
    await repo.mutate('requirement-created', (l) => { l.requirements.push(req('REQ-abc123')); return { requirements: [l.requirements[0]] } })
    const out = await repo.mutate('noop', () => undefined)
    expect(out.changed.requirements).toEqual([])
    expect(repo.snapshot().revision).toBe(1)
  })

  it('快照深冻（改它抛错，不能绕过持久化路径）', async () => {
    const repo = new JsonLedgerRepository({ file })
    await repo.mutate('requirement-created', (l) => { l.requirements.push(req('REQ-abc123')); return { requirements: [l.requirements[0]] } })
    expect(Object.isFrozen(repo.snapshot())).toBe(true)
    expect(() => { (repo.snapshot().requirements as RequirementRecord[]).push(req('REQ-ffffff')) }).toThrow()
  })

  it('损坏台账被隔离（改名挪走）且 load 不抛', async () => {
    writeFileSync(file, '{ this is not json', 'utf8')
    const repo = new JsonLedgerRepository({ file })
    await expect(repo.load()).resolves.toBeUndefined()
    expect(repo.snapshot().requirements).toEqual([])
    expect(existsSync(file)).toBe(false)
    const quarantined = readdirSync(dir).filter(n => n.startsWith('ledger.json.corrupt-'))
    expect(quarantined).toHaveLength(1)
  })

  it('replaceAll：备份 + 整体替换 + 通知；重开可读到新台账', async () => {
    const repo = new JsonLedgerRepository({ file })
    await repo.mutate('requirement-created', (l) => { l.requirements.push(req('REQ-abc123')); return { requirements: [l.requirements[0]] } })
    const seen: string[] = []
    repo.subscribe((c) => seen.push(c.kind))
    const next = { schemaVersion: 5, revision: 870, requirements: [req('REQ-aaaaaa')], tasks: [], triages: [] }
    await repo.replaceAll('migration', next as never)
    expect(seen).toEqual(['ledger-replaced'])
    expect(repo.snapshot().schemaVersion).toBe(5)
    expect(repo.snapshot().requirements.map(r => r.id)).toEqual(['REQ-aaaaaa'])
    expect(readdirSync(dir).some(n => n.startsWith('ledger.json.backup-'))).toBe(true)
    const re = new JsonLedgerRepository({ file })
    await re.load()
    expect(re.snapshot().revision).toBe(870)
  })

  it('read：串行队列内读（先入队的读先执行；mutate 之后的读读到新状态）', async () => {
    const repo = new JsonLedgerRepository({ file })
    const before = repo.read(l => l.requirements.length)
    await repo.mutate('requirement-created', (l) => { l.requirements.push(req('REQ-abc123')); return { requirements: [l.requirements[0]] } })
    expect(await before).toBe(0) // FIFO：读在 mutate 之前入队
    expect(await repo.read(l => l.requirements.length)).toBe(1)
  })
})

describe('原子写（temp + rename）', () => {
  it('persistAtomic：写临时文件后 rename，目标内容完整且无 .tmp 残留', async () => {
    const target = join(dir, 'out.json')
    await persistAtomic(target, '{"ok":true}')
    expect(readFileSync(target, 'utf8')).toBe('{"ok":true}')
    expect(readdirSync(dir).filter(n => n.endsWith('.tmp'))).toEqual([])
  })

  it('persistAtomic：自动创建父目录', async () => {
    const target = join(dir, 'a', 'b', 'out.json')
    await persistAtomic(target, 'x')
    expect(readFileSync(target, 'utf8')).toBe('x')
  })

  it('故障注入：rename 失败时目标不被污染，且能观察到临时文件（证明先写临时再 rename）', async () => {
    const target = join(dir, 'occupied')
    mkdirSync(target) // 目标已是目录 → rename(file, dir) 失败
    await expect(persistAtomic(target, 'x')).rejects.toThrow()
    expect(readdirSync(target)).toEqual([]) // 目标目录未被写入
    const temps = readdirSync(dir).filter(n => n.endsWith('.tmp'))
    expect(temps.length).toBe(1) // 临时文件已生成（未 rename 成功 → 残留）
  })
})

describe('FileDocRepository', () => {
  it('write/read/exists/list/resolve/workspaceRoot', async () => {
    const docs = new FileDocRepository({ workspaceRoot: dir })
    expect(docs.workspaceRoot()).toBe(dir)
    expect(docs.resolve('a/b.md')).toBe(join(dir, 'a/b.md'))
    expect(docs.exists('a/b.md')).toBe(false)
    await docs.write('a/b.md', 'hello')
    expect(docs.exists('a/b.md')).toBe(true)
    expect(await docs.read('a/b.md')).toBe('hello')
    expect(docs.list('a').map(e => e.name)).toEqual(['b.md'])
    expect(docs.list('a')[0].isFile).toBe(true)
    expect(docs.list('missing')).toEqual([])
  })
})

describe('SystemClock / RandomIdFactory', () => {
  it('SystemClock.now() 约等于当前时间', () => {
    const before = Date.now()
    const now = new SystemClock().now()
    expect(now).toBeGreaterThanOrEqual(before)
    expect(now).toBeLessThanOrEqual(Date.now())
  })

  it('RandomIdFactory：前缀与 6 位 hex 格式（与 protocol new*Id 同形）', () => {
    const ids = new RandomIdFactory()
    for (let i = 0; i < 20; i++) {
      expect(ids.requirement()).toMatch(/^REQ-[0-9a-f]{6}$/)
      expect(ids.task()).toMatch(/^t-[0-9a-f]{6}$/)
      expect(ids.execution()).toMatch(/^e-[0-9a-f]{6}$/)
      expect(ids.comment()).toMatch(/^c-[0-9a-f]{6}$/)
    }
  })
})
