/**
 * 注入预算与保底（REQ-422af1 t3）—— 编写不限、注入有闸。
 *
 * 口径：字符数（token 的代理指标，确定性可测）。裁剪只作用于非保底片段；
 * **floor（清单/闸门/红旗/节点兜底档）永不裁**；连保底都超预算时返回结构化超限标记
 * 而不静默裁保底（响亮失败优于静默降级，对齐本仓既有教训）。
 *
 * @module dsh-pmboard/domain/prompt/budget
 */
import type { BudgetOverflow, Fragment } from './types.js'

/**
 * 默认注入预算（字符数）。
 *
 * P0 口径 = 实测上限（零行为变更不触发裁剪）；P1 六节点分化后，heavy 档要装下
 * **主 skill 原文（brainstorming 15,456 字符，全场景最大）+ overrides + common 铁律**——
 * 现取值 = 最大 heavy 注入实测值 + 余量（2026-09-17 实测 max ≈ 18.3K）。重档主 skill 永不裁，
 * 故预算不得低于它；超过预算时仍按 floor 优先裁剪并结构化报超限（见 applyBudget）。
 */
export const DEFAULT_PROMPT_BUDGET = 24000

export function isFloor(fragment: Fragment): boolean {
  return fragment.priority === 'floor'
}

/** 片段集合 → 注入文本：非空片段以空行分隔，空片段不产生任何字符。 */
export function assembleText(fragments: readonly Fragment[]): string {
  const parts: string[] = []
  for (const f of fragments) {
    if (f.text.length > 0) parts.push(f.text)
  }
  return parts.join('\n\n')
}

export interface BudgetOutcome {
  readonly kept: readonly Fragment[]
  readonly trimmed: readonly string[]
  readonly overBudget?: BudgetOverflow
}

/**
 * 按预算裁剪。budget 缺省/非法 → 不裁。
 * 裁剪顺序：优先级数值升序（低优先先裁），同优先级按 id 逆序（确定性）。
 */
export function applyBudget(fragments: readonly Fragment[], budget: number | undefined): BudgetOutcome {
  if (budget === undefined || !Number.isFinite(budget) || budget < 0) {
    return { kept: fragments, trimmed: [] }
  }
  if (assembleText(fragments).length <= budget) {
    return { kept: fragments, trimmed: [] }
  }
  const trimmable = fragments
    .filter((f) => !isFloor(f))
    .slice()
    .sort((a, b) => Number(a.priority) - Number(b.priority) || (a.id < b.id ? 1 : a.id > b.id ? -1 : 0))
  const removed = new Set<string>()
  for (const f of trimmable) {
    removed.add(f.id)
    const kept = fragments.filter((x) => !removed.has(x.id))
    if (assembleText(kept).length <= budget) {
      return { kept, trimmed: [...removed] }
    }
  }
  const floorOnly = fragments.filter(isFloor)
  return {
    kept: floorOnly,
    trimmed: [...removed],
    overBudget: { reason: 'floor-exceeds-budget', floorChars: assembleText(floorOnly).length, budget },
  }
}
