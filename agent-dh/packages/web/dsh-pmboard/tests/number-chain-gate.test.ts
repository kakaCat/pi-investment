/**
 * 编号串联门禁单测（REQ-d3e61a T-4 / serve TC-010 编号族）
 *
 * 验收口径：给任一 TC-xxx 反查根编号 → 返回成功；serves 指向不存在编号 → 被拒且 dangling 非空。
 */
import { describe, expect, it } from 'vitest'
import {
  collectNumberedItems, checkNumberChainGate, traceNumber,
} from '../src/application/internal/content-gate-wiring.js'

const doc = (...lines: string[]) => lines.join('\n')

const REQ = doc(
  '---', 'req_id: REQ-t', '---', '# 需求', '',
  '## 6. 功能点', '',
  '**FR-1 覆盖门禁**：拆分时逐条核对。', '',
  '**FR-4 三段可追溯**：需求↔任务↔证据。', '',
  '**FR-9 三方一致性**：做的和说的对得上吗。',
)

const DESIGN_OK = doc(
  '---', 'requirement_refs: [FR-4]', '---',
  '# 架构设计', '',
  '## D-ARCH-1 三级门禁 `serves: FR-1, FR-4`', '正文。', '',
  '## D-ARCH-2 编号模型 `serves: FR-4`', '正文。',
)

const DESIGN_DANGLING = doc(
  '# 架构设计', '',
  '## D-ARCH-1 三级门禁 `serves: FR-4`', '正文。', '',
  '## D-ARCH-2 悬空章节 `serves: FR-99`', '正文。',
)

const fakeDocs = (files: Record<string, string>) => ({
  exists: (p: string) => Object.prototype.hasOwnProperty.call(files, p),
  read: async (p: string) => files[p] ?? '',
  list: (dir: string) => Object.keys(files)
    .filter(k => k.startsWith(dir + '/'))
    .map(k => ({ name: k.slice(dir.length + 1), isFile: true })),
})

const REQP = 'docs/requirements/REQ-t/requirement.md'
const live = { id: 'REQ-t', artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'x' }] } as any

describe('traceNumber（双向可查 —— 本条的真正价值）', () => {
  const items = [
    { id: 'FR-4', serves: [], kind: 'requirement' },
    { id: 'T-1', serves: ['FR-4'], kind: 'task' },
    { id: 'D-DATA-1', serves: ['FR-4', 'T-1'], kind: 'design' },
    { id: 'TC-007', serves: ['FR-4', 'D-DATA-1'], kind: 'testcase' },
  ]

  it('给任一 TC-xxx → 向上能反查到根编号 FR-4（返回成功）', () => {
    const r = traceNumber(items, 'TC-007')
    expect(r.up).toContain('FR-4')
    expect(r.up).toContain('D-DATA-1')
  })

  it('给根编号 → 向下列出全部子孙', () => {
    const r = traceNumber(items, 'FR-4')
    expect(r.down).toEqual(['D-DATA-1', 'T-1', 'TC-007'].sort())
  })

  it('未知编号 → 两边都空（不假装有）', () => {
    expect(traceNumber(items, 'FR-999')).toEqual({ down: [], up: [] })
  })
})

describe('collectNumberedItems', () => {
  it('需求条款（根）+ 设计章节（带 serves）都被收集', async () => {
    const items = await collectNumberedItems(
      fakeDocs({ [REQP]: REQ, 'docs/requirements/REQ-t/design/architecture.md': DESIGN_OK }),
      live,
    )
    const ids = items.map(i => i.id)
    expect(ids).toContain('FR-1')
    expect(ids).toContain('FR-9')
    expect(ids).toContain('D-ARCH-1')
    const arch = items.find(i => i.id === 'D-ARCH-1')
    expect(arch?.serves).toEqual(['FR-1', 'FR-4'])
  })
})

describe('checkNumberChainGate（TC-010 编号族）', () => {
  it('serves 指向不存在编号 → 被拒，dangling/gaps 非空', async () => {
    const r = await checkNumberChainGate(
      fakeDocs({ [REQP]: REQ, 'docs/requirements/REQ-t/design/architecture.md': DESIGN_DANGLING }),
      live,
    )
    expect(r.failure).toBeDefined()
    expect(r.failure?.code).toBe('dangling_reference')
    expect((r.failure?.gaps ?? []).length).toBeGreaterThan(0)
    expect((r.failure?.gaps ?? []).join(' ')).toContain('FR-99')
  })

  it('引用全部有效 → 不拒；无下游的根编号进 orphans（标红而非拦）', async () => {
    const r = await checkNumberChainGate(
      fakeDocs({ [REQP]: REQ, 'docs/requirements/REQ-t/design/architecture.md': DESIGN_OK }),
      live,
    )
    expect(r.failure).toBeUndefined()
    // FR-9 没有任何一节服务它 → 孤儿（应标红）
    expect(r.orphans).toContain('FR-9')
    // FR-1 / FR-4 有下游 → 不是孤儿
    expect(r.orphans).not.toContain('FR-1')
    expect(r.orphans).not.toContain('FR-4')
  })

  it('存量需求豁免 / 无编号条目 → 不拦（避免误拦）', async () => {
    const docs = fakeDocs({ [REQP]: REQ, 'docs/requirements/REQ-t/design/architecture.md': DESIGN_DANGLING })
    expect((await checkNumberChainGate(docs, { id: 'REQ-t', artifacts: undefined } as any)).failure).toBeUndefined()
    expect((await checkNumberChainGate(fakeDocs({}), live)).failure).toBeUndefined()
  })

  it('跨文档链路端到端：FR-4 的子孙能连到设计章节', async () => {
    const r = await checkNumberChainGate(
      fakeDocs({ [REQP]: REQ, 'docs/requirements/REQ-t/design/architecture.md': DESIGN_OK }),
      live,
    )
    const traced = traceNumber(r.items, 'FR-4')
    expect(traced.down).toContain('D-ARCH-1')
    expect(traced.down).toContain('D-ARCH-2')
  })
})
