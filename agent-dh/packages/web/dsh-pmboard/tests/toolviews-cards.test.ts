/**
 * 9 张业务卡片 summarize 四档单测（REQ-c48f99 t3 / FR-2、FR-3、FR-4）。
 * 四档：正常 / 缺字段 / 畸形 / error 态；另锁定「同工具不同参数 → 折叠行两两不同」（FR-2）。
 */
import { describe, it, expect } from 'vitest'
import type { SettledBlock } from '../src/client/toolviews/shared.ts'
import { taskMoveSummarize } from '../src/client/toolviews/rows/task-move.ts'
import { submitSummarize } from '../src/client/toolviews/rows/submit.ts'
import { askConfirmSummarize } from '../src/client/toolviews/rows/ask-confirm.ts'
import { statusSummarize } from '../src/client/toolviews/rows/status.ts'
import { captureSummarize } from '../src/client/toolviews/rows/capture.ts'
import { memoryWriteSummarize } from '../src/client/toolviews/rows/memory-write.ts'
import { decisionAuditSummarize } from '../src/client/toolviews/rows/decision-audit.ts'
import { tradeSummarize } from '../src/client/toolviews/rows/trade.ts'
import { watchSummarize } from '../src/client/toolviews/rows/watch-manage.ts'
import type { CardSummarize } from '../src/client/toolviews/shared.ts'

function settled(args: Record<string, unknown>, result: unknown, isError = false): SettledBlock {
  return {
    kind: 'tool-result', callId: 'c1',
    call: { argsRaw: JSON.stringify(args) },
    content: [{ type: 'text', text: typeof result === 'string' ? result : JSON.stringify(result) }],
    isError,
  }
}
const running = (args: Record<string, unknown>): { callId: string; argsRaw: string } =>
  ({ callId: 'c0', argsRaw: JSON.stringify(args) })

interface Case {
  name: string
  fn: CardSummarize
  args: Record<string, unknown>
  result: unknown
  lineHas: string[]
}
const CASES: Case[] = [
  { name: 'task_move', fn: taskMoveSummarize, args: { task_id: 't-abc', to: 'done' },
    result: { success: true, task_id: 't-abc', from: 'in_review', to: 'done' }, lineHas: ['t-abc', '完工'] },
  { name: 'submit', fn: submitSummarize, args: { kind: 'verification', requirement_id: 'REQ-x', summary: 's', evidence: ['e1'] },
    result: { success: true, requirement_id: 'REQ-x', status: 'accepting' }, lineHas: ['验收材料', 'REQ-x'] },
  { name: 'ask_confirm', fn: askConfirmSummarize, args: { target: 'artifact', kind: 'design', question: '确认吗' },
    result: { success: true, confirmed: true, advanced: true, from: 'design', to: 'decomposing' }, lineHas: ['已确认', 'design'] },
  { name: 'status', fn: statusSummarize, args: {},
    result: { bound: true, open_count: 1, open_requirements: [{ id: 'REQ-x', title: 't', status: 'implementing' }], next_actions: ['done'] }, lineHas: ['1 个进行中'] },
  { name: 'capture', fn: captureSummarize, args: { title_options: ['需求A'], reason: 'r' },
    result: { success: true, requirement_id: 'REQ-x', answers: { title: '需求A', category: 'feature', difficulty: 'standard' } }, lineHas: ['立项', '需求A'] },
  { name: 'memory_write', fn: memoryWriteSummarize, args: { content: '教训内容文本', namespace: 'experience', tags: ['a', 'b'], importance: 0.7 },
    result: { success: true, memory_id: 'm-1' }, lineHas: ['experience', '教训内容文本'] },
  { name: 'decision_audit', fn: decisionAuditSummarize, args: { action: 'record', decision_type: 'trade_buy', parameters: { symbol: '600519' }, reasoning: 'r' },
    result: { success: true, decision_id: 'd-1' }, lineHas: ['留痕', 'trade_buy', '600519'] },
  { name: 'trade', fn: tradeSummarize, args: { action: 'BUY', symbol: '600519', quantity: 1000, price: 12.34, reason: 'r' },
    result: { order_id: 'o-1', status: 'filled', price: 12.34, amount: 12340 }, lineHas: ['买入', '600519', '1000', '已成交'] },
  { name: 'watch_manage', fn: watchSummarize, args: { action: 'create', symbol: '600519', condition: 'price>15', name: 'n' },
    result: { success: true, rule_id: 7, message: 'ok' }, lineHas: ['新建', '600519', 'price>15'] },
]

describe('9 卡 summarize · 正常档', () => {
  for (const c of CASES) {
    it(c.name + ' 折叠行含中文关键信息', () => {
      const block = settled(c.args, c.result)
      const sum = c.fn(c.args, c.result as Record<string, unknown>, block)
      expect(sum, c.name + ' 返回 null').not.toBeNull()
      for (const frag of c.lineHas) expect(sum!.line, c.name + ' 缺片段: ' + frag).toContain(frag)
      expect(sum!.line.includes('\n')).toBe(false)
    })
  }
})

describe('同工具不同参数 → 折叠行两两不同（FR-2 核心判据）', () => {
  it('task_move 三连不同 to', () => {
    const mk = (to: string) => taskMoveSummarize({ task_id: 't-x', to }, { success: true, task_id: 't-x', to }, settled({ task_id: 't-x', to }, { success: true, task_id: 't-x', to }))
    const lines = ['in_progress', 'testing', 'done'].map(to => mk(to)!.line)
    expect(new Set(lines).size).toBe(3)
  })
})

describe('9 卡 summarize · 缺字段档（不 throw、尽力降级）', () => {
  const partial: Array<[string, CardSummarize, Record<string, unknown>]> = [
    ['task_move', taskMoveSummarize, { task_id: 't-x' }],
    ['submit', submitSummarize, { kind: 'plan' }],
    ['ask_confirm', askConfirmSummarize, { kind: 'design' }],
    ['capture', captureSummarize, { title_options: ['A'] }],
    ['memory_write', memoryWriteSummarize, { content: 'c' }],
    ['decision_audit', decisionAuditSummarize, { action: 'record' }],
    ['trade', tradeSummarize, { action: 'SELL', symbol: '600519' }],
    ['watch_manage', watchSummarize, { action: 'delete', rule_id: 3 }],
  ]
  for (const [name, fn, args] of partial) {
    it(name + ' 缺字段仍有可渲染行', () => {
      const sum = fn(args, undefined, running(args) as never)
      expect(sum === null || typeof sum.line === 'string').toBe(true)
    })
  }
})

describe('9 卡 summarize · error 态档', () => {
  const errCases: Array<[string, CardSummarize, Record<string, unknown>]> = [
    ['task_move', taskMoveSummarize, { task_id: 't-x', to: 'done' }],
    ['submit', submitSummarize, { kind: 'plan' }],
    ['ask_confirm', askConfirmSummarize, { kind: 'design', question: 'q' }],
    ['trade', tradeSummarize, { action: 'BUY', symbol: '600519' }],
    ['watch_manage', watchSummarize, { action: 'create', symbol: '600519' }],
  ]
  for (const [name, fn, args] of errCases) {
    it(name + ' error 态红标 + 首行错误', () => {
      const block = settled(args, '拒绝原因：任务不存在', true)
      const sum = fn(args, undefined, block)
      expect(sum).not.toBeNull()
      expect(sum!.isError).toBe(true)
      expect(sum!.line).toContain('任务不存在')
    })
  }
})

describe('status 卡特殊档', () => {
  it('未绑定', () => {
    const sum = statusSummarize({}, { bound: false, open_count: 0 }, settled({}, { bound: false, open_count: 0 }))
    expect(sum!.line).toBe('看板 · 未绑定需求')
  })
  it('结果缺失（运行中）', () => {
    const sum = statusSummarize({}, undefined, running({}) as never)
    expect(sum!.line).toContain('查询中')
  })
})

describe('9 卡 summarize · 畸形档（返回 null → 交 fallbackRow，FR-4）', () => {
  const junk: Array<[string, CardSummarize]> = [
    ['task_move', taskMoveSummarize],
    ['submit', submitSummarize],
    ['ask_confirm', askConfirmSummarize],
    ['memory_write', memoryWriteSummarize],
    ['decision_audit', decisionAuditSummarize],
    ['trade', tradeSummarize],
    ['watch_manage', watchSummarize],
  ]
  for (const [name, fn] of junk) {
    it(name + ' 关键字段全缺 → null', () => {
      const sum = fn({}, {}, settled({}, {}))
      expect(sum, name + ' 应返回 null').toBeNull()
    })
  }
  it('status 卡：结算但结果非 JSON → null', () => {
    const block: SettledBlock = { kind: 'tool-result', callId: 'c9', call: { argsRaw: '{}' }, content: [{ type: 'text', text: 'plain text' }], isError: false }
    expect(statusSummarize({}, undefined, block)).toBeNull()
  })
  it('capture 卡：结算但无 id 无标题 → null', () => {
    const sum = captureSummarize({}, {}, settled({}, {}))
    expect(sum).toBeNull()
  })
})
