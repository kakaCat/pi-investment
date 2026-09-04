/**
 * Sidebar foot action occupant for the execution board — the GUI entry point.
 *
 * Registers through the OFFICIAL DSH slot seat `sidebar.footer.action`
 * (the only third-party sidebar seat; declared by client-ui-sidebar as a
 * list/root slot rendered beside Settings at the sidebar foot). The shell
 * hands the occupant only the column state (`wide`: false = 56px rail).
 *
 * Authoring notes (why no JSX): this package has no React toolchain and
 * agent-dh's tsconfig carries no `jsx` transform — the client bundle is plain
 * tsdown CJS with react externalized (loader-seed resolved at runtime, same as
 * official bundles). So the occupant is authored with `React.createElement`.
 *
 * @module dashboard-execution/client/footer-action
 */
import { createElement } from 'react'

/** Panel identity shared by this client half. */
export const PANEL_NAME = 'dashboard-execution'
export const PANEL_LABEL = '执行看板'

/** Stylesheet id tag so re-apply never double-injects. */
const CSS_TAG = '@pi-investment/dashboard-execution/footer-action.css'

/** Owner prop share passed by the sidebar shell (see sidebar slots contract). */
export interface FooterActionOwnerProps {
  /** Whether the sidebar renders wide content (false = 56px rail). */
  wide: boolean
}

/** Optional click seam for the next increment (board view); inert until wired. */
export const OPEN_EVENT = 'dashboard-execution:open-board'

/**
 * Footer action occupant. Wide: label row beside Settings. Rail: icon-only
 * square. Self-contained styles ride the shell's --dsw-* tokens where the
 * theme exposes them, with neutral fallbacks otherwise.
 */
export function ExecFooterAction(props: FooterActionOwnerProps): unknown {
  const { wide } = props
  const label = PANEL_LABEL
  return createElement(
    'button',
    {
      type: 'button',
      className: wide ? 'dsh-exec-foot wide' : 'dsh-exec-foot rail',
      title: label,
      'aria-label': label,
      onClick: () => {
        // Dispatch the open-board seam; index.ts apply() listens and toggles
        // the center-column board controller (official-slot wiring).
        console.log('[dashboard-execution] footer action clicked — dispatching', OPEN_EVENT)
        window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { open: true } }))
      },
    },
    wide
      ? [
          createElement('span', { className: 'dsh-exec-foot-icon', key: 'i' }, ICON),
          createElement('span', { className: 'dsh-exec-foot-label', key: 'l' }, label),
        ]
      : createElement('span', { className: 'dsh-exec-foot-icon', key: 'i' }, ICON),
  )
}

/** Minimal inline "board" glyph (two-by-two grid), sized by CSS. */
const ICON = createElement(
  'svg',
  {
    viewBox: '0 0 16 16',
    width: '16',
    height: '16',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': '1.4',
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    'aria-hidden': 'true',
  },
  createElement('rect', { x: '2', y: '2', width: '5', height: '5', rx: '1' }),
  createElement('rect', { x: '9', y: '2', width: '5', height: '5', rx: '1' }),
  createElement('rect', { x: '2', y: '9', width: '5', height: '5', rx: '1' }),
  createElement('rect', { x: '9', y: '9', width: '5', height: '5', rx: '1' }),
)

const FOOT_STYLES = `
.dsh-exec-foot {
  display: flex; align-items: center; gap: 8px;
  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
  font: inherit; font-size: 13px; cursor: pointer;
  -webkit-appearance: none; appearance: none;
}
.dsh-exec-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-exec-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
.dsh-exec-foot.wide {
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border-radius: 8px; justify-content: flex-start; text-align: left;
}
.dsh-exec-foot.rail {
  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
  justify-content: center; padding: 0;
}
.dsh-exec-foot-icon { display: inline-flex; flex: none; }
.dsh-exec-foot.rail .dsh-exec-foot-label { display: none; }
.dsh-exec-foot-icon svg { width: 16px; height: 16px; }
`

/** Inject the footer-action stylesheet once (idempotent, guarded). */
export function injectFooterStyles(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector(`style[data-plugin-css="${CSS_TAG}"]`)) return
  const tag = document.createElement('style')
  tag.dataset.pluginCss = CSS_TAG
  tag.textContent = FOOT_STYLES
  document.head.appendChild(tag)
}
