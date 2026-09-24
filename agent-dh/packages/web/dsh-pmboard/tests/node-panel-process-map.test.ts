/**
 * 「执行流程」对照表防漂移守护（REQ-260923134706-e72f / FR-6）。
 *
 * 锁死三件事：
 *  1. STAGE_PROCESS 覆盖全部 7 个 MainStageKey；draft 无阶段提示词 → promptRefs 为空（如实）。
 *  2. 每条规定动作的 cite 必须能在该阶段片段语料（src/domain/prompt/fragments/<stage>/**.md）里找到——
 *     提示词纪律改了而对照表没跟上（或反之）时本测试变红。
 *  3. resolveFragmentRef 的「路由壳」判定与生成库 fragments.ts 的真实形状一致
 *     （text==='' 且带 include ⇔ 三段非 overrides id）；canonicalPromptRefs 指向的文件全部存在。
 */
import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import {
  STAGE_PROCESS,
  canonicalPromptRefs,
  resolveFragmentRef,
} from '../src/client/node-panel-process.js'
import { GENERATED_FRAGMENTS } from '../src/domain/prompt/generated/fragments.js'
import { ALL_STAGE_KEYS } from '../src/shared/protocol.js'

const ROOT = join(__dirname, '..')
const FRAGMENTS_DIR = join(ROOT, 'src/domain/prompt/fragments')

function collectMarkdown(dir: string, acc: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) collectMarkdown(p, acc)
    else if (name.endsWith('.md')) acc.push(readFileSync(p, 'utf8'))
  }
  return acc
}

describe('STAGE_PROCESS 覆盖与 draft 如实', () => {
  it('覆盖全部 7 个 MainStageKey', () => {
    for (const stage of ALL_STAGE_KEYS) {
      expect(STAGE_PROCESS[stage as keyof typeof STAGE_PROCESS], stage).toBeDefined()
      expect(STAGE_PROCESS[stage as keyof typeof STAGE_PROCESS].actions.length, stage + ' 至少一条规定动作').toBeGreaterThan(0)
    }
  })

  it('draft 无阶段提示词 → canonicalPromptRefs 为空', () => {
    expect(canonicalPromptRefs('draft', 'feature')).toEqual([])
  })
})

describe('cite 防漂移：规定动作锚点必须真实存在于阶段片段语料', () => {
  for (const stage of ALL_STAGE_KEYS) {
    if (stage === 'draft') continue // draft 无片段语料，cite 留空由本测试跳过
    it(stage + '：每条 cite 都能在片段语料中找到', () => {
      const corpus = collectMarkdown(join(FRAGMENTS_DIR, stage)).join('\n')
      expect(corpus.length, stage + ' 片段语料非空').toBeGreaterThan(0)
      for (const a of STAGE_PROCESS[stage as keyof typeof STAGE_PROCESS].actions) {
        expect(a.cite.length, stage + ' 动作「' + a.label + '」的 cite 非空').toBeGreaterThan(0)
        expect(corpus.includes(a.cite), stage + ' 语料中找不到 cite「' + a.cite + '」（提示词纪律已改？对照表须同步）').toBe(true)
      }
    })
  }
})

describe('resolveFragmentRef 与生成库形状一致', () => {
  it('每个生成片段：shell ⇔ text 为空且带 include', () => {
    for (const frag of Object.values(GENERATED_FRAGMENTS)) {
      const id = (frag as { id: string }).id
      const resolved = resolveFragmentRef(id)
      const inc = (frag as unknown as { include?: readonly string[] }).include
      const isShell = ((frag as { text?: string }).text ?? '') === '' && Array.isArray(inc) && (inc as readonly string[]).length > 0
      expect(resolved.kind, id).toBe(isShell ? 'shell' : 'file')
    }
  })

  it('canonicalPromptRefs 指向的文件全部存在（6 阶段 × 6 类型）', () => {
    const categories = ['feature', 'bug', 'doc', 'refactor', 'spike', 'chore']
    for (const stage of ALL_STAGE_KEYS) {
      if (stage === 'draft') continue
      for (const cat of categories) {
        for (const ref of canonicalPromptRefs(stage as Exclude<(typeof ALL_STAGE_KEYS)[number], 'draft'>, cat)) {
          const p = join(FRAGMENTS_DIR, ref.id + '.md')
          expect(existsSync(p), p).toBe(true)
        }
      }
    }
  })
})
