/**
 * Bulletin client styles, injected as one global stylesheet with dsh-bbd-
 * prefixed classes. Surfaces ride the shell --dsw-* tokens where available so
 * the entry follows the active theme. phase1 ships ONLY the top sidebar entry
 * row (board body styles arrive with the board in phase2).
 *
 * @module dashboard-bulletin/client/styles
 */
export const STYLES = `
.dsh-bbd-entry {
  display: flex; align-items: center; gap: 8px; position: relative;
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border: none; border-radius: 8px; background: transparent;
  color: var(--dsw-text-secondary, inherit); font: inherit; font-size: 13px;
  cursor: pointer; text-align: left;
}
.dsh-bbd-entry:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-bbd-entry[data-active="true"] { background: var(--dsw-active, rgba(128,128,128,.18)); color: var(--dsw-text-primary, inherit); font-weight: 500; }
.dsh-bbd-entry svg { flex: none; }
[data-sidebar-collapsed] [data-dsh-bbd-entry],
[class*="_collapsed"] [data-dsh-bbd-entry] {
  width: 36px; height: 36px; min-width: 36px; margin: 0 0 12px; padding: 0;
  justify-content: center; gap: 0; text-align: center;
}
[data-sidebar-collapsed] [data-dsh-bbd-entry] .dsh-bbd-entry-label,
[class*="_collapsed"] [data-dsh-bbd-entry] .dsh-bbd-entry-label { display: none; }
[data-sidebar-collapsed] [data-dsh-bbd-entry] svg,
[class*="_collapsed"] [data-dsh-bbd-entry] svg { width: 16px; height: 16px; }
`

/** Inject the stylesheet once (tagged for the HMR driver cleanup). */
export function injectStyles(): void {
  const id = "dsh-bbd-styles"
  if (document.getElementById(id) !== null) return
  const style = document.createElement('style')
  style.id = id
  style.textContent = STYLES
  ;(document.head ?? document.documentElement).appendChild(style)
}
