/**
 * 时间格式化工具 —— 所有 DSH GUI page 共享。
 * 统一口径，消除各页面 view.ts 里的重复实现。
 *
 * @module page-kit/client/fmt
 */

const pad2 = (n: number): string => String(n).padStart(2, '0')

/** 解析 ISO/类 ISO 字符串为 Date；无效时返回 null。 */
function parseDate(ts: unknown): Date | null {
  if (!ts) return null
  const d = new Date(String(ts))
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * 格式化为 "MM-DD HH:mm"。
 * 可选项：
 *   - withYear: true → "YYYY-MM-DD HH:mm"
 *   - omitDateIfToday: true → 今天只显示 "HH:mm"
 */
export function fmtClock(ts: string | null | undefined, opts?: { withYear?: boolean; omitDateIfToday?: boolean }): string {
  if (!ts) return '—'
  const d = parseDate(ts)
  if (!d) return String(ts).slice(0, 16).replace('T', ' ')
  const now = new Date()
  const isToday = d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
  const hm = pad2(d.getHours()) + ':' + pad2(d.getMinutes())
  if (opts?.omitDateIfToday && isToday) return hm
  const date = opts?.withYear
    ? d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate())
    : pad2(d.getMonth() + 1) + '-' + pad2(d.getDate())
  return date + ' ' + hm
}

/** 仅日期："YYYY-MM-DD" */
export function fmtDate(ts: string | null | undefined): string {
  if (!ts) return '—'
  const d = parseDate(ts)
  if (!d) return String(ts)
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate())
}

/** 仅时间："HH:mm" */
export function fmtTime(ts: string | null | undefined): string {
  if (!ts) return '—'
  const d = parseDate(ts)
  if (!d) return String(ts).slice(11, 16)
  return pad2(d.getHours()) + ':' + pad2(d.getMinutes())
}
