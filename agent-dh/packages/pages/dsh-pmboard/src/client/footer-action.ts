/**
 * Sidebar footer action for requirement board.
 * Pure React.createElement (no JSX) — matches execution plugin pattern.
 */
import { createElement } from 'react'
import { PANEL_LABEL } from './dom.ts'

const CSS_TAG = 'dsh-pmboard/footer-action.css'

export const OPEN_EVENT = 'dsh-pmboard:open-board'

export interface FooterActionProps {
  wide: boolean
}

const ICON = createElement(
  'svg',
  {
    viewBox: '0 0 16 16', width: '16', height: '16',
    fill: 'none', stroke: 'currentColor', 'stroke-width': '1.4',
    'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true',
  },
  createElement('rect', { x: '2', y: '2', width: '5', height: '5', rx: '1' }),
  createElement('rect', { x: '9', y: '2', width: '5', height: '5', rx: '1' }),
  createElement('rect', { x: '2', y: '9', width: '5', height: '5', rx: '1' }),
  createElement('rect', { x: '9', y: '9', width: '5', height: '5', rx: '1' }),
)

const STYLES = `
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
`

export function injectFooterStyles(): void {
  if (typeof document === 'undefined') return
  if (document.querySelector(`style[data-plugin-css="${CSS_TAG}"]`)) return
  const tag = document.createElement('style')
  tag.dataset.pluginCss = CSS_TAG
  tag.textContent = STYLES
  document.head.appendChild(tag)
}

export function ReqboardFooterAction(props: FooterActionProps): unknown {
  const { wide } = props
  const label = PANEL_LABEL
  return createElement(
    'button',
    {
      type: 'button',
      className: wide ? 'dsh-reqboard-foot wide' : 'dsh-reqboard-foot rail',
      title: label,
      'aria-label': label,
      onClick: () => {
        window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { open: true } }))
      },
    },
    wide
      ? [
          createElement('span', { className: 'dsh-reqboard-foot-icon', key: 'i' }, ICON),
          createElement('span', { className: 'dsh-reqboard-foot-label', key: 'l' }, label),
        ]
      : createElement('span', { className: 'dsh-reqboard-foot-icon', key: 'i' }, ICON),
  )
}
