/**
 * 难度推断（REQ-d3e61a T-15 / FR-16）——把"注入难度"从**缺省值**改为**由需求实质推断**。
 *
 * 现状（本仓实证）：注入按 (stage, difficulty, category) 路由，而 difficulty 缺省
 * DEFAULT_DIFFICULTY = 'light'。于是 REQ-c9f899 这种"动架构、跨多子系统"的重构，
 * 被注入了**轻档**需求分析提示词——需求说自己要重构，注入却说"这是小事"。
 *
 * 本模块只做纯推断，并把**推断依据**一并返回（供 injection-log 留痕）；
 * 真正的"不一致时响亮提示"由 difficultyMismatch() 给出，调用方负责播报。
 */

import { DEFAULT_DIFFICULTY, type Difficulty } from './types.js'
import { fmt } from '../text/fmt.js'

export type SignalKind = 'architecture' | 'data-model' | 'new-subsystem' | 'multi-subsystem' | 'scale'

export interface DifficultySignal {
  kind: SignalKind
  /** 人类可读标签（进留痕）。 */
  label: string
  hit: boolean
  /** 命中的原文片段（留痕用，最多 3 条）。 */
  evidence: string[]
}

export interface DifficultyInference {
  difficulty: Difficulty
  signals: DifficultySignal[]
  /** 推断依据（人类可读，写进 injection-log）。空数组 = 无信号 → 用缺省。 */
  reasons: string[]
}

interface Rule { kind: SignalKind; label: string; re: RegExp }

/** 前置信号：任一命中即判 heavy（对齐 FR-16：动架构 / 多子系统 / 改数据模型 / 新增子系统）。 */
const RULES: readonly Rule[] = [
  { kind: 'architecture', label: '动架构', re: /架构|重构|分层|解耦|模块划分|接口变更|接口契约/g },
  { kind: 'data-model', label: '改数据模型', re: /数据模型|表结构|表与|加列|改字段|迁移|schema|DDL|数据库表/g },
  { kind: 'new-subsystem', label: '新增子系统', re: /新增[^\n]{0,6}(子系统|模块|服务|插件|适配器|通道)/g },
  { kind: 'multi-subsystem', label: '跨多子系统', re: /(?:src|packages)\/[a-z-]+\/[a-z0-9-]+/g },
]

/** 规模信号：功能点数量阈值（单靠规模也判 heavy）。 */
const SCALE_THRESHOLD = 8
const SCALE_RE = /(?:^|\n)\s*(?:[-*]\s*)?(?:\*\*)?(?:FR|BUG|RF|SP|DOC|CH)-\d+/g

function takeEvidence(values: readonly string[], max = 3): string[] {
  const out: string[] = []
  for (const v of values) {
    const s = v.trim()
    if (s.length > 0 && !out.includes(s)) out.push(s)
    if (out.length >= max) break
  }
  return out
}

/**
 * 由需求实质推断注入难度。
 * @param input.title 需求标题；input.body 需求正文；input.category 立项类型
 */
export function inferDifficulty(input: { title?: string; body?: string; category?: string } = {}): DifficultyInference {
  const text = [input.title ?? '', input.body ?? ''].join('\n')
  const signals: DifficultySignal[] = []
  const reasons: string[] = []

  for (const rule of RULES) {
    // multi-subsystem 是"跨"信号：命中 ≥3 个不同路径才算，避免单个路径就判 heavy
    const all = Array.from(text.matchAll(rule.re))
    const distinct = [...new Set(all.map(m => m[0]))]
    const threshold = rule.kind === 'multi-subsystem' ? 3 : 1
    const hit = distinct.length >= threshold
    const evidence = hit ? takeEvidence(distinct) : []
    signals.push({ kind: rule.kind, label: rule.label, hit, evidence })
    if (hit) {
      reasons.push(fmt('[{label}] 命中 {count} 处：{evidence}', {
        label: rule.label, count: distinct.length, evidence: evidence.join(' / '),
      }))
    }
  }

  const scaleMatches = Array.from(text.matchAll(SCALE_RE))
  const scaleHit = scaleMatches.length >= SCALE_THRESHOLD
  signals.push({
    kind: 'scale',
    label: '规模大',
    hit: scaleHit,
    evidence: takeEvidence([fmt('{count} 个功能点（阈值 {threshold}）', {
      count: scaleMatches.length, threshold: SCALE_THRESHOLD,
    })]),
  })
  if (scaleHit) {
    reasons.push(fmt('[规模大] 功能点 {count} 个 ≥ 阈值 {threshold}', {
      count: scaleMatches.length, threshold: SCALE_THRESHOLD,
    }))
  }

  const heavy = signals.some(s => s.hit)
  return { difficulty: heavy ? 'heavy' : DEFAULT_DIFFICULTY, signals, reasons }
}

/**
 * 「注入难度 vs 推断难度」一致性检查。不一致 → 返回**响亮**的提示文案（调用方必须播报，不静默）。
 * 一致或无推断依据 → undefined。
 */
export function difficultyMismatch(inferred: DifficultyInference, injected: Difficulty | undefined): string | undefined {
  const actual = injected ?? DEFAULT_DIFFICULTY
  if (inferred.reasons.length === 0) return undefined
  if (actual === inferred.difficulty) return undefined
  return fmt('⚠️ 注入难度与需求实质不一致：注入={actual}，按需求实质应为 {expected}。依据：{reasons}。请显式传入 difficulty={expected}（缺省 {fallback} 不适用于本需求）。', {
    actual, expected: inferred.difficulty, reasons: inferred.reasons.join('；'), fallback: DEFAULT_DIFFICULTY,
  })
}
