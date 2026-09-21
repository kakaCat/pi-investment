/**
 * 任务卡验收标准修订通道单测（REQ-d3e61a T-9 前置 / 用户裁定 b）
 *
 * 通道的意义：acceptance 落库后原本无修订路径 → "不可照着验"只能被硬拦却无法修复（=死锁）。
 * 本用例验证：能改、改后合规、改不了时响亮拒绝、不传时零行为变更。
 */
import { describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { amendTaskAcceptanceIfRequested, requestedAcceptance } from '../src/application/use-cases/AmendTaskAcceptance.js'

const EXEC = { agent: { id: 'session-w-001' } }

const seed = () =>
  makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'in_progress' })] })

describe('requestedAcceptance（未传 = 不改，零行为变更）', () => {
  it('缺省 / 空串 → undefined', () => {
    expect(requestedAcceptance({ task_id: 't-000001' })).toBeUndefined()
    expect(requestedAcceptance({ acceptance: '' })).toBeUndefined()
    expect(requestedAcceptance({ acceptance: '   ' })).toBeUndefined()
  })
  it('有值 → 返回原文', () => {
    expect(requestedAcceptance({ acceptance: '跑 npx vitest run 全绿' })).toBe('跑 npx vitest run 全绿')
  })
})

describe('amendTaskAcceptanceIfRequested', () => {
  it('不传 acceptance → 返回 undefined（既有 task_move 调用完全不受影响）', async () => {
    const h = seed()
    expect(await amendTaskAcceptanceIfRequested(h.deps, { task_id: 't-000001' }, EXEC)).toBeUndefined()
    expect(h.repo.ledger.tasks[0].acceptance).not.toBe('跑 npx vitest run 全绿')
  })

  it('传弱标准（"确认可用"）→ 拒绝，且台账不变（空话不能换成更弱的标准）', async () => {
    const h = seed()
    await expect(
      amendTaskAcceptanceIfRequested(h.deps, { task_id: 't-000001', acceptance: '确认可用' }, EXEC),
    ).rejects.toThrow()
    expect(h.repo.ledger.tasks[0].acceptance).not.toBe('确认可用')
  })

  it('传可操作标准 → 台账更新并返回新文本', async () => {
    const h = seed()
    const next = '跑 npx vitest run tests/x.test.ts → 3 passed'
    const out = await amendTaskAcceptanceIfRequested(h.deps, { task_id: 't-000001', acceptance: next }, EXEC)
    expect(out).toBe(next)
    expect(h.repo.ledger.tasks[0].acceptance).toBe(next)
  })

  it('旧卡（改名前的 ## 验收标准）仍能整段替换——存量不重写也要能改', async () => {
    const h = seed()
    const docPath = 'docs/requirements/REQ-000001/tasks/t-000001.md'
    await h.docs.write(docPath, '# t-000001\n\n## 验收标准\n\n旧的弱标准\n\n## 下一步\n\n继续\n')
    const next = '跑 npx vitest run tests/x.test.ts → 3 passed'
    await amendTaskAcceptanceIfRequested(h.deps, { task_id: 't-000001', acceptance: next }, EXEC)
    const text = await h.docs.read(docPath)
    expect(text).toContain(next)
    expect(text).not.toContain('旧的弱标准')
    expect(text).toContain('## 下一步')
  })

  it('新卡（## 得到什么结果）同样整段替换——改名后 T-9 通道不失效', async () => {
    const h = seed()
    const docPath = 'docs/requirements/REQ-000001/tasks/t-000001.md'
    await h.docs.write(docPath, '# t-000001\n\n## 在做什么\n甲\n\n## 得到什么结果\n\n旧的弱标准\n\n## 下一步\n\n继续\n')
    const next = '跑 npx vitest run tests/x.test.ts → 3 passed'
    await amendTaskAcceptanceIfRequested(h.deps, { task_id: 't-000001', acceptance: next }, EXEC)
    const text = await h.docs.read(docPath)
    expect(text).toContain(next)
    expect(text).not.toContain('旧的弱标准')
    // 整段替换不能吃掉邻节
    expect(text).toContain('## 在做什么')
    expect(text).toContain('## 下一步')
  })

  it('卡上两个标题都没有 → 台账照改、文档不硬造（无该段不是错误）', async () => {
    const h = seed()
    const docPath = 'docs/requirements/REQ-000001/tasks/t-000001.md'
    const original = '# t-000001\n\n## 范围\n\n- 阶段：implement\n'
    await h.docs.write(docPath, original)
    const next = '跑 npx vitest run tests/x.test.ts → 3 passed'
    await amendTaskAcceptanceIfRequested(h.deps, { task_id: 't-000001', acceptance: next }, EXEC)
    expect(h.repo.ledger.tasks[0].acceptance).toBe(next)
    expect(await h.docs.read(docPath)).toBe(original)
  })

  it('任务不属于本窗口绑定的需求 → 拒绝', async () => {
    const h = makeHarness({
      requirements: [req({ id: 'REQ-000002', sourceSessionId: 'session-other', status: 'implementing' })],
      tasks: [task({ id: 't-000002', requirementId: 'REQ-000002', status: 'in_progress' })],
    })
    await expect(
      amendTaskAcceptanceIfRequested(h.deps, { task_id: 't-000002', acceptance: '跑 npx vitest run 全绿' }, EXEC),
    ).rejects.toThrow()
  })
})
