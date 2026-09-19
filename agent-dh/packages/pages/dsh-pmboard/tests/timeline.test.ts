/**
 * 时间线（状态事件）单测 —— 数据模型、历史回填与加载迁移。
 *
 * 背景（用户提问「项目看板的需求没有对应的时间」）：此前记录上只有 createdAt/updatedAt，
 * 「评审/拆分/实施/验收/归档各发生在什么时候、每段停留多久」在台账里不存在。本组测试
 * 锁死三件事：①recordStatus 写事件；②老记录由评论留痕反推回填并标 inferred；
 * ③Store 加载时自动迁移（v2 → v3），且迁移结果会随下一次写盘持久化。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import {
  milestoneAt,
  recordStatus,
  ALL_REQ_STATUSES,
  ALL_TASK_STATUSES,
  type RequirementRecord,
  type TaskRecord,
} from '../src/shared/protocol.js'
import {
  backfillRequirementHistory,
  backfillTaskHistory,
  parseTransitionTarget,
} from '../src/domain/legacy/LegacyStatus.js'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'

function req(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-abc123', title: '需求', description: '', status: 'draft', blocked: false,
    comments: [], version: 1, createdAt: 1000, updatedAt: 1000,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  } as RequirementRecord
}

function task(over: Partial<TaskRecord> = {}): TaskRecord {
  return {
    id: 't-abc123', requirementId: 'REQ-abc123', title: '任务', description: '',
    phase: 'implement', side: 'fullstack', dependsOn: [],
    scope: { apis: [], tables: [], files: [] }, acceptance: '', context: '',
    status: 'todo', blocked: false, executions: [], comments: [], version: 1,
    createdAt: 1000, updatedAt: 1000,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  } as TaskRecord
}

describe('recordStatus（状态事件写入）', () => {
  it('追加事件；相邻同状态同时间戳去重', () => {
    const r = req()
    recordStatus(r, 'draft', 1000, { kind: 'human' }, '创建')
    recordStatus(r, 'draft', 1000, { kind: 'human' }, '创建') // 去重
    recordStatus(r, 'brainstorming', 2000, { kind: 'system' }, '启动对账')
    expect(r.statusHistory).toHaveLength(2)
    expect(r.statusHistory?.map(e => e.status)).toEqual(['draft', 'brainstorming'])
    expect(r.statusHistory?.[0]?.reason).toBe('创建')
    expect(milestoneAt(r, 'brainstorming')).toBe(2000)
    expect(milestoneAt(r, 'done')).toBeUndefined()
  })
})

describe('parseTransitionTarget（历史留痕解析）', () => {
  it('识别三种历史格式，拒绝非法状态', () => {
    expect(parseTransitionTarget('[自动推进] draft → brainstorming：启动对账', ALL_REQ_STATUSES)).toBe('brainstorming')
    expect(parseTransitionTarget('[窗口推进] brainstorming → decomposing：拆完', ALL_REQ_STATUSES)).toBe('decomposing')
    expect(parseTransitionTarget('[状态] implementing ← 转移说明：看板泳道卡面操作', ALL_REQ_STATUSES)).toBe('implementing')
    expect(parseTransitionTarget('[状态] → in_progress：开工', ALL_TASK_STATUSES)).toBe('in_progress')
    expect(parseTransitionTarget('[会话捕获] 来自会话 session-x', ALL_REQ_STATUSES)).toBeUndefined()
    expect(parseTransitionTarget('[自动推进] draft → not_a_status：x', ALL_REQ_STATUSES)).toBeUndefined()
  })
})

describe('backfill*（老记录时间线回填）', () => {
  it('需求：从评论逐条反推 + 末态兜底，全部标 inferred', () => {
    const r = req({
      status: 'implementing',
      updatedAt: 5000,
      comments: [
        { id: 'c1', body: '[会话捕获] 来自会话 session-x', createdAt: 1000, createdBy: { kind: 'human' } },
        { id: 'c2', body: '[自动推进] draft → brainstorming：启动对账', createdAt: 3000, createdBy: { kind: 'system' } },
      ],
    })
    const hist = backfillRequirementHistory(r)
    expect(hist).toBeDefined()
    expect(hist?.map(e => e.status)).toEqual(['draft', 'brainstorming', 'implementing'])
    expect(hist?.every(e => e.inferred === true)).toBe(true)
    expect(hist?.[1]?.at).toBe(3000)
    expect(hist?.[2]?.at).toBe(5000)
    expect(hist?.[2]?.reason).toContain('updatedAt')
  })

  it('历史评论里的旧状态名（reviewing）映射到新名（brainstorming），不丢历史', () => {
    const r = req({
      status: 'design',
      updatedAt: 6000,
      comments: [
        { id: 'c1', body: '[自动推进] draft → reviewing：启动对账', createdAt: 2000, createdBy: { kind: 'system' } },
        { id: 'c2', body: '[窗口推进] reviewing → design：方案谈定', createdAt: 4000, createdBy: { kind: 'agent' } },
      ],
    })
    const hist = backfillRequirementHistory(r)
    expect(hist?.map(e => e.status)).toEqual(['draft', 'brainstorming', 'design'])
  })

  it('任务：识别 [状态] → x 格式；已有事件则不动（幂等）', () => {
    const t = task({
      status: 'done',
      updatedAt: 9000,
      comments: [{ id: 'c1', body: '[状态] → in_progress：开工', createdAt: 4000, createdBy: { kind: 'agent' } }],
    })
    const hist = backfillTaskHistory(t)
    expect(hist?.map(e => e.status)).toEqual(['todo', 'in_progress', 'done'])
    expect(backfillTaskHistory({ ...t, statusHistory: hist! })).toBeUndefined()
  })
})

describe('Store 加载（t10 后读路径零 legacy 兼容）', () => {
  let dir: string
  beforeEach(() => { dir = mkdtempSync(join(tmpdir(), 'pmboard-migrate-')) })
  afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

  // t10 硬约束：状态名归一与 statusHistory 回填**移出运行时读路径**（改由迁移脚本一次性固化）。
  // 本用例锁死这条新契约（若有人把回填加回 load()，断言立即变红）。
  it('老台账装载不再回填时间线；写盘按当前契约版本（5）落盘', async () => {
    const file = join(dir, 'dsh-reqboard.json')
    const legacy = {
      schemaVersion: 2,
      revision: 7,
      requirements: [{
        id: 'REQ-abc123', title: '老需求', description: '', status: 'brainstorming', blocked: false,
        comments: [{ id: 'c1', body: '[自动推进] draft → brainstorming：启动对账', createdAt: 2000, createdBy: { kind: 'system' } }],
        version: 2, createdAt: 1000, updatedAt: 2000,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'system' },
      }],
      tasks: [],
      triages: [],
    }
    writeFileSync(file, JSON.stringify(legacy), 'utf8')
    const store = new ReqboardStore({ file })
    await store.load()
    const loaded = store.snapshot().requirements[0]
    // 读路径不再反推（此前 load() 会补 ['draft','brainstorming'] 并标 inferred）
    expect(loaded.statusHistory).toBeUndefined()
    // 触发一次写盘：未回填的状态原样保留，版本按当前契约常量落盘
    await store.mutate('requirement-updated', (ledger) => {
      ledger.requirements[0].title = '改名'
      return { requirements: [ledger.requirements[0]] }
    })
    const onDisk = JSON.parse(readFileSync(file, 'utf8'))
    expect(onDisk.schemaVersion).toBe(7) // C1：schema 4 → 5 → 6 → 7（REQ-81aabd：planning → design 键改名）
    expect(onDisk.requirements[0].statusHistory).toBeUndefined()
  })
})
