/**
 * 持仓看板的「分块」契约（2026-09-13，w-adb088f2）
 *
 * 背景（实测）：GET /dashboard/api/holdings 整包 82 KB，其中 watchRules 54 条占 79.5 KB
 * （94.8%），而看板每 15 秒轮询同一接口 → 每 15 秒重传 82 KB，其中 95% 是几乎不变的盯盘规则。
 * 用户实际在看的「账户+汇总+持仓」只有约 3.6 KB（4.4%）。表现就是页面「卡住」。
 *
 * 方案：按**刷新频率**分块（不是按上游来源拆成多个路由——那只会把 1 次往返变成 N 次，
 * 而 host 侧本来就是并行扇出，总耗时≈最慢上游而非求和）：
 *   - hot  ：跟随轮询的高频小块
 *   - cold ：低频大块，按需/低频刷新
 * 缺省（不带 parts）＝全量，保持向后兼容。
 */

/** 跟随轮询的高频块（约 4 KB） */
// currentAccount 必须在 hot 里：账户下拉框的 selected 由它渲染，缺了它就会出现
// 「下拉框显示 A、数据是 B」的不一致（2026-09-13 实证）
export const HOT_PARTS = ['accounts', 'currentAccount', 'summary', 'positions', 'automation', 'compliance'] as const
/** 低频大块（约 85 KB）：盯盘规则 + 成交（todayTrades 与 tradeHistory 同源） */
export const COLD_PARTS = ['watchRules', 'tradeHistory', 'todayTrades'] as const
export const ALL_PARTS: readonly string[] = [...HOT_PARTS, ...COLD_PARTS]

/**
 * 解析 parts 查询参数。
 * - 缺省 / 空 / 全未知 → 全量（保守：宁可多传，绝不返回空页面）
 * - 'hot' / 'cold' / 'all' 预设
 * - 逗号分隔的显式块名
 */
export function parseParts(raw: string | null | undefined): string[] {
  if (raw == null || raw.trim() === '') return [...ALL_PARTS]
  const t = raw.trim().toLowerCase()
  if (t === 'hot') return [...HOT_PARTS]
  if (t === 'cold') return [...COLD_PARTS]
  if (t === 'all') return [...ALL_PARTS]
  const wanted = t.split(',').map((s) => s.trim()).filter((s) => s !== '')
  const valid = wanted.filter((p) => ALL_PARTS.includes(p))
  return valid.length > 0 ? valid : [...ALL_PARTS]
}

/** 只从 payload 里取本次实际请求到的块，避免用空数组把已加载的大块擦掉 */
export function pickParts<T extends Record<string, any>>(payload: T, parts: readonly string[] | undefined): Partial<T> {
  // 未声明 parts（老服务端/异常）时按"取全部"处理：合并场景下宁可多带，也不要把数据丢掉
  if (parts === undefined || parts.length === 0) return { ...payload }
  const keys = parts
  const out: Record<string, any> = {}
  for (const k of keys) {
    if (k in payload) out[k] = (payload as any)[k]
  }
  return out as Partial<T>
}
