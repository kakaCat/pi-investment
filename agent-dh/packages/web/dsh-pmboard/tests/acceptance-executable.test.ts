/**
 * 「怎么验」硬门槛单测（REQ-d3e61a T-9 / serve FR-10）
 *
 * 关键对照：验收期判据必须比计划期更严——"返回 409" 在计划期算是可验证锚点，
 * 但在验收期**不能独立复核**（谁跑？怎么跑？），故应被拦。
 */
import { describe, expect, it } from 'vitest'
import { checkHowToVerify, checkAcceptance, HOW_TO_VERIFY, VERIFIABLE_ANCHOR } from '../src/domain/task/Acceptability.js'

describe('checkHowToVerify（验收期：必须能照着动手）', () => {
  it('可执行命令 → 通过', () => {
    expect(checkHowToVerify('FR-1', '运行 npx vitest run tests/x.test.ts → 3 passed').ok).toBe(true)
    expect(checkHowToVerify('FR-2', '跑 pytest tests/gates/test_x.py 全绿').ok).toBe(true)
  })

  it('可达界面路径 → 通过', () => {
    expect(checkHowToVerify('FR-3', '打开盯盘规则页 → 编辑任一规则 → 条件下拉出现三项').ok).toBe(true)
  })

  it('可查数据（SQL/字段） → 通过', () => {
    expect(checkHowToVerify('FR-4', 'SELECT watch_todos WHERE status=promoted 有 1 行').ok).toBe(true)
  })

  it('只写"确认可用""应该没问题" → 被拦', () => {
    expect(checkHowToVerify('FR-5', '确认可用').ok).toBe(false)
    expect(checkHowToVerify('FR-6', '应该没问题').ok).toBe(false)
    expect(checkHowToVerify('FR-7', '').ok).toBe(false)
  })

  it('**只有断言词、没有可执行操作** → 被拦（这正是与计划期判据的分水岭）', () => {
    const onlyAssertion = '注入难度判定返回 heavy'
    expect(checkHowToVerify('FR-8', onlyAssertion).ok).toBe(false)
    // 但它在计划期是合格的（含断言词"返回"）
    expect(checkAcceptance('T-8', onlyAssertion).ok).toBe(true)
  })

  it('两条判据的关系：验收期 ⊂ 计划期（验收期通过 → 计划期必然通过）', () => {
    const good = '运行 npx vitest run tests/x.test.ts → 通过'
    expect(checkHowToVerify('FR-9', good).ok).toBe(true)
    expect(checkAcceptance('T-9', good).ok).toBe(true)
    expect(HOW_TO_VERIFY.source.length).toBeGreaterThan(0)
    expect(VERIFIABLE_ANCHOR.source.length).toBeGreaterThan(0)
  })

  it('拒绝消息本身可操作（给出三类可执行操作示例 + key）', () => {
    const r = checkHowToVerify('T-3 拆分门禁', '返回 409')
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.reason).toContain('T-3 拆分门禁')
      expect(r.reason).toContain('npx/vitest/curl/pytest')
      expect(r.reason).toContain('怎么验')
    }
  })
})
