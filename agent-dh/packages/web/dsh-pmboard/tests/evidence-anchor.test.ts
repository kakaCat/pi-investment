/**
 * 结单证据锚定单测（REQ-d3e61a T-6 / serve FR-4）
 *
 * 验收口径：清空某张卡的 evidence 后重新结单 → 返回拒绝（凭证门）；evidence 可定位到编号时返回通过。
 * 核心：**证据不是"我做了"，而是"这条需求因此被满足了"**。
 */
import { describe, expect, it } from 'vitest'
import { evidenceAnchorGap, EVIDENCE_ANCHOR, doneEvidenceAnchorFailure } from '../src/application/internal/content-gate-wiring.js'

const doc = (...lines: string[]) => lines.join('\n')

const fakeDocs = (files: Record<string, string>) => ({
  exists: (p: string) => Object.prototype.hasOwnProperty.call(files, p),
  read: async (p: string) => files[p] ?? '',
})

const RTM = doc(
  '# REQ-t 拆分清单', '',
  '## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）', '',
  '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |',
  '|--------|---------|--------|------|------|',
  '| FR-4 | T-1 | t-aaa111 | 证据锚定 | done |',
)
const DOCS = fakeDocs({ 'docs/requirements/REQ-t/decomposition.md': RTM })

describe('evidenceAnchorGap（证据必须可定位）', () => {
  it('无 RTM 绑定（clauseIds 空）→ 规则不适用（不追溯惩罚）', () => {
    expect(evidenceAnchorGap([], ['测试通过'])).toBeUndefined()
  })

  it('**证据为空 → 缺口**（清空 evidence 后结单的形态）', () => {
    expect(evidenceAnchorGap(['FR-4'], [])).toContain('证据为空')
    expect(evidenceAnchorGap(['FR-4'], ['   '])).toContain('证据为空')
  })

  it('证据含条款编号 → 可定位', () => {
    expect(evidenceAnchorGap(['FR-4'], ['FR-4：拆分时漏条款已被拦下'])).toBeUndefined()
  })

  it('证据含可核验锚点（命令/路径/数据）→ 可定位', () => {
    expect(evidenceAnchorGap(['FR-4'], ['npx vitest run tests/x.test.ts 3 passed'])).toBeUndefined()
    expect(evidenceAnchorGap(['FR-4'], ['packages/pages/dsh-pmboard/tests/x.test.ts'])).toBeUndefined()
    expect(evidenceAnchorGap(['FR-4'], ['SELECT count(*) FROM watch_todos → 0'])).toBeUndefined()
  })

  it('**空话证据 → 缺口**（"测试通过""已完成"无法定位到条款）', () => {
    expect(evidenceAnchorGap(['FR-4'], ['测试通过'])).toContain('不可定位')
    expect(evidenceAnchorGap(['FR-4'], ['已完成'])).toContain('不可定位')
    expect(evidenceAnchorGap(['FR-4'], ['没问题'])).toContain('不可定位')
  })

  it('缺口文案点明缺什么（编号 + 锚点），可照着补', () => {
    const gap = evidenceAnchorGap(['FR-4', 'FR-9'], ['已完成'])
    expect(gap).toContain('FR-4/FR-9')
    expect(gap).toContain('命令/路径/数据')
  })

  it('锚点模式覆盖命令/路径/数据三类（判据本身的守卫）', () => {
    expect(EVIDENCE_ANCHOR.test('npx vitest run')).toBe(true)
    expect(EVIDENCE_ANCHOR.test('tests/a.test.ts')).toBe(true)
    expect(EVIDENCE_ANCHOR.test('3 passed')).toBe(true)
    expect(EVIDENCE_ANCHOR.test('测试通过')).toBe(false)
  })
})

describe('doneEvidenceAnchorFailure（结单前的门禁；状态判定在 application 层）', () => {
  const tasks = [
    { id: 't-aaa111', requirementId: 'REQ-t', lastReport: { completed: ['已完成'] } },
    { id: 't-bbb222', requirementId: 'REQ-t', lastReport: { completed: ['npx vitest run tests/x.test.ts 3 passed'] } },
  ]
  const base = { to: 'done', tasks, boundRequirementIds: ['REQ-t'] }

  it('**验收场景**：清空 evidence 后重新结单 → 返回缺口（凭证门）', async () => {
    const cleared = [{ id: 't-aaa111', requirementId: 'REQ-t', lastReport: { completed: [] } }]
    const gap = await doneEvidenceAnchorFailure(DOCS, { ...base, taskId: 't-aaa111', tasks: cleared })
    expect(gap).toBeDefined()
    expect(gap).toContain('证据为空')
  })

  it('空话证据 → 缺口', async () => {
    const gap = await doneEvidenceAnchorFailure(DOCS, { ...base, taskId: 't-aaa111' })
    expect(gap).toBeDefined()
  })

  it('**可定位的证据 → 通过**', async () => {
    expect(await doneEvidenceAnchorFailure(DOCS, { ...base, taskId: 't-bbb222' })).toBeUndefined()
  })

  it('非结单目标状态 → 不校验（状态判定在 application 层，工具壳不判）', async () => {
    expect(await doneEvidenceAnchorFailure(DOCS, { ...base, taskId: 't-aaa111', to: 'testing' })).toBeUndefined()
  })

  it('不属于本窗口绑定需求 / 未知任务 → 不拦', async () => {
    expect(await doneEvidenceAnchorFailure(DOCS, { ...base, taskId: 't-aaa111', boundRequirementIds: [] })).toBeUndefined()
    expect(await doneEvidenceAnchorFailure(DOCS, { ...base, taskId: 't-zzz999' })).toBeUndefined()
  })

  it('需求没有 RTM 表 → 无绑定 → 不拦（不追溯惩罚）', async () => {
    expect(await doneEvidenceAnchorFailure(fakeDocs({}), { ...base, taskId: 't-aaa111' })).toBeUndefined()
  })
})
