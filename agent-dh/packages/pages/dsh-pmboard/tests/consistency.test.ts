/**
 * 三方一致性单测（REQ-d3e61a T-8 / serve FR-9）
 *
 * 验收口径：用 R9 场景回归——需求有编号、无设计、无实施 → 验收单返回「设计缺失/实施缺失」。
 * 这是 R9 静默丢失的解药：不一致必须**显式出现**，不允许沉默。
 */
import { describe, expect, it } from 'vitest'
import {
  buildConsistencyRows, clauseReceiveStatus, consistencyGaps, taskRefsFromDecomposition, collectTaskRefs,
} from '../src/application/internal/content-gate-wiring.js'
import { parseDocument } from '../src/application/internal/content-gates.js'
import { buildSheet } from '../src/domain/workflow/AcceptanceSheetSpec.js'

const doc = (...lines: string[]) => lines.join('\n')

describe('buildConsistencyRows + consistencyGaps（三方比对）', () => {
  it('**R9 场景**：需求有编号、无设计、无实施 → 同时报「设计缺失」与「实施缺失」', () => {
    const items = [
      { id: 'FR-1', serves: [], kind: 'requirement' },
      { id: 'FR-4', serves: [], kind: 'requirement' },
      { id: 'FR-9', serves: [], kind: 'requirement' },
    ]
    const gaps = consistencyGaps(buildConsistencyRows(items, [
      { id: 't-1', requirement_refs: ['FR-1'] },
      { id: 't-2', requirement_refs: ['FR-4'] },
    ]))
    expect(gaps.join(' ')).toContain('FR-9 设计缺失')
    expect(gaps.join(' ')).toContain('FR-9 实施缺失')
    expect(gaps.join(' ')).not.toContain('FR-1 实施缺失')
  })

  it('有设计无实施 → 只报「实施缺失」', () => {
    const items = [
      { id: 'FR-1', serves: [], kind: 'requirement' },
      { id: 'D-ARCH-1', serves: ['FR-1'], kind: 'design' },
    ]
    const gaps = consistencyGaps(buildConsistencyRows(items, []))
    expect(gaps.join(' ')).toContain('FR-1 实施缺失')
    expect(gaps.join(' ')).not.toContain('FR-1 设计缺失')
  })

  it('三方齐全 → 一致，无缺口', () => {
    const items = [
      { id: 'FR-1', serves: [], kind: 'requirement' },
      { id: 'D-ARCH-1', serves: ['FR-1'], kind: 'design' },
    ]
    expect(consistencyGaps(buildConsistencyRows(items, [{ id: 't-1', requirement_refs: ['FR-1'] }]))).toEqual([])
  })

  it('超范围：任务没接任何条款 → 单独报', () => {
    const gaps = consistencyGaps(buildConsistencyRows(
      [{ id: 'FR-1', serves: [], kind: 'requirement' }],
      [{ id: 't-9', requirement_refs: [] }],
    ))
    expect(gaps.join(' ')).toContain('t-9 超范围')
  })

  it('悬空引用：设计章节声称服务不存在的编号', () => {
    const gaps = consistencyGaps(buildConsistencyRows(
      [{ id: 'D-ARCH-1', serves: ['FR-99'], kind: 'design' }],
      [],
    ))
    expect(gaps.join(' ')).toContain('FR-99')
    expect(gaps.join(' ')).toContain('不存在')
  })

  it('camelCase 的 requirementRefs 同样被认', () => {
    const items = [
      { id: 'FR-1', serves: [], kind: 'requirement' },
      { id: 'D-ARCH-1', serves: ['FR-1'], kind: 'design' },
    ]
    expect(consistencyGaps(buildConsistencyRows(items, [{ id: 't-1', requirementRefs: ['FR-1'] }]))).toEqual([])
  })
})

describe('taskRefsFromDecomposition（绑定从 RTM 表读——TaskRecord 不存它）', () => {
  const dec = doc(
    '# REQ-x 拆分清单', '',
    '## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）', '',
    '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |',
    '|--------|---------|--------|------|------|',
    '| FR-1 | T-1 | t-aaa111 | 覆盖门禁 | todo |',
    '| FR-4 | T-1 | t-aaa111 | 覆盖门禁 | todo |',
    '| —（未声明接收任何条款） | T-9 | t-zzz999 | 顺手改的 | todo |',
  )

  it('按任务聚合根编号；未声明的行不计入', () => {
    const refs = taskRefsFromDecomposition(parseDocument(dec))
    // 语义不变，只是值随"计划键 → 台账任务"解析通道升级：title 是新增的解析凭据
    // （文档里的任务列可能是计划键 T-1 而非台账 id t-aaa111，靠标题唯一匹配认回去）。
    expect(refs).toEqual([
      { id: 't-aaa111', requirement_refs: ['FR-1', 'FR-4'], title: '覆盖门禁' },
    ])
  })

  it('带标题的 RTM：id 认不出时按标题唯一匹配解析回台账任务（真实需求用计划键）', () => {
    const refs0 = taskRefsFromDecomposition(parseDocument(dec))
    const ledger = [{ id: 't-aaa111', status: 'in_progress', title: '覆盖门禁' }]
    const s = clauseReceiveStatus(['FR-1'], refs0, ledger)
    expect(s[0]).toEqual({ clause: 'FR-1', state: 'received', by: ['t-aaa111'] })
    const canceled = [{ id: 't-aaa111', status: 'canceled', title: '覆盖门禁' }]
    expect(clauseReceiveStatus(['FR-1'], refs0, canceled)[0].state).toBe('unreceived')
  })

  it('无 RTM 表 → 空数组（调用方据此判"无法比对"，不误报实施缺失）', async () => {
    const fake = { exists: () => true, read: async () => '# 只有任务清单\n\n| 计划 key | 任务 id |\n|---|---|\n| T-1 | t-1 |' }
    expect(await collectTaskRefs(fake as any, { id: 'REQ-x' } as any)).toEqual([])
  })
})

describe('验收单可见性', () => {
  const base = {
    sheetHistoryLength: 0,
    tasks: [{ id: 't-1', title: 'A', acceptance: 'npx vitest run x 通过' }],
    evidence: ['ev'], generatedAt: 1, generatedBy: { kind: 'agent', sessionId: 'w' },
  } as any

  it('有不一致 → 出现「三方一致性」可见项且 pending', () => {
    const r = buildSheet({ ...base, consistencyGaps: ['FR-9 设计缺失：…', 'FR-9 实施缺失：…'] })
    const item = r.sheet.items.find(i => i.criterion.includes('三方一致性'))
    expect(item).toBeDefined()
    expect(item?.criterion).toContain('FR-9')
    expect(item?.status).toBe('pending')
  })

  it('无不一致 → 不追加（不制造噪声）', () => {
    expect(buildSheet(base).sheet.items.some(i => i.criterion.includes('三方一致性'))).toBe(false)
  })
})
