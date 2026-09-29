/**
 * 子卡链再生成（补链）机制测试（卡片层契约 2026-09-28 / t6）。
 *
 * 覆盖：solo 卡不落链 / 链缺失全量补 / 半链只补差集 / 已有子卡（含 done）不动 / 链内 dependsOn 接续。
 * 只测纯机制（chainDiagnosis + regenerateChain），不含台账写入与工具协议。
 */
import { describe, it, expect } from 'vitest'
import { chainDiagnosis, regenerateChain } from '../src/application/internal/lazy-expand.js'

let seq = 0
const ids = { requirement: () => 'REQ-x', task: () => 't-new' + String(++seq), execution: () => 'e-x', comment: () => 'c-x' }

function parentCard(over: Record<string, unknown> = {}) {
  return {
    id: 't-p1', requirementId: 'REQ-t', title: '父卡', phase: 'implement', side: 'backend',
    dependsOn: ['t-ext'], scope: { apis: [], tables: [], files: [] }, context: 'ctx',
    implementation: 'impl', status: 'in_progress', ...over,
  }
}
function kidCard(stageKind: string, status = 'todo') {
  return {
    id: 't-k-' + stageKind, requirementId: 'REQ-t', title: '父卡·' + stageKind, phase: 'implement',
    side: 'backend', dependsOn: [], scope: { apis: [], tables: [], files: [] }, context: 'ctx',
    implementation: 'impl', status, parentId: 't-p1', stageKind, attempt: 0,
  }
}

describe('chainDiagnosis：链体检（只读）', () => {
  it('stages: []（solo）→ solo=true 且无缺失（这就是「不需子卡」）', () => {
    const d = chainDiagnosis([parentCard({ stages: [] })], parentCard({ stages: [] }) as never, { category: 'feature' })
    expect(d.solo).toBe(true)
    expect(d.expected).toEqual([])
    expect(d.missing).toEqual([])
  })
  it('无子卡 → 全部段缺失（链未生成）', () => {
    const d = chainDiagnosis([parentCard()], parentCard() as never, { category: 'feature' })
    expect(d.expected).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(d.existing).toEqual([])
    expect(d.missing).toEqual(['dev', 'integrate', 'review', 'test'])
  })
  it('半链 → 只报缺段（已有子卡不动）', () => {
    const tasks = [parentCard(), kidCard('dev', 'done'), kidCard('integrate', 'done')]
    const d = chainDiagnosis(tasks, parentCard() as never, { category: 'feature' })
    expect(d.existing).toEqual(['dev', 'integrate'])
    expect(d.missing).toEqual(['review', 'test'])
  })
  it('doc 卡走 doc 模板（2 段 dev→review）——模板未改，行为不变', () => {
    const d = chainDiagnosis([parentCard({ phase: 'doc' })], parentCard({ phase: 'doc' }) as never, { category: 'feature' })
    expect(d.expected).toEqual(['dev', 'review'])
  })
})

describe('regenerateChain：只补缺失阶段', () => {
  it('solo 卡（stages: []）→ 返回空集（不落任何子卡）', () => {
    const created = regenerateChain([parentCard({ stages: [] })], parentCard({ stages: [] }) as never, { category: 'feature' }, 1, ids as never)
    expect(created).toEqual([])
  })
  it('链未生成 → 全量补，链首继承父卡外部依赖，其后串前一张', () => {
    const created = regenerateChain([parentCard()], parentCard() as never, { category: 'feature' }, 1, ids as never)
    expect(created.map((c) => c.stageKind)).toEqual(['dev', 'integrate', 'review', 'test'])
    expect(created.every((c) => c.parentId === 't-p1')).toBe(true)
    expect(created.every((c) => c.status === 'todo')).toBe(true)
    expect(created[0].dependsOn).toEqual(['t-ext'])
    expect(created[1].dependsOn).toEqual([created[0].id])
    expect(created[3].dependsOn).toEqual([created[2].id])
  })
  it('半链 → 只补差集，接在已有链尾之后；已有子卡（含 done）不被改动', () => {
    const dev = kidCard('dev', 'done')
    const integ = kidCard('integrate', 'done')
    const tasks = [parentCard(), dev, integ]
    const created = regenerateChain(tasks, parentCard() as never, { category: 'feature' }, 1, ids as never)
    expect(created.map((c) => c.stageKind)).toEqual(['review', 'test'])
    expect(created[0].dependsOn).toEqual(['t-k-integrate'])
    expect(created[1].dependsOn).toEqual([created[0].id])
    expect(dev.status).toBe('done')
    expect(integ.status).toBe('done')
  })
  it('幂等：链已完整 → 返回空集（不重复生卡）', () => {
    const tasks = [parentCard(), kidCard('dev', 'done'), kidCard('integrate', 'done'), kidCard('review', 'done'), kidCard('test', 'done')]
    const created = regenerateChain(tasks, parentCard() as never, { category: 'feature' }, 1, ids as never)
    expect(created).toEqual([])
  })
  it('子卡自身不参与再生成（parentId 非空 → 空集）', () => {
    const created = regenerateChain([kidCard('dev')], kidCard('dev') as never, { category: 'feature' }, 1, ids as never)
    expect(created).toEqual([])
  })
})
