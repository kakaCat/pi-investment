/** Minimal styles for reqboard client (step 1: sidebar entry + placeholder board). */

const CSS_TAG = '@pi-investment/dashboard-requirement/styles.css'

const CSS = `
/* Sidebar footer button */
.dsh-reqboard-foot {
  display: flex; align-items: center; gap: 8px;
  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
  font: inherit; font-size: 13px; cursor: pointer;
  -webkit-appearance: none; appearance: none;
}
.dsh-reqboard-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-reqboard-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
.dsh-reqboard-foot.wide {
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border-radius: 8px; justify-content: flex-start; text-align: left;
}
.dsh-reqboard-foot.rail {
  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
  justify-content: center; padding: 0;
}
.dsh-reqboard-foot-icon { display: inline-flex; flex: none; }
.dsh-reqboard-foot.rail .dsh-reqboard-foot-label { display: none; }
.dsh-reqboard-foot-icon svg { width: 16px; height: 16px; }

/* Center column board container */
.dsh-reqboard-view {
  display: none;
  position: absolute; inset: 0;
  background: var(--dsw-bg-primary, #fff);
  z-index: 10;
  flex-direction: column;
  padding: 24px;
  overflow: auto;
}
html[data-dsh-reqboard-active] .dsh-reqboard-view { display: flex; }

/* Placeholder content */
.dsh-reqboard-placeholder {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; gap: 16px;
  color: var(--dsw-text-secondary, #888);
}
.dsh-reqboard-placeholder h2 {
  margin: 0; font-size: 20px; color: var(--dsw-text-primary, #333);
}
.dsh-reqboard-placeholder p {
  margin: 0; font-size: 14px;
}
`

export function injectStyles(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector(`style[data-plugin-css="${CSS_TAG}"]`)) return
  const tag = document.createElement('style')
  tag.dataset.pluginCss = CSS_TAG
  tag.textContent = CSS
  document.head.appendChild(tag)
}
