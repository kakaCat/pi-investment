/**
 * 验收单说人话单测（REQ-d3e61a T-11 / serve FR-7）
 *
 * 验收口径：现网真实验收单 → 判定不合格；重述后每项返回可读的业务结果描述。
 * 判据（刻意机械可判）：每项必须**先说业务结果**（【业务标题】），再说**怎么验**。
 * 只说命令的项读不出"在确认什么"，就是原来用户看不懂的那种。
 */
import { describe, expect, it } from 'vitest'
import { buildSheet, REQUIREMENT_LEVEL_CRITERION } from '../src/domain/workflow/AcceptanceSheetSpec.js'

const actor = { kind: 'agent', sessionId: 'w' } as any

const build = (tasks: any[]) =>
  buildSheet({
    sheetHistoryLength: 0,
    tasks,
    evidence: ['npx vitest run 全绿'],
    generatedAt: 1,
    generatedBy: actor,
  }).sheet

/** 「先说业务」判据：must starts with 【…】 (业务标题)，且标题里含中文。 */
const saysBusinessFirst = (criterion: string): boolean => {
  const m = /^【(.+?)】/.exec(criterion)
  return m !== null && /[\u4e00-\u9fa5]/.test(m[1])
}

describe('验收项：先说业务结果，再说怎么验（T-11）', () => {
  it('任务项 = 【业务标题】验收：<怎么验>', () => {
    const sheet = build([
      { id: 't-100001', title: '拆分门禁：条款没落卡就拦下', acceptance: 'npx vitest run tests/clause-coverage-gate.test.ts 通过' },
    ])
    const item = sheet.items[0]
    expect(item.criterion).toContain('【拆分门禁：条款没落卡就拦下】')
    expect(item.criterion).toContain('怎么验'.slice(0, 0) + 'npx vitest run tests/clause-coverage-gate.test.ts 通过')
    expect(saysBusinessFirst(item.criterion)).toBe(true)
  })

  it('回归：**旧格式（只有命令）过不了「先说业务」判据** —— 这正是用户看不懂的那种', () => {
    const oldStyle = 'npx vitest run tests/x.test.ts 通过'
    expect(saysBusinessFirst(oldStyle)).toBe(false)
    // 新格式能过
    const sheet = build([{ id: 't-100002', title: '覆盖门禁：漏条款即拦', acceptance: oldStyle }])
    expect(saysBusinessFirst(sheet.items[0].criterion)).toBe(true)
  })

  it('无验收标准时也说得清（【标题】验收：交付完成），不出现空 criter利', () => {
    const sheet = build([{ id: 't-100003', title: '某个业务动作', acceptance: '' }])
    expect(sheet.items[0].criterion).toBe('【某个业务动作】验收：交付完成')
  })

  it('标题为空时回退到 id（不产生空标题的【】）', () => {
    const sheet = build([{ id: 't-100004', title: '', acceptance: 'npx vitest run x 通过' }])
    expect(sheet.items[0].criterion).toBe('【t-100004】验收：npx vitest run x 通过')
  })

  it('需求级项保持业务语言（人手写的常量，不是命令）', () => {
    const sheet = build([{ id: 't-100005', title: 'A', acceptance: 'npx vitest run x 通过' }])
    const reqItem = sheet.items.find(i => i.source.kind === 'requirement')
    expect(reqItem?.criterion).toBe(REQUIREMENT_LEVEL_CRITERION)
    expect(/[\u4e00-\u9fa5]/.test(reqItem?.criterion ?? '')).toBe(true)
  })

  it('任务级项**全部**满足「先说业务」判据；需求级项为业务常量（不走同一谓词）', () => {
    const sheet = build([
      { id: 't-1', title: '门禁一', acceptance: 'npx vitest run a 通过' },
      { id: 't-2', title: '门禁二', acceptance: 'npx vitest run b 通过' },
    ])
    const taskItems = sheet.items.filter(i => i.source.kind === 'task')
    expect(taskItems).toHaveLength(2)
    expect(taskItems.every(i => saysBusinessFirst(i.criterion))).toBe(true)
    // 需求级项本来就是人手写的业务语言常量，不套「【标题】」格式（套了反而是形式主义）
    expect(sheet.items.filter(i => i.source.kind === 'requirement').every(i => i.criterion === REQUIREMENT_LEVEL_CRITERION)).toBe(true)
  })
})
