/**
 * 台账 schema v9 测试（REQ-260927202051-f6df · t6 / TC-5.1~TC-5.6 / FR-6）。
 *
 * 这一卡的核心不是"删掉一个字段"，而是**读兼容从宽容翻转为拒绝**：
 * v8 台账（含 tasks）必须抛 `LEDGER_REQUIRES_MIGRATION`，绝不能静默丢弃 600+ 条任务。
 * 因此本文件的一半断言在验证"拒绝得响亮且没有副作用"（不隔离、不改写、不置 loaded）。
 */

import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { JsonLedgerRepository } from '../../src/adapters/JsonLedgerRepository.js'
import type { LedgerChange as AdapterLedgerChange } from '../../src/adapters/JsonLedgerRepository.js'
import type { LedgerChange as PortLedgerChange } from '../../src/application/ports.js'
import { REQBOARD_SCHEMA_VERSION, emptyLedger } from '../../src/shared/protocol.js'
import type { ReqboardLedger } from '../../src/shared/protocol.js'

/** 编译期断言：条件为 false 时本行编译失败。 */
type Assert<T extends true> = T

// ── TC-5.5 类型级断言：LedgerChange 无 tasks 字段 ──
export type _PortChangeNoTasks = Assert<Exclude<keyof PortLedgerChange, 'requirements' | 'triages'> extends never ? true : false>
export type _AdapterChangeNoTasks = Assert<Exclude<keyof AdapterLedgerChange, 'revision' | 'kind' | 'requirements' | 'triages'> extends never ? true : false>
// ── TC-5.1 类型级断言：ReqboardLedger 无 tasks 字段 ──
export type _LedgerNoTasks = Assert<'tasks' extends keyof ReqboardLedger ? false : true>

let root: string
let file: string

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), 'dsh-ledger-v9-'))
  file = join(root, 'dsh-reqboard.json')
})

afterEach(async () => {
  await rm(root, { recursive: true, force: true })
})

/** 一条结构可信的需求记录（load 的 isPlausibleRequirement 要求 id/title/status/version）。 */
function requirement(id: string): Record<string, unknown> {
  return { id, title: `需求 ${id}`, status: 'implementing', version: 1 }
}

/** 一条结构可信的任务卡（v8 台账形态）。 */
function v8Task(id: string, requirementId: string): Record<string, unknown> {
  return {
    id,
    requirementId,
    title: `任务 ${id}`,
    description: 'd',
    phase: 'implement',
    side: 'backend',
    scope: { apis: [], tables: [], files: [] },
    acceptance: 'a',
    context: 'c',
    dependsOn: [],
    status: 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: 1759000000000,
    updatedAt: 1759000000000,
    createdBy: { kind: 'agent' },
    updatedBy: { kind: 'agent' },
  }
}

const REQ = 'REQ-260927202051-f6df'

async function writeLedger(payload: unknown): Promise<void> {
  await writeFile(file, JSON.stringify(payload, null, 2), 'utf8')
}

describe('TC-5.1 / TC-5.2 台账 v9 契约', () => {
  it('TC-5.1 emptyLedger()：schemaVersion===9 且**没有** tasks 键', () => {
    const ledger = emptyLedger()

    expect(REQBOARD_SCHEMA_VERSION).toBe(9)
    expect(ledger.schemaVersion).toBe(9)
    expect(Object.keys(ledger).sort()).toEqual(['requirements', 'revision', 'schemaVersion', 'triages'])
    expect('tasks' in ledger).toBe(false)
  })

  it('TC-5.2 v9 台账（无 tasks）不算损坏：load 成功且 requirements 可读', async () => {
    await writeLedger({ schemaVersion: 9, revision: 7, requirements: [requirement(REQ)], triages: [] })

    const repo = new JsonLedgerRepository({ file })
    await repo.load()

    const snapshot = repo.snapshot()
    expect(snapshot.schemaVersion).toBe(9)
    expect(snapshot.revision).toBe(7)
    expect(snapshot.requirements.map((r) => r.id)).toEqual([REQ])
    expect(snapshot.migrations).toBeUndefined()
  })

  it('TC-5.2b 空 tasks 数组不触发迁移门（空数组不含会丢的任务）', async () => {
    await writeLedger({ schemaVersion: 9, revision: 1, requirements: [], tasks: [], triages: [] })

    const repo = new JsonLedgerRepository({ file })
    await expect(repo.load()).resolves.toBeUndefined()
    expect(repo.snapshot().revision).toBe(1)
  })

  it('TC-5.6 台账写入内容：落盘 JSON 无 "tasks" 键', async () => {
    await writeLedger({ schemaVersion: 9, revision: 1, requirements: [requirement(REQ)], triages: [] })
    const repo = new JsonLedgerRepository({ file })

    await repo.mutate('requirement-updated', (ledger) => {
      ledger.requirements[0]!.title = '改过的标题'
      return { requirements: [ledger.requirements[0]!] }
    })

    const text = await readFile(file, 'utf8')
    expect(text).not.toContain('"tasks"')
    const parsed = JSON.parse(text) as Record<string, unknown>
    expect('tasks' in parsed).toBe(false)
    expect(parsed.schemaVersion).toBe(9)
    expect(parsed.revision).toBe(2)
  })
})

describe('TC-5.3 加载 v8 台账（含 tasks）：拒绝且不静默丢弃', () => {
  it('抛 LEDGER_REQUIRES_MIGRATION，message 指向迁移脚本', async () => {
    await writeLedger({
      schemaVersion: 8,
      revision: 5764,
      requirements: [requirement(REQ)],
      tasks: [v8Task('t-000001', REQ), v8Task('t-000002', REQ)],
      triages: [],
    })
    const repo = new JsonLedgerRepository({ file })

    await expect(repo.load()).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })
    await expect(repo.load()).rejects.toThrow(/migrate-ledger\.ts/)
  })

  it('拒绝时**不隔离、不改写**原文件（任务还在，人工可救）', async () => {
    const payload = {
      schemaVersion: 8,
      revision: 5764,
      requirements: [requirement(REQ)],
      tasks: [v8Task('t-000001', REQ)],
      triages: [],
    }
    await writeLedger(payload)
    const repo = new JsonLedgerRepository({ file })

    await expect(repo.load()).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })

    expect(existsSync(file)).toBe(true)
    const parsed = JSON.parse(await readFile(file, 'utf8')) as Record<string, unknown>
    expect((parsed.tasks as unknown[]).length).toBe(1) // 一条都没丢
  })

  it('requireMigration 的错误信息带实测条数（可核对，不是"出错了"）', async () => {
    await writeLedger({ schemaVersion: 8, revision: 1, requirements: [], tasks: [v8Task('t-000001', REQ)], triages: [] })
    const repo = new JsonLedgerRepository({ file })

    await expect(repo.load()).rejects.toThrow(/tasks=1 条/)
  })

  it('仅自报 schemaVersion<9（无 tasks）也拒绝：版本号本身就是迁移未完成的证据', async () => {
    await writeLedger({ schemaVersion: 8, revision: 1, requirements: [], triages: [] })
    const repo = new JsonLedgerRepository({ file })

    await expect(repo.load()).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })
  })

  it('迁移完成后可重试：load 抛错不置 loaded，换成 v9 文件后同一实例即可加载', async () => {
    await writeLedger({ schemaVersion: 8, revision: 1, requirements: [], tasks: [v8Task('t-000001', REQ)], triages: [] })
    const repo = new JsonLedgerRepository({ file })

    await expect(repo.load()).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })

    await writeLedger({ schemaVersion: 9, revision: 2, requirements: [requirement(REQ)], triages: [] })
    await expect(repo.load()).resolves.toBeUndefined()
    expect(repo.snapshot().revision).toBe(2)
  })

  it('read/mutate/snapshot 路径都经 load：v8 台账下不会读到"看起来正常"的空台账', async () => {
    await writeLedger({ schemaVersion: 8, revision: 1, requirements: [requirement(REQ)], tasks: [v8Task('t-000001', REQ)], triages: [] })
    const repo = new JsonLedgerRepository({ file })

    await expect(repo.read((l) => l.revision)).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })
    await expect(repo.mutate('requirement-updated', () => ({}))).rejects.toMatchObject({ code: 'LEDGER_REQUIRES_MIGRATION' })
  })
})

describe('TC-5.4 写通道去 tasks', () => {
  it('repo.mutate 返回体的 changed 只有 requirements / triages 两个键', async () => {
    await writeLedger({ schemaVersion: 9, revision: 1, requirements: [requirement(REQ)], triages: [] })
    const repo = new JsonLedgerRepository({ file })

    const result = await repo.mutate('requirement-updated', (ledger) => {
      ledger.requirements[0]!.title = 't2'
      return { requirements: [ledger.requirements[0]!] }
    })

    expect(Object.keys(result.changed).sort()).toEqual(['requirements', 'triages'])
    expect('tasks' in result.changed).toBe(false)
    expect(Object.keys(result.ledger).sort()).toEqual(['migrations', 'requirements', 'revision', 'schemaVersion', 'triages'].filter((k) => k !== 'migrations'))
  })

  it('无变更时返回空变更集（仍是两键）', async () => {
    await writeLedger({ schemaVersion: 9, revision: 3, requirements: [], triages: [] })
    const repo = new JsonLedgerRepository({ file })

    const result = await repo.mutate('requirement-updated', () => undefined)

    expect(Object.keys(result.changed).sort()).toEqual(['requirements', 'triages'])
    expect(result.revision).toBe(3)
  })

  it('订阅者收到的 LedgerChange 无 tasks 字段', async () => {
    await writeLedger({ schemaVersion: 9, revision: 1, requirements: [requirement(REQ)], triages: [] })
    const repo = new JsonLedgerRepository({ file })
    const seen: AdapterLedgerChange[] = []
    repo.subscribe((change) => seen.push(change))

    await repo.mutate('requirement-updated', (ledger) => {
      ledger.requirements[0]!.title = 't3'
      return { requirements: [ledger.requirements[0]!] }
    })

    expect(seen).toHaveLength(1)
    expect('tasks' in seen[0]!).toBe(false)
  })

  it('replaceAll（迁移专用）通知的变更集也无 tasks', async () => {
    await writeLedger({ schemaVersion: 9, revision: 1, requirements: [], triages: [] })
    const repo = new JsonLedgerRepository({ file })
    const seen: AdapterLedgerChange[] = []
    repo.subscribe((change) => seen.push(change))
    const next: ReqboardLedger = {
      schemaVersion: 9,
      revision: 9,
      requirements: [],
      triages: [],
      migrations: [{ from: 8, to: 9, at: 1759000000000, by: 'migrate-ledger.ts' }],
    }

    await repo.replaceAll('migration', next)

    expect(seen).toHaveLength(1)
    expect('tasks' in seen[0]!).toBe(false)
    expect(repo.snapshot().migrations).toHaveLength(1)
  })
})

describe('t6 的连带契约（删除而非静默失效）', () => {
  it('JsonLedgerRepository 不再提供 getTask（任务请走 TaskStore）', () => {
    const repo = new JsonLedgerRepository({ file })
    expect((repo as unknown as Record<string, unknown>).getTask).toBeUndefined()
  })

  it('台账文件里从不写出 tasks 键（连空数组都不写）', async () => {
    const repo = new JsonLedgerRepository({ file })
    await repo.mutate('requirement-created', (ledger) => {
      ledger.requirements.push(requirement(REQ) as never)
      return { requirements: [ledger.requirements[0]!] }
    })

    const text = await readFile(file, 'utf8')
    expect(text).not.toContain('tasks')
  })
})
