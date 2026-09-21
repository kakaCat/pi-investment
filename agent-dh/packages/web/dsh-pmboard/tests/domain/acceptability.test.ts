/**
 * L1 领域单测 · 可证伪验收 + 计划任务依赖引用（REQ-47939a t2，规则源自 REQ-2e9473 t03/事故 G）。
 *
 * 覆盖：空话黑名单命中 / 缺可验证锚点 / 合法锚点通过；自依赖 / 悬空引用 / 前向引用三条拒绝，
 * 以及报错优先级（与搬迁前逐字一致）。
 */
import { describe, it, expect } from 'vitest'
import {
  VACUOUS_ACCEPTANCE,
  VERIFIABLE_ANCHOR,
  checkAcceptance,
  checkPlanTaskReferences,
} from '../../src/domain/task/Acceptability.js'

describe('checkAcceptance：验收标准可证伪', () => {
  it('缺验收标准 → 拒绝', () => {
    const v = checkAcceptance('t1', '')
    expect(v.ok).toBe(false)
    if (!v.ok) expect(v.reason).toContain('缺验收标准')
  })

  it('空话（黑名单命中）→ 拒绝，即使带锚点也拒', () => {
    for (const text of ['正常', '功能正常', '没问题', '一切正常', '运行正常', '看起来没问题']) {
      expect(VACUOUS_ACCEPTANCE.test(text) || !VERIFIABLE_ANCHOR.test(text)).toBe(true)
      const v = checkAcceptance('t1', text)
      expect(v.ok, text).toBe(false)
    }
  })

  it('缺可验证锚点 → 拒绝', () => {
    const v = checkAcceptance('t1', '把功能做好并交付')
    expect(v.ok).toBe(false)
    if (!v.ok) expect(v.reason).toContain('缺少可验证锚点')
  })

  it('含文件路径 / 命令 / 断言关键词之一 → 通过', () => {
    for (const text of [
      'src/foo.ts 存在且导出 bar',
      'npx vitest run 全绿',
      '接口返回 200 且内容包含 ok',
    ]) {
      expect(checkAcceptance('t1', text), text).toEqual({ ok: true })
    }
  })
})

describe('checkPlanTaskReferences：自依赖 / 悬空 / 前向引用', () => {
  it('自依赖 → 拒绝', () => {
    const v = checkPlanTaskReferences([{ key: 't1', dependsOn: ['t1'] }])
    expect(v.ok).toBe(false)
    if (!v.ok) expect(v.reason).toContain('不能依赖自身')
  })

  it('悬空引用 → 拒绝', () => {
    const v = checkPlanTaskReferences([{ key: 't1', dependsOn: ['t9'] }])
    expect(v.ok).toBe(false)
    if (!v.ok) expect(v.reason).toContain('不存在的 key：t9')
  })

  it('前向引用 → 拒绝（事故 G）', () => {
    const v = checkPlanTaskReferences([
      { key: 't1', dependsOn: ['t2'] },
      { key: 't2', dependsOn: [] },
    ])
    expect(v.ok).toBe(false)
    if (!v.ok) expect(v.reason).toContain('前向引用')
  })

  it('后向引用 / 无依赖 → 通过', () => {
    expect(checkPlanTaskReferences([
      { key: 't1', dependsOn: [] },
      { key: 't2', dependsOn: ['t1'] },
    ])).toEqual({ ok: true })
  })
})
