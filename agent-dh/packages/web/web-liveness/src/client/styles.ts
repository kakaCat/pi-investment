/**
 * web-liveness 样式：一条顶部常驻横幅（`.dsh-wlv-*` 命名空间，单份 <style> 注入）。
 * 配色对齐壳的 --dsw-* token，取不到时退回固定色，保证任何主题下都读得清。
 *
 * @module web-liveness/client/styles
 */
export const STYLES = `
.dsh-wlv-bar {
  position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
  z-index: 10050; display: none; align-items: center; gap: 10px;
  max-width: min(88vw, 720px); padding: 8px 14px;
  border-radius: 8px; font-size: 12.5px; line-height: 1.5;
  box-shadow: 0 4px 16px rgba(0, 0, 0, .22);
  color: #fff; background: #303133;
}
.dsh-wlv-bar[data-phase="offline"] { display: flex; background: #b88230; }
.dsh-wlv-bar[data-phase="stale"] { display: flex; background: #2f6fbf; }
.dsh-wlv-text { flex: 1 1 auto; }
.dsh-wlv-action {
  flex: none; border: 1px solid rgba(255, 255, 255, .55); border-radius: 6px;
  background: rgba(255, 255, 255, .14); color: #fff; font: inherit;
  padding: 3px 10px; cursor: pointer;
}
.dsh-wlv-action:hover { background: rgba(255, 255, 255, .26); }
`

const STYLE_ID = 'dsh-wlv-styles'

/** 注入样式一次（重复调用/重复 apply 都安全）。 */
export function injectStyles(): void {
  if (document.getElementById(STYLE_ID) !== null) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = STYLES
  ;(document.head ?? document.documentElement).appendChild(style)
}
