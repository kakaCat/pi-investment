/**
 * 盯盘规则载荷瘦身（RFC 017 P2 收尾，2026-10-27）。
 *
 * 背景：/api/watch/rules 返回 220 条规则、约 410KB，其中 94% 是看板不展示的
 * 停用/过期规则与 30+ 个内部字段；切换账户和每 60s 辅助刷新都要整包传。
 * 看板只需要「活跃规则 + 视图实际读取的字段」：
 *   id / symbol / enabled / conditions / context / account / expires_at
 *
 * 这里做两件事：
 *  ① 服务端过滤掉 enabled=false 或已过期的规则（客户端原本也会过滤，语义等价）；
 *  ② 只保留视图字段，并把 context 截断到 400 字符（视图只展示 44 字符、title 最多 400）。
 * 实测 410KB → 约 33KB（-92%），且不改变看板可见内容。
 */
import type { WatchCondition, WatchRule } from '../types/index.js'

/** 视图最多展示 400 字符的 context title；再长没有意义。 */
export const WATCH_CONTEXT_MAX_CHARS = 400

function compactContext(value: unknown): string {
  if (typeof value === 'string') return value.slice(0, WATCH_CONTEXT_MAX_CHARS)
  if (value && typeof value === 'object') {
    try {
      return JSON.stringify(value).slice(0, WATCH_CONTEXT_MAX_CHARS)
    } catch {
      return ''
    }
  }
  return ''
}

/** 只保留 condChip 会读的字段，剥掉 cooldown_sec 等调度内部参数。 */
function compactConditions(value: unknown): WatchCondition[] {
  if (!Array.isArray(value)) return []
  const out: WatchCondition[] = []
  for (const raw of value) {
    if (!raw || typeof raw !== 'object') continue
    const c = raw as Record<string, any>
    const condition: WatchCondition = { type: String(c.type ?? c.operator ?? 'condition') }
    if (typeof c.operator === 'string') condition.operator = c.operator
    if (typeof c.threshold === 'number') condition.threshold = c.threshold
    if (typeof c.field === 'string') condition.field = c.field
    if (c.params && typeof c.params === 'object') {
      const params: { price?: number; direction?: string } = {}
      if (typeof c.params.price === 'number') params.price = c.params.price
      if (typeof c.params.direction === 'string') params.direction = c.params.direction
      if (Object.keys(params).length > 0) condition.params = params
    }
    out.push(condition)
  }
  return out
}

/** 与客户端 isActiveRule 同口径：停用/暂停或已过期都不展示。 */
export function isActiveWatchRule(rule: any, now: number = Date.now()): boolean {
  if (!rule || typeof rule !== 'object') return false
  if (rule.enabled === false) return false
  if (rule.expires_at) {
    const t = new Date(rule.expires_at).getTime()
    if (Number.isFinite(t) && t <= now) return false
  }
  return true
}

/** 原始 v2 规则 → 看板最小契约（活跃规则 + 视图字段）。 */
export function slimWatchRules(rules: unknown, now: number = Date.now()): WatchRule[] {
  if (!Array.isArray(rules)) return []
  const out: WatchRule[] = []
  for (const raw of rules) {
    if (!isActiveWatchRule(raw, now)) continue
    const r = raw as Record<string, any>
    out.push({
      id: Number(r.id),
      symbol: String(r.symbol ?? ''),
      enabled: true,
      conditions: compactConditions(r.conditions),
      context: compactContext(r.context),
      ...(r.account != null ? { account: String(r.account) } : {}),
      ...(r.expires_at != null ? { expires_at: String(r.expires_at) } : {}),
    })
  }
  return out
}
