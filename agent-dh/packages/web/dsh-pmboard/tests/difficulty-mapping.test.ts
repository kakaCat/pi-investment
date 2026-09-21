/**
 * 难度取词映射测试（REQ-e3b6a0 t6 / FR-4 / NFR-4）。
 *
 * 锁三件事：
 *  ① 四档 → 两档的映射覆盖 shared 的全部 PromptDifficulty 枚举值（用真实枚举遍历，防"少映射一档"）；
 *  ② 与文本推断冲突时**取重不取轻**；
 *  ③ 未声明时行为与改造前完全一致（向后兼容：仍按文本推断，无推断则走 DEFAULT）。
 *
 * @module dsh-pmboard/tests/difficulty-mapping
 */
import { describe, it, expect } from 'vitest'
import {
  difficultyFromDeclaredPrompt,
  heavierDifficulty,
} from '../src/domain/prompt/difficulty-mapping.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'
import { ALL_PROMPT_DIFFICULTIES } from '../src/shared/protocol.js'

// 命中 heavy 推断规则的文本（动架构 / 跨多子系统：规则见 difficulty-inference.ts）
const HEAVY_TEXT = '本需求要动架构并做分层重构，同时改变接口契约'
const LIGHT_TEXT = '把按钮文案改一下'

const base = { stage: 'design' as const, category: 'feature' as const }

describe('四档 → 两档映射', () => {
  it('覆盖 shared 的全部 PromptDifficulty 枚举值（少映射一档即红）', () => {
    const mapped = ALL_PROMPT_DIFFICULTIES.map(d => difficultyFromDeclaredPrompt(d))
    expect(mapped).toEqual(['light', 'light', 'heavy', 'heavy'])
    expect(mapped.every(x => x !== undefined)).toBe(true)
  })

  it('未声明 / 无法识别 → undefined（交给文本推断，不静默回落 light）', () => {
    expect(difficultyFromDeclaredPrompt(undefined)).toBeUndefined()
    expect(difficultyFromDeclaredPrompt('')).toBeUndefined()
    expect(difficultyFromDeclaredPrompt('unknown')).toBeUndefined()
    expect(difficultyFromDeclaredPrompt('EXPERT')).toBeUndefined() // 大小写不宽松匹配
  })

  it('取重不取轻', () => {
    expect(heavierDifficulty('light', 'light')).toBe('light')
    expect(heavierDifficulty('light', 'heavy')).toBe('heavy')
    expect(heavierDifficulty('heavy', 'light')).toBe('heavy')
    expect(heavierDifficulty('heavy', 'heavy')).toBe('heavy')
  })
})

describe('resolveStagePrompt 消费声明难度', () => {
  it('声明 expert（→heavy）→ routeKey 含 heavy，即便文本看着轻', () => {
    const r = resolveStagePrompt({
      ...base,
      declaredDifficulty: difficultyFromDeclaredPrompt('expert'),
      requirement: { title: LIGHT_TEXT, description: LIGHT_TEXT },
    })
    expect(r.routeKey.split('/')[1]).toBe('heavy')
  })

  it('声明 simple（→light）→ routeKey 含 light', () => {
    const r = resolveStagePrompt({
      ...base,
      declaredDifficulty: difficultyFromDeclaredPrompt('simple'),
    })
    expect(r.routeKey.split('/')[1]).toBe('light')
  })

  it('声明 simple 但文本推断 heavy → 取重不取轻（heavy）', () => {
    const r = resolveStagePrompt({
      ...base,
      declaredDifficulty: difficultyFromDeclaredPrompt('simple'),
      requirement: { title: HEAVY_TEXT, description: HEAVY_TEXT },
    })
    expect(r.routeKey.split('/')[1]).toBe('heavy')
    expect(r.difficultyReasons?.join(' | ')).toContain('取重不取轻')
  })

  it('声明 advanced 但文本推断 light → 取重不取轻（heavy）', () => {
    const r = resolveStagePrompt({
      ...base,
      declaredDifficulty: difficultyFromDeclaredPrompt('advanced'),
      requirement: { title: LIGHT_TEXT, description: LIGHT_TEXT },
    })
    expect(r.routeKey.split('/')[1]).toBe('heavy')
  })

  it('显式 difficulty 优先于声明档（既有语义不变）', () => {
    const r = resolveStagePrompt({
      ...base,
      difficulty: 'light',
      declaredDifficulty: difficultyFromDeclaredPrompt('expert'),
      requirement: { title: HEAVY_TEXT, description: HEAVY_TEXT },
    })
    expect(r.routeKey.split('/')[1]).toBe('light')
  })

  it('向后兼容：未声明 + 无需求实质 → DEFAULT（light），且不产生 difficultyReasons', () => {
    const r = resolveStagePrompt({ ...base })
    expect(r.routeKey.split('/')[1]).toBe('light')
    expect(r.difficultyReasons).toBeUndefined()
  })

  it('向后兼容：未声明 + 文本推断 heavy → heavy（原行为不变）', () => {
    const r = resolveStagePrompt({ ...base, requirement: { title: HEAVY_TEXT, description: HEAVY_TEXT } })
    expect(r.routeKey.split('/')[1]).toBe('heavy')
  })

  it('声明档会进留痕依据（difficultyReasons）', () => {
    const r = resolveStagePrompt({
      ...base,
      declaredDifficulty: difficultyFromDeclaredPrompt('standard'),
    })
    expect(r.difficultyReasons?.join(' | ')).toContain('声明难度已映射为取词档 light')
  })
})
