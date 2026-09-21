/**
 * 需求文档面 + 看板面的一致性单测（REQ-d3e61a T-5 / serve FR-3）。
 *
 * 验收口径原话：「取消某张卡对某条的交付后，该条在 **requirement.md 与看板** 返回
 * 「未被接收（红）」状态」。所以这里同时验两个面**来自同一次推导**——只验一面，等于允许
 * 「文档红、看板不红」这种半盲状态（R9 恰恰是在半盲里溜过去的）。
 *
 * 两面文案不同（文档=markdown 表格、看板=HTML），所以断言分开写，不复用同一串。
 */
import { describe, expect, it } from 'vitest'
import {
  MARKS_BEGIN,
  hasMarksBlock,
  readMarksBlockStates,
  renderMarksBlock as renderDocMarks,
  upsertMarksBlock,
} from '../src/application/internal/requirement-marks-doc.js'
import { renderMarksBlock as renderKanbanMarks } from '../src/client/marks-info.js'
import { syncRequirementMarks } from '../src/application/use-cases/SyncRequirementMarks.js'
import { assembleRequirementMarks } from '../src/application/query/QueryRequirementMarks.js'
import { clauseReceiveStatus } from '../src/application/internal/content-trace.js'
import type { RequirementMarksView } from '../src/shared/protocol.js'

const REQ_ID = 'REQ-t5mark'
const DOC = 'docs/requirements/' + REQ_ID + '/requirement.md'
const DEC = 'docs/requirements/' + REQ_ID + '/decomposition.md'

const REQUIREMENT_MD = [
  '# ' + REQ_ID + ' 样例需求',
  '',
  '## 6. 功能点',
  '',
  '**FR-1 覆盖门禁**：拆分时逐条核对。',
  '- AC1：构造样例 → 被拒绝。',
  '',
  '**FR-4 三段可追溯**：从一条功能点定位到卡与证据。',
  '',
  '**FR-9 幂等**：重复调用不动。',
  '',
  '## 7. 非功能需求',
  '',
  '| 项 | 要求 |',
  '|----|------|',
  '| 规模 | 单次提交 < 1s |',
  '',
].join('\n')

const DECOMP_MD = [
  '# ' + REQ_ID + ' 拆分清单',
  '',
  '## §1 RTM 覆盖对照表（根编号 ↔ 任务卡）',
  '',
  '| 根编号 | 计划 key | 任务 id | 标题 | 状态 |',
  '|--------|---------|--------|------|------|',
  '| FR-1 | t1 | t-aaa111 | 甲卡 | in_progress |',
  '| FR-4 | t2 | t-bbb222 | 乙卡 | in_progress |',
  '| FR-9 | t3 | t-ccc333 | 丙卡 | in_progress |',
  '',
].join('\n')

/** 内存版 DocRepository：只实现本用例用到的 exists/read/write。 */
function fakeDocs(files: Record<string, string>) {
  const store: Record<string, string> = { ...files }
  return {
    store,
    docs: {
      exists: (p: string): boolean => Object.prototype.hasOwnProperty.call(store, p),
      read: async (p: string): Promise<string> => {
        const v = store[p]
        if (v === undefined) throw new Error('ENOENT ' + p)
        return v
      },
      write: async (p: string, c: string): Promise<void> => { store[p] = c },
    },
  }
}

const REQ = { id: REQ_ID } as unknown as Parameters<typeof syncRequirementMarks>[1]

/** 取消 t-bbb222 对 FR-4 的交付后的台账（验收场景的给定状态）。 */
const TASKS_AFTER = [
  { id: 't-aaa111', status: 'in_progress' },
  { id: 't-bbb222', status: 'canceled' },
  { id: 't-ccc333', status: 'in_progress' },
]
const TASKS_BEFORE = [
  { id: 't-aaa111', status: 'in_progress' },
  { id: 't-bbb222', status: 'in_progress' },
  { id: 't-ccc333', status: 'in_progress' },
]

function viewOf(clauses: RequirementMarksView['clauses']): RequirementMarksView {
  return {
    requirementId: REQ_ID,
    clauses,
    unreceived: clauses.filter(c => c.state === 'unreceived').map(c => c.clause),
    available: true,
  }
}

describe('推导层：取消的卡不再算交付', () => {
  it('同一条 RTM 绑定，卡一取消 → 该条回落为未被接收（红）', () => {
    const refs = [{ id: 't-bbb222', requirement_refs: ['FR-4'] }]
    const before = clauseReceiveStatus(['FR-4'], refs, [{ id: 't-bbb222', status: 'in_progress' }])
    const after = clauseReceiveStatus(['FR-4'], refs, [{ id: 't-bbb222', status: 'canceled' }])
    expect(before[0].state).toBe('received')
    expect(after[0]).toEqual({ clause: 'FR-4', state: 'unreceived', by: [] })
  })
})

describe('文档面：渲染与幂等写入', () => {
  it('有未接收条款 → 表里标红、小结点名', () => {
    const md = renderDocMarks(viewOf([
      { clause: 'FR-1', state: 'received', by: ['t-aaa111'] },
      { clause: 'FR-4', state: 'unreceived', by: [] },
    ]))
    expect(md).toContain('| FR-4 | 🔴 **未被接收** | — |')
    expect(md).toContain('> 🔴 **未被接收（1 条）**：FR-4')
  })

  it('无缺口 → 明说全部有落点（不靠留白表达没问题）', () => {
    const md = renderDocMarks(viewOf([{ clause: 'FR-1', state: 'done', by: ['t-aaa111'] }]))
    expect(md).toContain('无未接收条款（1 条全部有落点）')
    expect(md).not.toContain('未被接收（')
  })

  it('文档在但没定义编号 → 说清没有编号，不冒充全部未接收', () => {
    expect(renderDocMarks(viewOf([]))).toContain('本需求文档尚未定义功能点编号')
  })

  it('需求文档缺失 → available=false 时也明说读不到，不冒充全部未接收', () => {
    expect(renderDocMarks({ requirementId: REQ_ID, clauses: [], unreceived: [], available: false }))
      .toContain('需求文档不存在')
  })

  it('插入点在 §6 之后、§7 之前，且不碰正文一个字', () => {
    const out = upsertMarksBlock(REQUIREMENT_MD, renderDocMarks(viewOf([{ clause: 'FR-1', state: 'received', by: ['t-aaa111'] }])))
    expect(out.indexOf(MARKS_BEGIN)).toBeLessThan(out.indexOf('## 7. 非功能需求'))
    expect(out.indexOf('## 6. 功能点')).toBeLessThan(out.indexOf(MARKS_BEGIN))
    expect(out).toContain('**FR-4 三段可追溯**：从一条功能点定位到卡与证据。')
  })

  it('重复写入是替换不是追加（幂等：标记只出现一次）', () => {
    const once = upsertMarksBlock(REQUIREMENT_MD, renderDocMarks(viewOf([{ clause: 'FR-1', state: 'received', by: [] }])))
    const twice = upsertMarksBlock(once, renderDocMarks(viewOf([{ clause: 'FR-1', state: 'unreceived', by: [] }])))
    expect(twice.split(MARKS_BEGIN)).toHaveLength(2)
    expect(twice).toContain('未被接收')
  })

  it('找不到 §6 锚点 → 退化为文末追加，绝不覆盖正文', () => {
    const plain = '# 无编号章节\n\n正文不许丢\n'
    const out = upsertMarksBlock(plain, renderDocMarks(viewOf([{ clause: 'FR-1', state: 'unreceived', by: [] }])))
    expect(out).toContain('正文不许丢')
    expect(hasMarksBlock(out)).toBe(true)
  })

  it('回读机器段 → 逐条状态（供复盘脚本消费）', () => {
    const out = upsertMarksBlock(REQUIREMENT_MD, renderDocMarks(viewOf([
      { clause: 'FR-1', state: 'received', by: ['t-aaa111'] },
      { clause: 'FR-4', state: 'unreceived', by: [] },
    ])))
    const states = readMarksBlockStates(out)
    expect(states).toHaveLength(2)
    expect(states[0]).toEqual({ clause: 'FR-1', state: '✅ 已接收', by: 't-aaa111' })
    expect(states[1].clause).toBe('FR-4')
    expect(states[1].state).toContain('未被接收')
  })
})

describe('看板面：同一视图的 HTML 渲染', () => {
  it('未被接收行带红类，且红名单写进摘要行', () => {
    const html = renderKanbanMarks(viewOf([
      { clause: 'FR-1', state: 'received', by: ['t-aaa111'] },
      { clause: 'FR-4', state: 'unreceived', by: [] },
    ]))
    expect(html).toContain('dsh-pm-mk-row is-unreceived')
    expect(html).toContain('🔴 未被接收 1 条：FR-4')
  })

  it('无缺口 → 明说全部有落点', () => {
    const html = renderKanbanMarks(viewOf([{ clause: 'FR-1', state: 'done', by: ['t-aaa111'] }]))
    expect(html).toContain('全部有落点')
    expect(html).not.toContain('is-unreceived')
  })

  it('读不到条款数据 → 明说读不到，不冒充全部未接收', () => {
    const html = renderKanbanMarks({ requirementId: REQ_ID, clauses: [], unreceived: [], available: false })
    expect(html).toContain('读不到条款数据')
  })
})

describe('**验收场景**：取消一张卡的交付 → 两个面同时回落为「未被接收（红）」', () => {
  it('取消前：需求文档与看板都无红', async () => {
    const { docs, store } = fakeDocs({ [DOC]: REQUIREMENT_MD, [DEC]: DECOMP_MD })
    await syncRequirementMarks({ docs } as never, REQ, TASKS_BEFORE)
    expect(store[DOC]).toContain('无未接收条款')
    const view = await assembleRequirementMarks({ docs } as never, REQ, TASKS_BEFORE)
    expect(view.unreceived).toEqual([])
    expect(renderKanbanMarks(view)).not.toContain('is-unreceived')
  })

  it('取消后：requirement.md 与看板同一批条款都标红（两面同源，不会一半盲）', async () => {
    const { docs, store } = fakeDocs({ [DOC]: REQUIREMENT_MD, [DEC]: DECOMP_MD })
    await syncRequirementMarks({ docs } as never, REQ, TASKS_AFTER)
    expect(store[DOC]).toContain('| FR-4 | 🔴 **未被接收** | — |')
    expect(store[DOC]).toContain('> 🔴 **未被接收（1 条）**：FR-4')
    const view = await assembleRequirementMarks({ docs } as never, REQ, TASKS_AFTER)
    expect(view.unreceived).toEqual(['FR-4'])
    expect(renderKanbanMarks(view)).toContain('未被接收 1 条：FR-4')
  })

  it('内容没变 → 不写盘（synced=false），避免文档 mtime 抖动', async () => {
    const { docs } = fakeDocs({ [DOC]: REQUIREMENT_MD, [DEC]: DECOMP_MD })
    const first = await syncRequirementMarks({ docs } as never, REQ, TASKS_AFTER)
    const second = await syncRequirementMarks({ docs } as never, REQ, TASKS_AFTER)
    expect(first.synced).toBe(true)
    expect(second.synced).toBe(false)
    expect(second.unreceived).toEqual(['FR-4'])
  })

  it('需求文档不存在 → 静默跳过（不要为不存在的文档造一个）', async () => {
    const { docs, store } = fakeDocs({ [DEC]: DECOMP_MD })
    const r = await syncRequirementMarks({ docs } as never, REQ, TASKS_AFTER)
    expect(r.synced).toBe(false)
    expect(store[DOC]).toBeUndefined()
  })
})
