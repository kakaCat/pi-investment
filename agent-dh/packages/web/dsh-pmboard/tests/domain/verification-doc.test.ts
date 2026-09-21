/**
 * verification.md 渲染 + 9 类文档完整性检查单测（REQ-308b9a FR-7）。
 *
 * serves: FR-7
 *
 * T-U5 四段齐全 / T-U6 结果表五列 / T-U7 缺一类即 passed=false 且 missing 精确。
 */
import { describe, it, expect } from 'vitest'
import { checkDocCompleteness, VERIFICATION_DOC_CLASSES } from '../../src/domain/workflow/DocCompleteness.js'
import { renderVerificationDoc } from '../../src/domain/workflow/VerificationDoc.js'

const ALL_FILES = new Set<string>([
  'requirement.md', 'plan.md', 'decomposition.md',
  'design/architecture.md', 'design/data-model.md', 'design/interfaces.md', 'design/test-cases.md',
  'reviews/r1.md', 'tests/unit.log',
])

describe('T-U7: 9 类文档完整性检查（AC-7.4）', () => {
  it('九类齐全 + 任务卡齐 → passed=true、missing 空', () => {
    const files = new Set([...ALL_FILES, 'tasks/t-aaaaaa.md'])
    const r = checkDocCompleteness({ files, taskIds: ['t-aaaaaa'] })
    expect(r.passed).toBe(true)
    expect(r.missing).toEqual([])
    expect(VERIFICATION_DOC_CLASSES).toHaveLength(8) // plan.md 已删除（REQ-84bea5 T-4）
  })

  it('缺 design/interfaces.md → passed=false 且 missing 精确点名它', () => {
    const files = new Set([...ALL_FILES, 'tasks/t-aaaaaa.md'])
    files.delete('design/interfaces.md')
    const r = checkDocCompleteness({ files, taskIds: ['t-aaaaaa'] })
    expect(r.passed).toBe(false)
    expect(r.missing).toEqual(['design/interfaces.md（接口）'])
  })

  it('任务卡缺失 → missing 点名 tasks/<id>.md', () => {
    const r = checkDocCompleteness({ files: ALL_FILES, taskIds: ['t-zzzzzz'] })
    expect(r.passed).toBe(false)
    expect(r.missing).toContain('tasks/t-zzzzzz.md（任务卡）')
  })
})

describe('T-U5/T-U6: verification.md 渲染（AC-7.2/7.3/7.8）', () => {
  const items = [
    { id: 'v1-1', title: '任务一', criterion: '【任务一】验收：单测绿', howToVerify: '跑 pnpm test；看结果全绿', status: 'passed' as const, decidedBy: 'human/session-x', decidedAt: 1700000000000 },
    { id: 'v1-2', title: '任务二', criterion: '【任务二】验收：截图可见', howToVerify: '打开页面截图', status: 'not_verifiable' as const, opinion: '本机无该环境' },
  ]
  const md = renderVerificationDoc({
    reqId: 'REQ-x', title: '测试需求', summary: '交付完成', sheetVersion: 1,
    items, testReport: ['npx vitest run 全绿'], docCheck: { passed: true, missing: [] },
  })

  it('T-U5: 含四段标题（验收列表 / 测试报告 / 文档完整性检查 / 验收结果）', () => {
    expect(md).toContain('## 1. 验收列表')
    expect(md).toContain('## 2. 测试报告')
    expect(md).toContain('## 3. 文档完整性检查')
    expect(md).toContain('## 4. 验收结果')
  })

  it('T-U5b: 每项含操作步骤与预期结果（AC-7.3）', () => {
    expect(md).toContain('**操作步骤**：')
    expect(md).toContain('**预期结果**：')
    expect(md).toContain('跑 pnpm test')
  })

  it('T-U6: 验收结果表列头恰为 编号/验收项/状态/验收人/验收时间（AC-7.8）', () => {
    expect(md).toContain('| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |')
  })

  it('不可验收项在结果表显式标出（AC-9.4）', () => {
    expect(md).toContain('⊘ 不可验收')
    expect(md).toContain('本机无该环境')
  })
})
