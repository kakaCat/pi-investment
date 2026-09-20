/**
 * 通用 toast 飘字 —— 所有 DSH GUI page 共享。
 * 替代各页面自建的 toast（bulletin、execution styles 残留、solve-kit 内嵌）。
 *
 * @module page-kit/client/toast
 */

function cssFor(pf: string): string {
  return [
    '.' + pf + '-toast { position:fixed; left:50%; bottom:54px; transform:translateX(-50%); z-index:10000; max-width:70vw; background:#303133; color:#fff; border-radius:7px; padding:7px 15px; font-size:12.5px; line-height:1.6; box-shadow:0 4px 16px rgba(0,0,0,.22); transition:opacity .35s, transform .35s; }',
    '.' + pf + '-toast.ok { background:#529b2e; }',
    '.' + pf + '-toast.err { background:#e64545; }',
    '.' + pf + '-toast.out { opacity:0; transform:translateX(-50%) translateY(8px); }',
  ].join('\n')
}

/** 注入 toast 样式一次（按前缀独立 style 标签）；返回清理函数。 */
export function injectToastStyles(prefix: string): () => void {
  const id = 'dsh-toast-styles-' + prefix
  const existing = document.getElementById(id)
  if (existing !== null && existing.tagName === 'STYLE') return () => existing.remove()
  const style = document.createElement('style')
  style.id = id
  style.textContent = cssFor(prefix)
  ;(document.head ?? document.documentElement).appendChild(style)
  return () => { document.getElementById(id)?.remove() }
}

/**
 * 显示飘字提示。
 * @param text 提示文本
 * @param ok true=绿色成功 / false=红色失败
 * @param prefix CSS 类前缀（页面隔离）
 * @param duration 显示毫秒数，默认 4200
 */
export function showToast(text: string, ok: boolean, prefix: string, duration = 4200): void {
  const el = document.createElement('div')
  el.className = prefix + '-toast ' + (ok ? 'ok' : 'err')
  el.textContent = text
  document.body.appendChild(el)
  window.setTimeout(() => {
    el.classList.add('out')
    window.setTimeout(() => el.remove(), 350)
  }, duration)
}
