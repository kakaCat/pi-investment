/**
 * 事件型 worktree 注入接线单测（REQ-260923222557-d3b0 t3 · serves FR-2, FR-3）。
 *
 * 断言两条路径各投递一次且文本含对应命令；投递抛错/未装配**不阻断**状态转移。
 */
import { describe, it, expect } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { acceptSheet } from '../src/application/use-cases/AcceptSheet.js'
import { submitVerification } from '../src/application/use-cases/SubmitVerification.js'
import { FINAL_PASS_LABEL } from '../src/domain/text/labels.js'

const EXEC = { agent: { id: 'session-w-001' } }

/** 记录型投递端口（可切换为抛错，验证降级）。 */
function spyDelivery(throwOnDeliver = false) {
  const sent: { windowKey: string; text: string }[] = []
  return {
    sent,
    port: {
      deliver(windowKey: string, message: { text: string }) {
        if (throwOnDeliver) throw new Error('投递通道炸了')
        sent.push({ windowKey, text: message.text })
        return { delivered: true }
      },
    },
  }
}

/** 造一张可完工的任务（doc 证据 + 已汇报，满足 done 凭证门）。 */
function doneReadySeed() {
  const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'in_review' })] })
  h.docs.put('src/x.ts', 'x')
  h.repo.ledger.tasks[0]!.lastReport = { at: h.clock.t, reportIndex: 1, filesChanged: ['src/x.ts'], completed: ['干完了'] }
  return h
}

describe('FR-2 子任务完成 → worktree 提交提示', () => {
  it('task → done 投递一次，文本含 commit 命令与任务标题', async () => {
    const h = doneReadySeed()
    const spy = spyDelivery()
    h.deps.delivery = spy.port
    const out: any = await executeMoveTask(h.deps, { task_id: 't-000001', to: 'done' }, EXEC)
    expect(out.to).toBe('done')
    expect(spy.sent).toHaveLength(1)
    expect(spy.sent[0]!.windowKey).toBe('session-w-001')
    expect(spy.sent[0]!.text).toContain('git commit -m')
    expect(spy.sent[0]!.text).toContain('REQ-000001')
    expect(spy.sent[0]!.text).toContain('任务')
  })

  it('故障注入：投递抛错 → 转移仍成功（不阻断）', async () => {
    const h = doneReadySeed()
    const spy = spyDelivery(true)
    h.deps.delivery = spy.port
    const out: any = await executeMoveTask(h.deps, { task_id: 't-000001', to: 'done' }, EXEC)
    expect(out.to).toBe('done')
    expect(h.repo.ledger.tasks[0]!.status).toBe('done')
  })

  it('未装配投递端口 → 转移仍成功（缺省 = 不投递）', async () => {
    const h = doneReadySeed()
    const out: any = await executeMoveTask(h.deps, { task_id: 't-000001', to: 'done' }, EXEC)
    expect(out.to).toBe('done')
  })

  it('非 done 转移不投递（in_progress 安静）', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'in_progress' })] })
    const spy = spyDelivery()
    h.deps.delivery = spy.port
    await executeMoveTask(h.deps, { task_id: 't-000001', to: 'testing' }, EXEC)
    expect(spy.sent).toHaveLength(0)
  })
})

describe('FR-3 需求归档 → worktree 合并清理提示', () => {
  it('accept_sheet 全通过归档 → 投递一次，文本含 merge/worktree remove', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })], tasks: [task({ status: 'done' })] })
    const spy = spyDelivery()
    h.deps.delivery = spy.port
    await submitVerification(h.deps, { summary: '交付', evidence: ['npx vitest run 全绿'] }, EXEC)
    // 把验收单各项置为已通过（模拟逐项裁决过完）
    const sheet = h.repo.ledger.requirements[0]!.verification!.sheet!
    for (const it of sheet.items) it.status = 'passed'
    h.questions.answers = [{ id: 'final-pass', selected: [FINAL_PASS_LABEL] }]
    const out: any = await acceptSheet(h.deps, {}, EXEC)
    expect(out.archived).toBe(true)
    expect(h.repo.ledger.requirements[0]!.status).toBe('archived')
    expect(spy.sent).toHaveLength(1)
    expect(spy.sent[0]!.text).toContain('git merge --no-ff feature/REQ-000001')
    expect(spy.sent[0]!.text).toContain('git worktree remove .worktrees/REQ-000001/')
  })
})
