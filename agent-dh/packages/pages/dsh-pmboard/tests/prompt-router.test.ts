/**
 * resolveStagePrompt 路由解析单测（REQ-422af1 t3）。
 *
 * 覆盖：五种命中层级（①精确 / ②难度档 / ③类型档 / ④节点兜底 / ⑤全局铁律合并）、
 * 6×2×6 组合无空串、预算裁剪（floor 永不裁 / 连 floor 超限返回结构化标记）、
 * include 展开去重、routeKey 与 hitLevel 契约。
 *
 * 五种层级用**合成分片库**构造（router 是纯函数、库由调用方注入）——这样不会因为
 * 真库当前只有 P0 兜底档而无法验证回退链。
 */
import { describe, it, expect } from 'vitest'
import {
  resolveFragmentPlan,
  resolveStagePrompt,
  FRAGMENT_LIBRARY,
  PROMPT_STAGES,
  DIFFICULTIES,
  CATEGORIES,
  type Fragment,
} from '../src/domain/prompt/index.js'

type Spec = Partial<Fragment> & { id: string; stage: Fragment['stage']; difficulty: Fragment['difficulty']; category: Fragment['category'] }

function frag(spec: Spec): Fragment {
  return { priority: 10, text: 'TEXT:' + spec.id, ...spec }
}

describe('回退链：五种命中层级', () => {
  it('① 精确命中 (stage,difficulty,category)', () => {
    const lib = [
      frag({ id: 'brainstorming/heavy/bug', stage: 'brainstorming', difficulty: 'heavy', category: 'bug' }),
      frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor' }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', difficulty: 'heavy', category: 'bug' })
    expect(r.hitLevel).toBe(1)
    expect(r.routeKey).toBe('brainstorming/heavy/bug')
    expect(r.fragmentIds).toContain('brainstorming/heavy/bug')
  })

  it('② 难度档回退 (stage,difficulty,*)', () => {
    const lib = [
      frag({ id: 'brainstorming/heavy', stage: 'brainstorming', difficulty: 'heavy', category: '*' }),
      frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor' }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', difficulty: 'heavy', category: 'chore' })
    expect(r.hitLevel).toBe(2)
    expect(r.fragmentIds).toContain('brainstorming/heavy')
  })

  it('③ 类型档回退 (stage,*,category)', () => {
    const lib = [
      frag({ id: 'brainstorming/bug', stage: 'brainstorming', difficulty: '*', category: 'bug' }),
      frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor' }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', difficulty: 'heavy', category: 'bug' })
    expect(r.hitLevel).toBe(3)
    expect(r.fragmentIds).toContain('brainstorming/bug')
  })

  it('④ 节点兜底 (stage,*,*)', () => {
    const lib = [frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor' })]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', difficulty: 'heavy', category: 'bug' })
    expect(r.hitLevel).toBe(4)
    expect(r.fragmentIds).toEqual(['brainstorming/default'])
  })

  it('⑤ 全局铁律是**合并**（不是替代）：节点内容与全局内容并存', () => {
    const lib = [
      frag({ id: 'design/default', stage: 'design', difficulty: '*', category: '*', priority: 'floor' }),
      frag({ id: 'common/iron-rules', stage: '*', difficulty: '*', category: '*', priority: 'floor', text: 'IRON' }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'design', difficulty: 'heavy', category: 'bug' })
    expect(r.hitLevel).toBe(4)
    // 顺序契约：①-④ 选中片段在前、⑤ 全局铁律在后（见 router.ts 的顺序说明）
    expect(r.fragmentIds).toEqual(['design/default', 'common/iron-rules'])
    expect(r.text).toContain('IRON')
  })

  it('⑤ 无任何节点命中时 hitLevel=5（只并入全局）', () => {
    const lib = [frag({ id: 'common/iron-rules', stage: '*', difficulty: '*', category: '*', priority: 'floor', text: 'IRON' })]
    const r = resolveFragmentPlan(lib, { stage: 'accepting', difficulty: 'light', category: 'doc' })
    expect(r.hitLevel).toBe(5)
    expect(r.fragmentIds).toEqual(['common/iron-rules'])
    expect(r.text).toBe('IRON')
  })

  it('难度优先于类型：②与③同时可得时取②', () => {
    const lib = [
      frag({ id: 'brainstorming/heavy', stage: 'brainstorming', difficulty: 'heavy', category: '*' }),
      frag({ id: 'brainstorming/bug', stage: 'brainstorming', difficulty: '*', category: 'bug' }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', difficulty: 'heavy', category: 'bug' })
    expect(r.hitLevel).toBe(2)
    expect(r.fragmentIds).toEqual(['brainstorming/heavy'])
  })
})

describe('覆盖完备：6 节点 × 2 难度 × 6 类型 全部非空', () => {
  it('真分片库下 0 例空串', () => {
    const empty: string[] = []
    for (const stage of PROMPT_STAGES) {
      for (const difficulty of DIFFICULTIES) {
        for (const category of CATEGORIES) {
          const r = resolveStagePrompt({ stage, difficulty, category })
          if (r.text.length === 0) empty.push(stage + '/' + difficulty + '/' + category)
        }
      }
    }
    expect(empty, '以下组合解析为空串：\n' + empty.join('\n')).toEqual([])
  })

  it('routeKey 恒为 stage/difficulty/category（缺省值补齐）', () => {
    const r = resolveStagePrompt({ stage: 'implementing' })
    expect(r.routeKey).toBe('implementing/light/feature')
  })
})

describe('预算与保底（INV-3）', () => {
  it('超预算裁非保底片段，floor 仍在 fragmentIds', () => {
    const lib = [
      frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor', text: 'FLOOR' }),
      frag({ id: 'brainstorming/extra', stage: 'brainstorming', difficulty: '*', category: '*', priority: 10, text: 'X'.repeat(200) }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', budget: 10 })
    expect(r.trimmed).toEqual(['brainstorming/extra'])
    expect(r.fragmentIds).toContain('brainstorming/default')
    expect(r.text).toBe('FLOOR')
    expect(r.overBudget).toBeUndefined()
  })

  it('连 floor 都超预算 → 结构化超限标记，绝不静默丢掉 floor', () => {
    const lib = [
      frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor', text: 'F'.repeat(100) }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', budget: 5 })
    expect(r.overBudget).toEqual({ reason: 'floor-exceeds-budget', floorChars: 100, budget: 5 })
    expect(r.fragmentIds).toContain('brainstorming/default')
    expect(r.text.length).toBe(100)
  })

  it('缺省预算下 heavy 主 skill 全文注入且不触发裁剪（t7：重档原文不裁）', () => {
    const r = resolveStagePrompt({ stage: 'brainstorming', difficulty: 'heavy', category: 'bug' })
    // vendor 原文 brainstorming = 15,456 字符；heavy = 原文 + overrides + common/iron-rules
    expect(r.charCount).toBeGreaterThan(15456)
    expect(r.overBudget).toBeUndefined()
    expect(r.trimmed).toEqual([])
    expect(r.fragmentIds).toContain('brainstorming/heavy')
    expect(r.fragmentIds).toContain('brainstorming/heavy/overrides')
    expect(r.fragmentIds).toContain('common/iron-rules')
  })
})

describe('去重与 include 展开', () => {
  it('同一 id 被重复 include → fragmentIds 只出现一次', () => {
    const lib = [
      frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor', include: ['common/extra', 'common/extra'] }),
      frag({ id: 'common/extra', stage: '*', difficulty: '*', category: '*', priority: 'floor', text: 'EXTRA' }),
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming' })
    expect(r.fragmentIds.filter((id) => id === 'common/extra').length).toBe(1)
    expect(r.fragmentIds).toContain('common/extra')
  })

  it('include 指向不存在的 id → 响亮抛错（不静默忽略）', () => {
    const lib = [
      frag({ id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor', include: ['nope/missing'] }),
    ]
    expect(() => resolveFragmentPlan(lib, { stage: 'brainstorming' })).toThrow(/nope\/missing/)
  })

  it('真分片库 id 唯一（门禁 4 的前置）', () => {
    const ids = FRAGMENT_LIBRARY.map((f) => f.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})
