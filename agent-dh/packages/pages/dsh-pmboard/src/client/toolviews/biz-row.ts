/**
 * BizRow —— 业务工具定制卡片的通用行布局（REQ-c48f99 t2 / FR-1~FR-4）。
 *
 * 布局：24px 行 = icon + 标题 + 摘要（ellipsis）+ chevron；点击展开详情体。
 * 解析失败（summarize 返回 null）→ fallbackRow（FR-4：keyed 命中替换通用行，
 * 组件必须自带兜底，禁止白屏/throw）。
 * @module dsh-pmboard/client/toolviews/biz-row
 */
import { createElement as h, useState, type ReactNode } from 'react'
import {
  parseArgs, resultJson, argsRawOf, isSettled, fallbackModel, resultHeadline,
  type CardSummarize, type ToolBlock,
} from './shared.ts'

/** 单张卡片的声明：key=工具 wire 名，title=行标题，icon=默认图标，summarize=摘要纯函数。 */
export interface BizCard {
  key: string
  title: string
  icon: string
  summarize: CardSummarize
}

/** toolview 组件收到的 props（owner + locale seat；只用需要的字段）。 */
export interface BizRowProps {
  toolName?: string
  block: ToolBlock
  inspect?: () => void
  t?: (key: string) => string
}

const TV_CSS = `
.dsh-pm-tv-row{display:flex;align-items:center;height:24px;min-width:0;cursor:pointer;position:relative;border-radius:6px}
.dsh-pm-tv-row:hover{background:var(--dsw-alias-interactive-bg-hover-solid,rgba(0,0,0,.04))}
.dsh-pm-tv-icon{flex:none;width:16px;margin-right:6px;font-size:13px;text-align:center}
.dsh-pm-tv-title{flex:none;font-size:13px;color:var(--dsw-alias-label-secondary,#666);margin-right:8px}
.dsh-pm-tv-line{flex:auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  font-size:var(--dsh-content-font-size-secondary,13px);line-height:24px;color:var(--dsw-alias-label-tertiary,#999)}
.dsh-pm-tv-line[data-err]{color:var(--dsw-alias-state-error-primary,#c00)}
.dsh-pm-tv-chev{flex:none;margin-left:6px;color:var(--dsw-alias-label-caption,#aaa);font-size:11px}
.dsh-pm-tv-body{display:flex;flex-direction:column;margin:2px 0 4px 22px;padding:8px 12px;
  border:.5px solid var(--dsw-alias-border-l1,#ddd);border-radius:8px;gap:2px;
  font-size:12px;color:var(--dsw-alias-label-secondary,#666)}
.dsh-pm-tv-kv{display:grid;grid-template-columns:max-content 1fr;column-gap:14px;align-items:baseline}
.dsh-pm-tv-k{color:var(--dsw-alias-label-caption,#aaa)}
.dsh-pm-tv-v{white-space:pre-wrap;word-break:break-word;min-width:0}
.dsh-pm-tv-running{color:var(--dsw-alias-label-caption,#aaa);font-style:italic}
`

let cssInjected = false
function injectTvCss(): void {
  if (cssInjected || typeof document === 'undefined') return
  if (document.querySelector('style[data-dsh-pm-tv]') !== null) { cssInjected = true; return }
  const tag = document.createElement('style')
  tag.dataset.dshPmTv = '1'
  tag.textContent = TV_CSS
  document.head.appendChild(tag)
  cssInjected = true
}

/** 兜底行（FR-4）：任何输入都可渲染，永不 throw。 */
export function FallbackRow({ toolName, block }: { toolName: string; block: ToolBlock }): ReactNode {
  injectTvCss()
  const m = fallbackModel(toolName, block)
  return h('div', { className: 'dsh-pm-tv-row', 'data-err': m.isError ? '' : undefined },
    h('span', { className: 'dsh-pm-tv-icon' }, m.isError ? '❌' : '⚙'),
    h('span', { className: 'dsh-pm-tv-title' }, toolName),
    h('span', { className: 'dsh-pm-tv-line', ...(m.isError ? { 'data-err': '' } : {}) },
      m.outputLine !== '' && m.isError ? m.outputLine : m.argLine),
  )
}

/** 通用行工厂：把 BizCard 声明变成 toolview 组件。 */
export function makeBizRow(card: BizCard) {
  return function BizToolRow(props: BizRowProps): ReactNode {
    injectTvCss()
    const block = props.block
    const toolName = props.toolName ?? card.key
    let args: ReturnType<typeof parseArgs>
    let result: ReturnType<typeof resultJson>
    try {
      args = parseArgs(argsRawOf(block))
      result = resultJson(block)
    } catch {
      return h(FallbackRow, { toolName, block })
    }
    let sum: ReturnType<CardSummarize>
    try {
      sum = card.summarize(args, result, block)
    } catch {
      return h(FallbackRow, { toolName, block })
    }
    if (sum === null) return h(FallbackRow, { toolName, block })
    const cardSum = sum

    const settled = isSettled(block)
    const err = cardSum.isError === true
    const line = settled ? cardSum.line : `${cardSum.line}（执行中…）`
    const details = cardSum.details ?? []
    const headline = resultHeadline(block)

    function RowBody(): ReactNode {
      const [open, setOpen] = useState(false)
      const expandable = settled && details.length > 0
      return h('div', {},
        h('div', {
          className: 'dsh-pm-tv-row',
          onClick: expandable ? () => setOpen(!open) : undefined,
          style: expandable ? undefined : { cursor: 'default' },
        },
          h('span', { className: 'dsh-pm-tv-icon' }, err ? '❌' : cardSum.icon),
          h('span', { className: 'dsh-pm-tv-title' }, card.title),
          h('span', { className: 'dsh-pm-tv-line', ...(err ? { 'data-err': '' } : {}) }, line),
          expandable ? h('span', { className: 'dsh-pm-tv-chev' }, open ? '▾' : '▸') : null,
        ),
        open
          ? h('div', { className: 'dsh-pm-tv-body' },
              headline !== '' ? h('div', { className: 'dsh-pm-tv-kv' },
                h('span', { className: 'dsh-pm-tv-k' }, '结果'),
                h('span', { className: 'dsh-pm-tv-v' }, headline)) : null,
              details.map(([k, v]) => h('div', { className: 'dsh-pm-tv-kv', key: k },
                h('span', { className: 'dsh-pm-tv-k' }, k),
                h('span', { className: 'dsh-pm-tv-v' }, v))),
            )
          : null,
      )
    }
    return h(RowBody)
  }
}
