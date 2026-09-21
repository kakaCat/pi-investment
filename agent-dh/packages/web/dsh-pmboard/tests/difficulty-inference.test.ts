/**
 * 难度推断单测（REQ-d3e61a T-15 / serve FR-16）
 *
 * 覆盖：四类 heavy 信号（动架构 / 改数据模型 / 新增子系统 / 跨多子系统）+ 规模信号、
 * 无信号回落缺省、以及「注入 vs 推断」不一致时的响亮提示。
 */
import { describe, expect, it } from 'vitest'
import { inferDifficulty, difficultyMismatch } from '../src/domain/prompt/difficulty-inference.js'
import { DEFAULT_DIFFICULTY } from '../src/domain/prompt/types.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'
import { injectionLogInputFromResolved } from '../src/application/internal/injection-log.js'

describe('inferDifficulty（FR-16：难度由需求实质推断，而非缺省值）', () => {
  it('① 动架构的需求 → heavy（这是 REQ-c9f899 被注入 light 的翻版）', () => {
    const r = inferDifficulty({
      title: '盯盘引擎重构',
      body: '这是一次架构重构：拆分触发-判据-投递-生命周期四层，调整模块划分与接口契约。',
    })
    expect(r.difficulty).toBe('heavy')
    expect(r.reasons.join(' ')).toContain('动架构')
    expect(r.reasons.join(' ')).toContain('架构')
  })

  it('② 改数据模型的 → heavy', () => {
    const r = inferDifficulty({ body: '新增四张表，并给两张现有表加列；需要写迁移脚本。' })
    expect(r.difficulty).toBe('heavy')
    expect(r.reasons.join(' ')).toContain('改数据模型')
  })

  it('③ 新增子系统的 → heavy', () => {
    const r = inferDifficulty({ body: '新增一个自愈服务，负责按日聚合统计。' })
    expect(r.difficulty).toBe('heavy')
    expect(r.reasons.join(' ')).toContain('新增子系统')
  })

  it('④ 跨多子系统（≥3 条不同路径）→ heavy', () => {
    const r = inferDifficulty({
      body: '涉及 src/application/internal、src/domain/prompt、src/adapters/outbound 三处。',
    })
    expect(r.difficulty).toBe('heavy')
    expect(r.reasons.join(' ')).toContain('跨多子系统')
  })

  it('跨子系统阈值：只提 1-2 条路径不算（避免单个路径就判 heavy）', () => {
    expect(inferDifficulty({ body: '只改 src/domain/prompt。' }).difficulty).toBe(DEFAULT_DIFFICULTY)
    expect(inferDifficulty({ body: '改 src/domain/prompt 与 src/domain/stage 两处。' }).difficulty).toBe(DEFAULT_DIFFICULTY)
  })

  it('⑤ 规模大（≥8 个功能点）→ heavy', () => {
    const body = Array.from({ length: 9 }, (_, i) => '- **FR-' + (i + 1) + ' 功能点**：说明。').join('\n')
    const r = inferDifficulty({ body })
    expect(r.difficulty).toBe('heavy')
    expect(r.reasons.join(' ')).toContain('规模大')
  })

  it('⑥ 无任何信号的小需求 → 回落缺省 light（不误判为大工程）', () => {
    const r = inferDifficulty({ title: '修正文案错别字', body: '把首页标题的错别字改掉。' })
    expect(r.difficulty).toBe(DEFAULT_DIFFICULTY)
    expect(r.reasons).toEqual([])
  })

  it('留痕：reasons 非空时含标签与证据片段', () => {
    const r = inferDifficulty({ body: '这是一次架构重构，改模块划分。' })
    expect(r.reasons.length).toBeGreaterThan(0)
    expect(r.reasons.some(x => x.includes('[') && x.includes('命中'))).toBe(true)
    const sig = r.signals.find(s => s.kind === 'architecture')
    expect(sig?.hit).toBe(true)
    expect((sig?.evidence ?? []).length).toBeGreaterThan(0)
  })
})

describe('端到端：需求实质真的驱动了注入难度（FR-16 的核心）', () => {
  it('标题含"重构" → 注入难度判为 heavy（而非缺省 light），且留痕带依据', () => {
    const resolved = resolveStagePrompt({
      stage: 'brainstorming',
      category: 'feature',
      requirement: { title: '盯盘引擎重构', description: '拆分四层、调整模块划分与接口契约。' },
    })
    expect(resolved.routeKey).toContain('heavy')
    expect((resolved.difficultyReasons ?? []).length).toBeGreaterThan(0)

    // 留痕自动带走依据（看板可查"这次为什么按 heavy 注入"）
    const entry = injectionLogInputFromResolved(resolved, 'w-test')
    expect(entry.difficulty).toBe('heavy')
    expect((entry.difficultyReasons ?? []).join(' ')).toContain('动架构')
  })

  it('不传 requirement → 行为与既有完全一致（向后兼容，零影响）', () => {
    const resolved = resolveStagePrompt({ stage: 'brainstorming', category: 'feature' })
    expect(resolved.routeKey).toContain('light')
    expect(resolved.difficultyReasons).toBeUndefined()
  })

  it('小需求无 heavy 信号 → 仍 light（不误判成大工程）', () => {
    const resolved = resolveStagePrompt({
      stage: 'brainstorming',
      category: 'doc',
      requirement: { title: '修正错别字', description: '把首页标题的错别字改掉。' },
    })
    expect(resolved.routeKey).toContain('light')
  })

  it('显式难度与推断冲突 → 不静默：显式优先，但依据里带响亮告警', () => {
    const resolved = resolveStagePrompt({
      stage: 'brainstorming',
      category: 'feature',
      difficulty: 'light',
      requirement: { title: '引擎重构', description: '架构重构，跨 src/a/b、src/c/d、src/e/f 三处。' },
    })
    expect(resolved.routeKey).toContain('light')
    expect((resolved.difficultyReasons ?? []).join(' ')).toContain('不一致')
  })
})

describe('difficultyMismatch（不一致要响亮，不静默按缺省走）', () => {
  const heavyInference = inferDifficulty({ body: '这是一次架构重构，跨 src/a/b、src/c/d、src/e/f 三处。' })

  it('推断 heavy 但注入缺省 light → 给出带依据的告警', () => {
    const msg = difficultyMismatch(heavyInference, undefined)
    expect(msg).toBeDefined()
    expect(msg).toContain('不一致')
    expect(msg).toContain('heavy')
    expect(msg).toContain('依据')
  })

  it('显式传 light 也会告警（漏传与传错都要响）', () => {
    expect(difficultyMismatch(heavyInference, 'light')).toBeDefined()
  })

  it('一致时静默（不打扰）', () => {
    expect(difficultyMismatch(heavyInference, 'heavy')).toBeUndefined()
  })

  it('无推断依据时不告警（不该对着小需求喊）', () => {
    const small = inferDifficulty({ title: '改错别字' })
    expect(difficultyMismatch(small, 'light')).toBeUndefined()
  })
})
