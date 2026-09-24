/**
 * template-clause-gate（REQ-260923134706-e72f / t7，FR-10）：模板与 G2 门禁矛盾消除验证。
 *
 * 矛盾背景：brainstorming 模板指导 agent 写 requirement.md，却不告诉它 G2 clause 门禁
 * （DEF_LINE_RE）只认 `**<前缀>-N: 名称**` 这种定义行，也不给 feature 类型列出
 * requiredRootSectionsFor('feature') 的必填节——于是 agent 产出的需求文档条款解析不到、
 * 缺必填节，G2 反复拦截（"模板和代码门禁互相矛盾"）。
 *
 * 本测试锁死修复：6 份 brainstorming 模板各含一条门禁可解析的示范定义行（前缀按类型），
 * feature 模板覆盖全部必填根节，bug 模板无 G1/G2 撞名编号。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { DEF_LINE_RE, ROOT_PREFIXES } from '../src/application/internal/doc-parse.js'
import { requiredRootSectionsFor } from '../src/application/internal/category-doc-sets.js'

const DIR = join(__dirname, '..', 'src', 'domain', 'prompt', 'fragments', 'brainstorming')
const CATEGORY_PREFIX: Record<string, string> = {
  feature: 'FR', bug: 'BUG', refactor: 'RF', spike: 'SP', doc: 'DOC', chore: 'CH',
}

function readTemplate(cat: string): string {
  return readFileSync(join(DIR, cat + '.md'), 'utf8')
}

describe('FR-10 模板与 G2 门禁对齐', () => {
  it('6 份模板各含一条 DEF_LINE_RE 可解析的示范定义行，前缀按类型', () => {
    for (const [cat, prefix] of Object.entries(CATEGORY_PREFIX)) {
      const text = readTemplate(cat)
      // 找出所有被 DEF_LINE_RE 认得的定义行
      const hits = text.split('\n')
        .map(l => l.match(DEF_LINE_RE))
        .filter((m): m is RegExpMatchArray => m !== null)
      expect(hits.length, cat + ' 应有 ≥1 条可解析定义行').toBeGreaterThanOrEqual(1)
      // 前缀必须是该类型的根前缀（FR/BUG/RF/SP/DOC/CH）
      for (const m of hits) {
        const id = m[1]
        expect(id.startsWith(prefix + '-'), cat + ' 定义行前缀应为 ' + prefix + '，实得 ' + id).toBe(true)
      }
    }
  })

  it('示范定义行独立成行、带「名称」段（编号后有内容，非空壳）', () => {
    for (const [cat, prefix] of Object.entries(CATEGORY_PREFIX)) {
      const text = readTemplate(cat)
      // 示范定义行 = 独立成行的列表项定义行（前面有「示范」引导段，不在 checklist 复选框内）
      const example = text.split('\n').find(l => {
        const m = l.match(DEF_LINE_RE)
        return m !== null && m[1].startsWith(prefix + '-') && !l.includes('[ ]')
      })
      expect(example, cat + ' 应有独立成行的示范定义行').toBeDefined()
      // 编号后必须跟非空白（: 名称 / ：名称 / 名称）
      const m = example!.match(DEF_LINE_RE)!
      const after = example!.slice(example!.indexOf(m[1]) + m[1].length)
      expect(after.trim().length, cat + ' 示范行编号后应有名称').toBeGreaterThan(0)
    }
  })

  it('feature 模板覆盖 requiredRootSectionsFor(\'feature\') 全部必填节', () => {
    const required = requiredRootSectionsFor('feature')
    expect(required).toContain('产品定义')
    const text = readTemplate('feature')
    for (const sec of required) {
      expect(text.includes(sec), 'feature 模板应提到必填节「' + sec + '」').toBe(true)
    }
  })

  it('bug 模板不把 G1/G2 当条款编号（无加粗 G 子句/目标表编号）', () => {
    const text = readTemplate('bug')
    // 允许提及闸门名「G2 clause 门禁」；禁止把 G1/G2 用作条款/目标编号（**G1、G2:、G1.）
    expect(text).not.toMatch(/\*\*G[12]\b/)
    expect(text).not.toMatch(/\bG[12]\s*[:：.]/)
  })

  it('ROOT_PREFIXES 覆盖六类前缀', () => {
    for (const p of Object.values(CATEGORY_PREFIX)) {
      expect(ROOT_PREFIXES).toContain(p)
    }
  })
})
