/**
 * Sidebar foot action occupant for the holdings board — the GUI entry point.
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
 * @module dashboard-holdings/client/footer-action
 */
import { createElement } from 'react'

/** Panel identity shared by this client half. */
export const PANEL_NAME = 'dashboard-holdings'
export const PANEL_LABEL = '账户持仓'

/** Stylesheet id tag so re-apply never double-injects. */
const CSS_TAG = '@pi-investment/dashboard-holdings/footer-action.css'

/** Owner prop share passed by the sidebar shell (see sidebar slots contract). */
export interface FooterActionOwnerProps {
  /** Whether the sidebar renders wide content (false = 56px rail). */
  wide: boolean
}

/** Optional click seam for the next increment (board view); inert until wired. */
export const OPEN_EVENT = 'dashboard-holdings:open-board'

/**
 * Footer action occupant. Wide: label row beside Settings. Rail: icon-only
 * square. Self-contained styles ride the shell's --dsw-* tokens where the
 * theme exposes them, with neutral fallbacks otherwise.
 */
export function HoldingsFooterAction(props: FooterActionOwnerProps): unknown {
  const { wide } = props
  const label = PANEL_LABEL
  return createElement(
    'button',
    {
      type: 'button',
      className: wide ? 'dsh-hld-foot wide' : 'dsh-hld-foot rail',
      title: label,
      'aria-label': label,
      onClick: () => {
        // Dispatch the open-board seam; index.ts apply() listens and toggles
        // the center-column board controller (official-slot wiring).
        console.log('[dashboard-holdings] footer action clicked — dispatching', OPEN_EVENT)
        window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { open: true } }))
      },
    },
    wide
      ? [
          createElement('span', { className: 'dsh-hld-foot-icon', key: 'i' }, ICON),
          createElement('span', { className: 'dsh-hld-foot-label', key: 'l' }, label),
        ]
      : createElement('span', { className: 'dsh-hld-foot-icon', key: 'i' }, ICON),
  )
}

/** Minimal inline "portfolio" glyph (pie chart), sized by CSS. */
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
  createElement('circle', { cx: '8', cy: '8', r: '6' }),
  createElement('path', { d: 'M8 2 V8 L12 11' }),
  createElement('path', { d: 'M8 8 L4 5' }),
)

const FOOT_STYLES = `
.dsh-hld-foot {
  display: flex; align-items: center; gap: 8px;
  border: none; background: transparent; color: var(--dsw-text-secondary, inherit);
  font: inherit; font-size: 13px; cursor: pointer;
  -webkit-appearance: none; appearance: none;
}
.dsh-hld-foot:hover { background: var(--dsw-hover, rgba(128,128,128,.12)); color: var(--dsw-text-primary, inherit); }
.dsh-hld-foot:active { background: var(--dsw-active, rgba(128,128,128,.2)); }
.dsh-hld-foot.wide {
  width: calc(100% - 8px); margin: 2px 4px; padding: 6px 10px;
  border-radius: 8px; justify-content: flex-start; text-align: left;
}
.dsh-hld-foot.rail {
  width: 36px; height: 36px; margin: 4px auto; border-radius: 8px;
  justify-content: center; padding: 0;
}
.dsh-hld-foot-icon { display: inline-flex; flex: none; }
.dsh-hld-foot.rail .dsh-hld-foot-label { display: none; }
.dsh-hld-foot-icon svg { width: 16px; height: 16px; }
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
