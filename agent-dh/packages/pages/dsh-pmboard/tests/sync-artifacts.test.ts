/**
 * 需求目录产物自动发现单测（REQ-2e9473 t11/W4，事故 E 修复）。
 * serves: FR-3, FR-5（REQ-81aabd design 归位与旧条目回填）。
 * 覆盖：文件名→种类推断；目录扫描补登（autoDiscovered 标记）；幂等（重复扫描不重复）；
 * 已登记文件跳过；目录不存在不炸。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { discoverArtifacts, syncReqArtifacts, syncAllReqArtifacts, reqDirRel } from '../src/adapters/ArtifactSync.js'
import { kindForRelPath } from '../src/domain/artifact/ArtifactSpec.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

let dir: string
let store: ReqboardStore
const REQ = 'REQ-abc123'

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-sync-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seedReq(artifacts?: StageArtifact[]): Promise<void> {
  const r = {
    id: REQ, title: '看板需求', description: '', status: 'brainstorming', blocked: false,
    sourceSessionId: 'session-w', comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    ...(artifacts !== undefined ? { artifacts } : {}),
  } as unknown as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

function writeReqFile(rel: string, content = 'x'): void {
  const abs = join(dir, reqDirRel(REQ), rel)
  mkdirSync(join(abs, '..'), { recursive: true })
  writeFileSync(abs, content)
}

describe('kindForRelPath', () => {
  it('必备产物按文件名归位，其余归 notes', () => {
    expect(kindForRelPath('requirement.md')).toBe('requirement')
    expect(kindForRelPath('plan.md')).toBe('plan')
    expect(kindForRelPath('decomposition.md')).toBe('decomposition')
    expect(kindForRelPath('verification.md')).toBe('verification')
    expect(kindForRelPath('archive.md')).toBe('archive')
    expect(kindForRelPath('tasks/t-abc123.md')).toBe('task_detail')
    expect(kindForRelPath('design/architecture.md')).toBe('design')
    expect(kindForRelPath('prototype.html')).toBe('notes')
    expect(kindForRelPath('lanes-prototype.html')).toBe('notes')
  })
})

describe('discoverArtifacts（纯扫描）', () => {
  it('扫描需求目录，未登记文件带 autoDiscovered 标记', async () => {
    await seedReq()
    writeReqFile('requirement.md')
    writeReqFile('prototype.html')
    writeReqFile('tasks/t-abc123.md')
    const req = store.snapshot().requirements[0]
    const found = discoverArtifacts(req, join(dir, reqDirRel(REQ)), reqDirRel(REQ))
    const byPath = Object.fromEntries(found.map(a => [a.path, a]))
    expect(byPath[reqDirRel(REQ) + '/requirement.md'].kind).toBe('requirement')
    expect(byPath[reqDirRel(REQ) + '/prototype.html'].kind).toBe('notes')
    expect(byPath[reqDirRel(REQ) + '/prototype.html'].autoDiscovered).toBe(true)
    expect(byPath[reqDirRel(REQ) + '/prototype.html'].fileSize).toBeGreaterThan(0)
    expect(byPath[reqDirRel(REQ) + '/tasks/t-abc123.md'].kind).toBe('task_detail')
  })

  it('已登记的文件跳过', async () => {
    const p = reqDirRel(REQ) + '/requirement.md'
    await seedReq([{ stage: 'brainstorming', kind: 'requirement', path: p, registeredAt: 1, registeredBy: { kind: 'agent' } }])
    writeReqFile('requirement.md')
    const req = store.snapshot().requirements[0]
    const found = discoverArtifacts(req, join(dir, reqDirRel(REQ)), reqDirRel(REQ))
    expect(found).toHaveLength(0)
  })

  it('目录不存在 → 返回空数组不炸', async () => {
    await seedReq()
    const req = store.snapshot().requirements[0]
    expect(discoverArtifacts(req, join(dir, 'nope'), reqDirRel(REQ))).toEqual([])
  })
})

describe('syncReqArtifacts（落库）', () => {
  it('落库补登 + 写评论；重复调用幂等返回 0', async () => {
    await seedReq()
    writeReqFile('prototype.html')
    const added1 = await syncReqArtifacts(store, REQ, dir)
    expect(added1).toBe(1)
    const req1 = store.snapshot().requirements.find(r => r.id === REQ)!
    expect(req1.artifacts).toHaveLength(1)
    expect(req1.artifacts![0].autoDiscovered).toBe(true)
    expect(req1.comments.some(c => c.body.includes('产物自动发现'))).toBe(true)

    const added2 = await syncReqArtifacts(store, REQ, dir)
    expect(added2).toBe(0)
    expect(store.snapshot().requirements.find(r => r.id === REQ)!.artifacts).toHaveLength(1)
  })

  it('design/*.md 补登为设计文档，归设计节点（FR-1/FR-3）', async () => {
    await seedReq()
    writeReqFile('design/architecture.md')
    expect(await syncReqArtifacts(store, REQ, dir)).toBe(1)
    const a = store.snapshot().requirements.find(r => r.id === REQ)!.artifacts![0]
    expect(a.path).toBe(reqDirRel(REQ) + '/design/architecture.md')
    expect(a.kind).toBe('design')
    expect(a.stage).toBe('design')
  })

  it('分类规则升级后回填旧条目种类（notes → design），且幂等', async () => {
    const p = reqDirRel(REQ) + '/design/architecture.md'
    await seedReq([{ stage: 'design', kind: 'notes', path: p, autoDiscovered: true, registeredAt: 1, registeredBy: { kind: 'agent' } }])
    writeReqFile('design/architecture.md')
    await syncReqArtifacts(store, REQ, dir)
    const a = store.snapshot().requirements.find(r => r.id === REQ)!.artifacts![0]
    expect(a.kind).toBe('design')
    expect(a.stage).toBe('design')
    // 已回填 + 已登记 → 再跑一次无动作（无新文件、无待回填）
    expect(await syncReqArtifacts(store, REQ, dir)).toBe(0)
  })

  it('手工登记的产物不被回填覆盖（只回填 autoDiscovered）', async () => {
    const p = reqDirRel(REQ) + '/design/architecture.md'
    await seedReq([{ stage: 'design', kind: 'notes', path: p, registeredAt: 1, registeredBy: { kind: 'agent' } }])
    writeReqFile('design/architecture.md')
    await syncReqArtifacts(store, REQ, dir)
    expect(store.snapshot().requirements.find(r => r.id === REQ)!.artifacts![0].kind).toBe('notes')
  })

  it('syncAllReqArtifacts 扫描全部需求', async () => {
    await seedReq()
    writeReqFile('requirement.md')
    writeReqFile('prototype.html')
    const total = await syncAllReqArtifacts(store, dir)
    expect(total).toBe(2)
  })
})
