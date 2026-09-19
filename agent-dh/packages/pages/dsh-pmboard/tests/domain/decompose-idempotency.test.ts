/**
 * L1 领域单测 · 拆分幂等守卫（REQ-47939a t3 / INV-3，事故 B / 2026-09-17 自锁修正）。
 */
import { describe, it, expect } from 'vitest'
import { checkDecomposeIdempotency } from '../../src/domain/workflow/DecomposeSpec.js'

describe('checkDecomposeIdempotency', () => {
  it('implementing / accepting（已越过拆分）→ 拒绝', () => {
    for (const status of ['implementing', 'accepting'] as const) {
      const v = checkDecomposeIdempotency(status, [])
      expect(v).toMatchObject({ ok: false, code: 'REQBOARD_ALREADY_DECOMPOSED' })
      if (!v.ok) expect(v.reason).toContain('需求已处于 ' + status)
    }
  })

  it('已有未取消任务 → 拒绝并列出清单', () => {
    const v = checkDecomposeIdempotency('decomposing', [{ id: 't-abc123', title: '改代码', status: 'todo' }])
    expect(v).toMatchObject({ ok: false, code: 'REQBOARD_ALREADY_DECOMPOSED' })
    if (!v.ok) {
      expect(v.reason).toContain('已落库 1 个未取消任务')
      expect(v.reason).toContain('t-abc123 改代码（todo）')
    }
  })

  it('decomposing 且无任务 → 放行（2026-09-17 修正：计划批准自动进 decomposing 不再自锁）', () => {
    expect(checkDecomposeIdempotency('decomposing', [])).toEqual({ ok: true })
  })

  it('draft / brainstorming / design 且无任务 → 放行', () => {
    for (const status of ['draft', 'brainstorming', 'design'] as const) {
      expect(checkDecomposeIdempotency(status, []), status).toEqual({ ok: true })
    }
  })
})
