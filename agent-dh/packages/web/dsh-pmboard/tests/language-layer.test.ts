/**
 * 语言强度按层 + 设计章节可追溯（REQ-d3e61a T-12 / serve FR-5, FR-8）
 *
 * 刻意只校验「每节有没有 serves」，**不校验文风**——文风是提示词分片给人的指引，
 * 机器判散文好坏就是形式主义。
 */
import { describe, expect, it } from 'vitest'
import { parseDocument, checkDesignSectionsHaveServes } from '../src/application/internal/content-gates.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'

const doc = (...lines: string[]) => lines.join('\n')

const GOOD_DESIGN = doc(
  '---',
  'req_id: REQ-x',
  'requirement_refs: [FR-12]',
  '---',
  '# 架构设计（serves: FR-12, FR-13）',
  '',
  '## D-ARCH-1 三级门禁架构 `serves: FR-12`',
  '正文……',
  '',
  '## D-ARCH-2 模块划分 `serves: FR-12`',
  '正文……',
)

const BAD_DESIGN = doc(
  '# 架构设计',
  '',
  '## D-ARCH-1 三级门禁架构 `serves: FR-12`',
  '',
  '## D-ARCH-2 模块划分',
  '（这一节忘了标 serves）',
)

describe('checkDesignSectionsHaveServes（FR-5）', () => {
  it('每节都标了 serves → 无缺失', () => {
    expect(checkDesignSectionsHaveServes(parseDocument(GOOD_DESIGN)).missing).toEqual([])
  })

  it('缺标注的章节被精确点出（孤儿章节）', () => {
    expect(checkDesignSectionsHaveServes(parseDocument(BAD_DESIGN)).missing).toEqual(['D-ARCH-2 模块划分'])
  })

  it('H1 文档标题不参与校验（文档级 serves 写在这里或 front-matter）', () => {
    const md = doc('# 架构设计（serves: FR-12）', '', '## D-DATA-1 编号模型 `serves: FR-2`')
    expect(checkDesignSectionsHaveServes(parseDocument(md)).missing).toEqual([])
  })

  it('代码块里的假章节不算（围栏陷阱回归）', () => {
    const md = doc('## D-ARCH-1 真章节 `serves: FR-12`', '', '```', '## 假章节', '```')
    expect(checkDesignSectionsHaveServes(parseDocument(md)).missing).toEqual([])
  })
})

describe('语言强度按层真的注入了吗（端到端）', () => {
  const dump = (stage: string, difficulty: string, category: string) =>
    JSON.stringify(resolveStagePrompt({ stage, difficulty, category } as any))

  it('design/light/feature 注入「章节可追溯」与「语言强度按层」', () => {
    const s = dump('design', 'light', 'feature')
    expect(s).toContain('每节必须标注服务哪条功能点')
    expect(s).toContain('语言强度按层')
  })

  it('design/heavy 也注入（措辞与 light 不同，断言其自身关键词）', () => {
    const s = dump('design', 'heavy', 'feature')
    expect(s).toContain('孤儿章节')
    expect(s).toContain('语言强度按层')
  })

  it('不越界：implementing 档不含 design 的语言强度条目', () => {
    expect(dump('implementing', 'light', 'feature')).not.toContain('语言强度按层')
  })
})
