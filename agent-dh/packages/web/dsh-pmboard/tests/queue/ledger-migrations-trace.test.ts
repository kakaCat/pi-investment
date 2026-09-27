/**
 * 台账 `migrations` 迁移留痕的**往返**回归（REQ-260927202051-f6df 验收项②）。
 *
 * 事故（2026-09-27 实测，上线后立即暴露）：
 *   迁移脚本把 `migrations: [{from:8,to:9,...}]` 写进台账（manifest 里也有留痕），
 *   但 `JsonLedgerRepository.load()` 只重建 4 个字段（schemaVersion/revision/requirements/triages），
 *   **丢掉了 `migrations`**；而 `mutate` 落盘的是整个 draft ⇒ **新进程的第一次写入就把留痕永久抹掉**。
 *   实测现场：台账顶层键 = ['requirements','revision','schemaVersion','triages']，`migrations = null`。
 *
 * 为什么必须钉住：验收项②要求「`migrations[]` 有 v8→v9 留痕」——留痕必须**留在台账里**，
 * 不能只留在 manifest 文件里（manifest 是迁移脚本的旁证，不是台账的事实）。
 *
 * 两条用例分别锁：① 有留痕 → 读进来、写出去都还在；② 无留痕 → 不许凭空造出来（防修过头）。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository } from '../../src/adapters/JsonLedgerRepository.js'

let root: string
let file: string

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'pmboard-migrations-'))
  file = join(root, 'dsh-reqboard.json')
})
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

const MIGRATION = { from: 8, to: 9, at: 1790520911425, by: 'migrate-ledger.ts' }

/** 一份最小的 v9 台账（无 tasks；可带/不带 migrations）。 */
function writeLedger(extra: Record<string, unknown> = {}): void {
  const requirement = {
    id: 'REQ-000001', title: 'x', description: '', status: 'draft', category: 'feature',
    blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  }
  writeFileSync(file, JSON.stringify({
    schemaVersion: 9, revision: 1, requirements: [requirement], triages: [], ...extra,
  }))
}

function readLedger(): Record<string, unknown> {
  return JSON.parse(readFileSync(file, 'utf8')) as Record<string, unknown>
}

describe('台账 migrations 留痕往返（v9）', () => {
  it('① load 保留留痕；且 **一次 mutate 之后**文件里仍在（事故的直接回归）', async () => {
    writeLedger({ migrations: [MIGRATION] })
    const repo = new JsonLedgerRepository({ file })
    await repo.load() // 注意：load() 是懒执行的公开 async 方法，snapshot() 不会触发读文件

    // load + 快照
    expect(repo.snapshot().migrations).toEqual([MIGRATION])

    // 一次真实写入：改需求（不加 tasks），落盘后留痕必须还在
    const requirement = repo.snapshot().requirements[0]!
    await repo.mutate('requirement-updated', (ledger) => {
      ledger.requirements[0] = { ...requirement, title: 'y' }
      return { requirements: [ledger.requirements[0]!] }
    })

    const onDisk = readLedger()
    expect(onDisk.migrations).toEqual([MIGRATION])
    expect((onDisk.requirements as { title: string }[])[0]!.title).toBe('y')
    // 迁移时代不被写坏
    expect(onDisk.schemaVersion).toBe(9)
    expect('tasks' in onDisk).toBe(false)
  })

  it('② 否命题：原本没有留痕的台账，写入后**不得**被凭空加上 migrations', async () => {
    writeLedger() // 不带 migrations
    const repo = new JsonLedgerRepository({ file })
    await repo.load()
    expect(repo.snapshot().migrations).toBeUndefined()

    const requirement = repo.snapshot().requirements[0]!
    await repo.mutate('requirement-updated', (ledger) => {
      ledger.requirements[0] = { ...requirement, title: 'z' }
      return { requirements: [ledger.requirements[0]!] }
    })

    const onDisk = readLedger()
    expect('migrations' in onDisk).toBe(false)
  })

  it('③ 畸形 migrations（非数组 / 缺 from-to）→ 丢弃而不是带进内存（防脏数据扩散）', async () => {
    writeLedger({ migrations: [{ at: 1, by: 'x' }, 'not-an-object', MIGRATION] })
    const repo = new JsonLedgerRepository({ file })
    await repo.load()
    expect(repo.snapshot().migrations).toEqual([MIGRATION])
  })
})
