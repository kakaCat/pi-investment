/**
 * QueueRepository 文件层测试（REQ-260927202051-f6df · t4 / TC-3.1~TC-3.6 / FR-1, FR-4）。
 *
 * 全部在 **临时目录** 里跑（`mkdtemp`），不碰真实工作区——队列文件是任务唯一存储，
 * 测试若误写工作区就等同于污染真实数据。
 *
 * ⚠️ 路径口径：验收锚点写 `npx vitest run src/repositories/QueueRepository.test.ts`，
 * 但本仓 vitest include 是 `tests/**\/*.test.ts`（`src/` 下的测试文件不会被收集），
 * 故测试落 `tests/queue/QueueRepository.test.ts`，命令相应调整。已于 t2 向 Lead 报备获批。
 */

import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  QUEUE_ERROR,
  QUEUE_FILENAME,
  JsonQueueRepository,
  queueRelativePath,
} from '../../src/repositories/QueueRepository.js'
import { REQ, clone, mkTask, queueOf } from './fixtures.js'

let root: string
let repo: JsonQueueRepository
let warnings: string[]

beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), 'dsh-queue-repo-'))
  warnings = []
  repo = new JsonQueueRepository({ workspaceRoot: root, onWarn: (message) => warnings.push(message) })
})

afterEach(async () => {
  await rm(root, { recursive: true, force: true })
})

/** 该需求队列文件所在目录。 */
const dirOf = (reqId = REQ): string => join(root, 'docs', 'requirements', reqId)

async function filesIn(dir: string): Promise<string[]> {
  try {
    return await readdir(dir)
  } catch {
    return []
  }
}

describe('QueueRepository 写（TC-3.1 / TC-3.4 / TC-3.6）', () => {
  it('TC-3.1 save 合法队列：文件存在、jq 解析成功、2 空格缩进', async () => {
    const file = queueOf(REQ, [mkTask('t-000001'), mkTask('t-000002', { dependsOn: ['t-000001'] })])

    await repo.save(REQ, file)

    const path = repo.pathOf(REQ)
    expect(existsSync(path)).toBe(true)
    expect(path).toBe(join(dirOf(), QUEUE_FILENAME))
    // 相对路径口径：docs/requirements/<REQ>/queue.json
    expect(repo.relativePathOf(REQ)).toBe(queueRelativePath(REQ))
    expect(queueRelativePath(REQ)).toBe(`docs/requirements/${REQ}/queue.json`)

    // jq . 解析成功（真实调用，不是"JSON.parse 过了就算"）
    const jqOut = execFileSync('jq', ['.requirement_id', path], { encoding: 'utf8' }).trim()
    expect(jqOut).toBe(`"${REQ}"`)

    // 2 空格缩进（便于 diff 与人工查看）
    const text = await readFile(path, 'utf8')
    expect(text).toContain('\n  "requirement_id"')
  })

  it('TC-3.1b save → load 往返：字段一个不少', async () => {
    const file = queueOf(REQ, [mkTask('t-000001'), mkTask('t-000002', { dependsOn: ['t-000001'] })])

    await repo.save(REQ, file)
    const loaded = await repo.load(REQ)

    expect(loaded).toEqual(file)
  })

  it('TC-3.4 save 校验失败：抛 QUEUE_VALIDATION_FAILED 且**文件不存在**、目录也不被创建', async () => {
    const invalid = clone(queueOf(REQ, [mkTask('t-000001')]))
    delete (invalid as unknown as Record<string, unknown>).schemaVersion
    invalid.ready = ['t-000001', 't-not-exist']

    await expect(repo.save(REQ, invalid)).rejects.toMatchObject({ code: QUEUE_ERROR.VALIDATION_FAILED })

    expect(existsSync(repo.pathOf(REQ))).toBe(false)
    // 连 mkdir 都不能先做（校验必须先于任何文件系统动作）
    expect(existsSync(dirOf())).toBe(false)
  })

  it('TC-3.4b save 的 requirement_id 与写入目标不一致：拒绝落盘（防串档）', async () => {
    const file = queueOf('REQ-260927000000-dead', [mkTask('t-000001', { requirementId: 'REQ-260927000000-dead' })])

    await expect(repo.save(REQ, file)).rejects.toMatchObject({ code: QUEUE_ERROR.VALIDATION_FAILED })
    expect(existsSync(repo.pathOf(REQ))).toBe(false)
    expect(existsSync(repo.pathOf('REQ-260927000000-dead'))).toBe(false)
  })

  it('TC-3.6 save 后目录内无临时文件残留', async () => {
    await repo.save(REQ, queueOf(REQ, [mkTask('t-000001')]))
    await repo.save(REQ, queueOf(REQ, [mkTask('t-000001'), mkTask('t-000002')]))

    const names = await filesIn(dirOf())
    expect(names).toContain(QUEUE_FILENAME)
    expect(names.filter((n) => n.includes('.tmp'))).toEqual([])
    expect(names).toEqual([QUEUE_FILENAME])
  })

  it('save 会创建缺失的需求目录（persistAtomic 的 mkdir recursive）', async () => {
    expect(existsSync(dirOf())).toBe(false)

    await repo.save(REQ, queueOf(REQ, [mkTask('t-000001')]))

    expect(existsSync(dirOf())).toBe(true)
  })
})

describe('QueueRepository 读（TC-3.2 / TC-3.3）', () => {
  it('TC-3.2 load 不存在的需求：返回 undefined 且不抛错、不创建目录', async () => {
    let loaded: unknown
    await expect(async () => {
      loaded = await repo.load('REQ-260927000000-none')
    }).not.toThrow()

    expect(loaded).toBeUndefined()
    expect(existsSync(dirOf('REQ-260927000000-none'))).toBe(false)
  })

  it('TC-3.3 load 损坏 JSON：返回 undefined + 产生 .corrupt-<ts> 隔离文件 + 告警', async () => {
    await mkdir(dirOf(), { recursive: true })
    const path = repo.pathOf(REQ)
    await writeFile(path, '{ "not": "json"', 'utf8')

    const loaded = await repo.load(REQ)

    expect(loaded).toBeUndefined()
    expect(existsSync(path)).toBe(false) // 原件已挪走
    const names = await filesIn(dirOf())
    const quarantined = names.filter((n) => n.startsWith(`${QUEUE_FILENAME}.corrupt-`))
    expect(quarantined).toHaveLength(1)
    expect(warnings.some((w) => w.includes('隔离'))).toBe(true)
  })

  it('load 校验失败：返回 undefined **但不隔离**（内容不合规 ≠ 文件损坏），原件仍在', async () => {
    await mkdir(dirOf(), { recursive: true })
    const path = repo.pathOf(REQ)
    const invalid = clone(queueOf(REQ, [mkTask('t-000001')]))
    invalid.ready = ['t-not-exist']
    await writeFile(path, JSON.stringify(invalid, null, 2), 'utf8')

    const loaded = await repo.load(REQ)

    expect(loaded).toBeUndefined()
    expect(existsSync(path)).toBe(true) // 不隔离：用户还能手工修
    expect((await filesIn(dirOf())).filter((n) => n.includes('.corrupt-'))).toEqual([])
    expect(warnings.some((w) => w.includes('未通过校验'))).toBe(true)
  })

  it('load 合法队列：返回与写入一致的对象（含派生字段）', async () => {
    const file = queueOf(REQ, [
      mkTask('t-000001', { status: 'done' }),
      mkTask('t-000002', { dependsOn: ['t-000001'] }),
    ])
    await repo.save(REQ, file)

    const loaded = await repo.load(REQ)

    expect(loaded).not.toBeUndefined()
    expect(loaded!.layers).toEqual([{ layer: 0, tasks: ['t-000001'] }, { layer: 1, tasks: ['t-000002'] }])
    expect(loaded!.ready).toEqual(['t-000002'])
    expect(loaded!.edges).toEqual([{ from: 't-000001', to: 't-000002' }])
  })
})

describe('QueueRepository 并发与原子性（TC-3.5）', () => {
  it('TC-3.5 并发两次 save：最终文件是**完整** JSON（不是半截），且等于其中一次的内容', async () => {
    const a = queueOf(REQ, [mkTask('t-000001')])
    const b = queueOf(REQ, [mkTask('t-000001'), mkTask('t-000002'), mkTask('t-000003', { dependsOn: ['t-000002'] })])

    await Promise.all([repo.save(REQ, a), repo.save(REQ, b)])

    const text = await readFile(repo.pathOf(REQ), 'utf8')
    const parsed = JSON.parse(text) as { tasks: unknown[] } // 半截 JSON 会在这里抛
    expect([a.tasks.length, b.tasks.length]).toContain(parsed.tasks.length)

    const loaded = await repo.load(REQ)
    expect(loaded).not.toBeUndefined()
    expect(JSON.stringify(loaded)).toBe(JSON.stringify(parsed))
  })

  it('TC-3.5b 连续 10 次 save 后仍是单文件、无临时残留、内容可解析', async () => {
    for (let i = 1; i <= 10; i += 1) {
      const tasks = Array.from({ length: i }, (_, k) => mkTask(`t-10000${k}`))
      await repo.save(REQ, queueOf(REQ, tasks))
    }

    expect(await filesIn(dirOf())).toEqual([QUEUE_FILENAME])
    const parsed = JSON.parse(readFileSync(repo.pathOf(REQ), 'utf8')) as { tasks: unknown[] }
    expect(parsed.tasks).toHaveLength(10)
  })
})

describe('QueueRepository 契约（复用 persistAtomic，不自造原子写）', () => {
  it('源码复用 adapters 的 persistAtomic；本文件不出现第二套 temp+rename 实现', () => {
    const source = readFileSync(new URL('../../src/repositories/QueueRepository.ts', import.meta.url), 'utf8')

    expect(source).toMatch(/import \{ persistAtomic \} from '\.\.\/adapters\/JsonLedgerRepository\.js'/)
    expect(source).toContain('persistAtomic(')
    // 自造原子写的指纹：临时文件名后缀 / 文件句柄 fsync
    expect(source).not.toContain('.tmp')
    expect(source).not.toContain('fh.sync')
    expect(source).not.toContain('await open(')
  })

  it('requirementDirOf 可注入（迁移与测试把队列写到别处）', async () => {
    const elsewhere = await mkdtemp(join(tmpdir(), 'dsh-queue-elsewhere-'))
    try {
      const custom = new JsonQueueRepository({ workspaceRoot: root, requirementDirOf: () => elsewhere })
      await custom.save(REQ, queueOf(REQ, [mkTask('t-000001')]))

      expect(existsSync(join(elsewhere, QUEUE_FILENAME))).toBe(true)
      expect(existsSync(repo.pathOf(REQ))).toBe(false)
      // 规范相对路径不受注入影响（它描述的是"规范位置"，不是实际落点）
      expect(custom.relativePathOf(REQ)).toBe(queueRelativePath(REQ))
    } finally {
      await rm(elsewhere, { recursive: true, force: true })
    }
  })
})
