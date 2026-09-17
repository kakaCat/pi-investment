/**
 * 类型档（六节点 × 六类型）单测（REQ-422af1 t8）。
 *
 * 断言锚点：
 *   ① 同一 (stage,difficulty) 下六个类型解析出的文本**两两不同**（含 bug ≠ feature）；
 *   ② 每类型命中其必要关键词（逐类型断言：bug→先复现/回归测试；refactor→行为等价；
 *      feature→接口/数据契约；spike→回答一个问题；doc→只改文档；chore→最小改动）；
 *   ③ 类型差异是**追加**：节点难度档仍在 fragmentIds（没被 ① 精确命中挤掉），hitLevel=①；
 *   ④ 回退链 ③ 层 (stage,*,category) 也可用（合成库验证 hitLevel=③；真库确有该分片）；
 *   ⑤ 无孤岛：36 份类型档都被路由命中（合并进六门禁第 4 条的口径）；
 *   ⑥ 源文件齐备：六节点 × 六类型 = 36 份 md 在盘上（decomposing 亦为自写档）。
 */
import { describe, it, expect } from 'vitest'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import {
  resolveStagePrompt,
  resolveFragmentPlan,
  FRAGMENT_LIBRARY,
  PROMPT_STAGES,
  DIFFICULTIES,
  CATEGORIES,
  type Category,
  type Fragment,
} from '../src/domain/prompt/index.js'

const FRAGMENTS_DIR = fileURLToPath(new URL('../src/domain/prompt/fragments', import.meta.url))

/** 每类型的必要关键词（design/fragments.md §6；t8 验收口径逐字）。 */
const REQUIRED_KEYWORDS: Readonly<Record<Category, readonly string[]>> = {
  bug: ['先复现', '回归测试'],
  refactor: ['行为等价'],
  feature: ['接口', '数据契约'],
  spike: ['回答一个问题'],
  doc: ['只改文档'],
  chore: ['最小改动'],
}

/** 该 (stage,difficulty) 下六个类型的解析文本（顺序 = CATEGORIES）。 */
function textsFor(stage: string, difficulty: string): { category: Category; text: string }[] {
  return CATEGORIES.map((category) => ({
    category,
    text: resolveStagePrompt({ stage: stage as never, difficulty: difficulty as never, category }).text,
  }))
}

function fragmentById(id: string): Fragment {
  const f = FRAGMENT_LIBRARY.find((x) => x.id === id)
  if (f === undefined) throw new Error('找不到分片：' + id)
  return f
}

describe('① 同一 (stage,difficulty) 下类型文本两两不同（难度轴之外，类型轴生效）', () => {
  for (const stage of PROMPT_STAGES) {
    for (const difficulty of DIFFICULTIES) {
      it(stage + '/' + difficulty + '：六个类型解析出的文本两两不同', () => {
        const texts = textsFor(stage, difficulty)
        const uniq = new Set(texts.map((t) => t.text))
        const dup = texts.filter((t, i) => texts.findIndex((x) => x.text === t.text) !== i).map((t) => t.category)
        expect(uniq.size, stage + '/' + difficulty + ' 类型文本重复：' + dup.join(',')).toBe(CATEGORIES.length)
        // 验收口径点名：bug 与 feature 必须不同
        const bug = texts.find((t) => t.category === 'bug')!.text
        const feature = texts.find((t) => t.category === 'feature')!.text
        expect(bug, stage + '/' + difficulty + ' bug 与 feature 文本相同').not.toBe(feature)
      })
    }
  }
})

describe('② 每类型命中必要关键词（逐类型逐节点逐难度断言）', () => {
  for (const stage of PROMPT_STAGES) {
    for (const difficulty of DIFFICULTIES) {
      for (const category of CATEGORIES) {
        it(stage + '/' + difficulty + '/' + category + ' 含必要关键词 ' + REQUIRED_KEYWORDS[category].join('、'), () => {
          const text = resolveStagePrompt({ stage, difficulty, category }).text
          for (const kw of REQUIRED_KEYWORDS[category]) {
            expect(text, stage + '/' + difficulty + '/' + category + ' 缺「' + kw + '」').toContain(kw)
          }
        })
      }
    }
  }
})

describe('③ 类型差异是追加：节点难度档与类型档同时在 fragmentIds，且命中回退链 ①', () => {
  for (const stage of PROMPT_STAGES) {
    for (const difficulty of DIFFICULTIES) {
      for (const category of CATEGORIES) {
        it(stage + '/' + difficulty + '/' + category + ' → hitLevel=①，含节点难度档与类型档', () => {
          const r = resolveStagePrompt({ stage, difficulty, category })
          expect(r.hitLevel, stage + '/' + difficulty + '/' + category + ' 应精确命中 ①').toBe(1)
          // 类型差异是"追加要求"，不能挤掉节点 light/heavy 内容
          expect(r.fragmentIds, '缺节点难度档').toContain(stage + '/' + difficulty)
          expect(r.fragmentIds, '缺类型档').toContain(stage + '/' + category)
          expect(r.fragmentIds, '缺 ⑤ 铁律').toContain('common/iron-rules')
          if (difficulty === 'heavy' && existsSync(join(FRAGMENTS_DIR, stage, 'heavy', 'overrides.md'))) {
            expect(r.fragmentIds).toContain(stage + '/heavy/overrides')
          }
        })
      }
    }
  }
})

describe('④ 回退链 ③ 层 (stage,*,category) 也可用（类型档不是只挂在 ① 上）', () => {
  it('无难度档时，(stage,*,category) 在 ③ 层命中', () => {
    const lib: Fragment[] = [
      { id: 'brainstorming/bug', stage: 'brainstorming', difficulty: '*', category: 'bug', priority: 10, text: 'BUG-DELTA' },
      { id: 'brainstorming/default', stage: 'brainstorming', difficulty: '*', category: '*', priority: 'floor', text: 'FLOOR' },
    ]
    const r = resolveFragmentPlan(lib, { stage: 'brainstorming', difficulty: 'heavy', category: 'bug' })
    expect(r.hitLevel).toBe(3)
    expect(r.fragmentIds).toContain('brainstorming/bug')
    expect(r.text).toContain('BUG-DELTA')
  })

  it('真库中 36 份类型档都注册在 (stage,*,category)', () => {
    for (const stage of PROMPT_STAGES) {
      for (const category of CATEGORIES) {
        const f = fragmentById(stage + '/' + category)
        expect(f.stage, stage + '/' + category).toBe(stage)
        expect(f.difficulty, stage + '/' + category).toBe('*')
        expect(f.category, stage + '/' + category).toBe(category)
      }
    }
  })
})

describe('⑤ 无孤岛：36 份类型档都被路由命中', () => {
  it('6×2×6 解析覆盖全部分片（含 36 份类型档与其 ① 路由壳）', () => {
    const hit = new Set<string>()
    for (const stage of PROMPT_STAGES) {
      for (const difficulty of DIFFICULTIES) {
        for (const category of CATEGORIES) {
          for (const id of resolveStagePrompt({ stage, difficulty, category }).fragmentIds) hit.add(id)
        }
      }
    }
    const islands = FRAGMENT_LIBRARY.filter((f) => !hit.has(f.id)).map((f) => f.id)
    expect(islands, '以下分片没有任何路由命中（孤岛）：\n' + islands.join('\n')).toEqual([])
    const missing = PROMPT_STAGES.flatMap((s) => CATEGORIES.map((c) => s + '/' + c)).filter((id) => !hit.has(id))
    expect(missing, '类型档未被命中：\n' + missing.join('\n')).toEqual([])
  })
})

describe('⑥ 源文件齐备：六节点 × 六类型 = 36 份类型档', () => {
  it('每份 <stage>/<category>.md 在盘上', () => {
    const missing: string[] = []
    for (const stage of PROMPT_STAGES) {
      for (const category of CATEGORIES) {
        if (!existsSync(join(FRAGMENTS_DIR, stage, category + '.md'))) missing.push(stage + '/' + category + '.md')
      }
    }
    expect(missing, '缺类型档源文件：\n' + missing.join('\n')).toEqual([])
  })
})
