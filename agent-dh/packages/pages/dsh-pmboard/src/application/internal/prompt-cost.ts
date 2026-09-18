/**
 * 提示词成本（REQ-a33899 t5）——纯投影：把 systemPrompt 装配结果与注入留痕折算成字符/估算 token。
 *
 * **不落台账**：固定系统提示词随代码、基因组、工作区指令变化，落盘即过期失真；
 * 因此每次请求实时装配、按需返回，并在响应里标 source（assembled/unavailable）。
 * 口径：字符 → token 用 estimateTokensFromChars（与 DSH 固定密度一致），UI 必须标「估算」。
 *
 * @module dsh-pmboard/application/internal/prompt-cost
 */
import {
  estimateTokensFromChars,
  windowCodeFromSessionId,
  type InjectionCost,
  type InjectionItem,
  type PromptPartCost,
  type SystemPromptCost,
} from '../../shared/protocol.js'

/** 注入留痕的最小形状（InjectionLogEntry 的结构子集，避免 application 依赖适配器类型）。 */
export interface InjectionLogLike {
  at: number
  windowKey: string
  stage: string
  routeKey: string
  fragmentIds: string[]
  charCount: number
}

/** 系统提示词装配服务不可得时的诚实降级值（不猜数字）。 */
export function unavailableSystemPromptCost(): SystemPromptCost {
  return { perTurnChars: 0, perTurnEstTokens: 0, turns: 0, sections: [], contexts: [], toolsChars: 0, source: 'unavailable' }
}

function partCost(name: unknown, text: unknown): PromptPartCost | undefined {
  if (typeof name !== 'string' || name.length === 0) return undefined
  const t = typeof text === 'string' ? text : ''
  if (t.length === 0) return undefined // 空段不产生注入成本（renderPrompt 同样滤空）
  return { name, chars: t.length, estTokens: estimateTokensFromChars(t.length), text: t }
}

/**
 * 把 PromptAssembly 折算成成本视图。
 * turns <= 0（回合数不可得）→ 不给 cumulativeEstTokens（缺失 ≠ 0）。
 */
export function summarizeSystemPrompt(assembly: unknown, turns: number): SystemPromptCost {
  // 装配结果本身不可得（undefined/null/非对象）→ 判为 unavailable，不产出一个"看似全 0"的 assembled
  if (typeof assembly !== 'object' || assembly === null) return unavailableSystemPromptCost()
  const a = assembly as { sections?: unknown; contexts?: unknown; tools?: unknown }
  const sections = (Array.isArray(a.sections) ? a.sections : [])
    .map(s => partCost((s as { name?: unknown } | undefined)?.name, (s as { text?: unknown } | undefined)?.text))
    .filter((x): x is PromptPartCost => x !== undefined)
  const contexts = (Array.isArray(a.contexts) ? a.contexts : [])
    .map(c => partCost((c as { name?: unknown } | undefined)?.name, (c as { text?: unknown } | undefined)?.text))
    .filter((x): x is PromptPartCost => x !== undefined)
  // 工具 schema 的文字化成本：无工具时不计 "[]" 这 2 个字符（空集合不产生注入成本）
  const tools = Array.isArray(a.tools) ? a.tools : []
  const toolsChars = tools.length === 0 ? 0 : JSON.stringify(tools).length
  const perTurnChars = sections.reduce((n, s) => n + s.chars, 0)
    + contexts.reduce((n, c) => n + c.chars, 0) + toolsChars
  const t = Number.isFinite(turns) && turns > 0 ? Math.floor(turns) : 0
  return {
    perTurnChars,
    perTurnEstTokens: estimateTokensFromChars(perTurnChars),
    turns: t,
    ...(t > 0 ? { cumulativeEstTokens: estimateTokensFromChars(perTurnChars) * t } : {}),
    sections,
    contexts,
    toolsChars,
    source: 'assembled',
  }
}

/** 需求关联的窗口集合（原始 sessionId ∪ 窗口码）——注入留痕按 windowKey 归属的匹配依据。 */
export function injectionWindowsOf(sessionIds: readonly (string | undefined)[]): Set<string> {
  const out = new Set<string>()
  for (const sid of sessionIds) {
    if (typeof sid !== 'string' || sid.length === 0) continue
    out.add(sid)
    out.add(windowCodeFromSessionId(sid))
  }
  return out
}

/**
 * 注入提示词成本：只统计属于该需求窗口的留痕；**没有可匹配窗口时不归因**（宁可空，不张冠李戴）。
 * chars 聚合 = 各条 charCount 之和（可核对）。
 */
export function summarizeInjections(
  entries: readonly InjectionLogLike[],
  windows: ReadonlySet<string>,
): InjectionCost {
  const items: InjectionItem[] = []
  if (windows.size > 0) {
    for (const e of entries) {
      if (!windows.has(e.windowKey)) continue
      const chars = Number.isFinite(e.charCount) && e.charCount > 0 ? e.charCount : 0
      items.push({
        at: e.at,
        stage: e.stage,
        routeKey: e.routeKey,
        fragmentIds: [...e.fragmentIds],
        chars,
        estTokens: estimateTokensFromChars(chars),
      })
    }
  }
  items.sort((a, b) => a.at - b.at)
  const byStageChars = new Map<string, number>()
  let chars = 0
  for (const it of items) {
    chars += it.chars
    byStageChars.set(it.stage, (byStageChars.get(it.stage) ?? 0) + it.chars)
  }
  const byStage: PromptPartCost[] = [...byStageChars.entries()]
    .map(([name, c]) => ({ name, chars: c, estTokens: estimateTokensFromChars(c) }))
  return { count: items.length, chars, estTokens: estimateTokensFromChars(chars), byStage, items }
}
