/**
 * HTML 安全工具 —— 所有 DSH GUI page 共享。
 *
 * @module page-kit/client/html
 */

/** 将文本中的 HTML 特殊字符转义为实体，防止 XSS。 */
export function esc(s: unknown): string {
  return String(s ?? '').replace(/[&<>"']/g, (m) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m] ?? m)
  )
}
