/**
 * Sidebar footer action for requirement board.
 * Pure React.createElement (no JSX) — matches execution plugin pattern.
 *
 * 2026-09-15 增强（用户诉求「现在的是汇总的内容，但是好丑，交互也差」）：
 *   1) 菜单项是**活的汇总**——鼠标悬停即在按钮旁展开进行中需求列表
 *      （需求名 / 状态 / 来源窗口码 / 任务进度条），不再需要先打开整块看板；
 *   2) 每一项可点击**直接跳到对应会话**（窗口↔需求↔会话三者打通），
 *      免去「在看板看到一条需求，再去侧栏翻会话」的来回；
 *   3) 视觉重做：卡片式条目 + 进度条 + 状态色，沿用 dsh-pm-* 主题变量。
 *
 * 数据来源：GET /dashboard/api/reqboard/requirements/summary（host 侧派生）。
 * 拉取失败不阻塞交互（展开空态 + 提示），点击按钮仍可打开完整看板。
 */
import { createElement, useState, useRef, useCallback, type ReactNode } from 'react'
import { PANEL_LABEL } from './dom.ts'
import { archivedSessionIds, jumpToSession, windowServiceAccess } from './session-jump.ts'

const CSS_TAG = 'dsh-pmboard/footer-action.css'

export const OPEN_EVENT = 'dsh-pmboard:open-board'

const BASE = '/dashboard/api/reqboard'
/** 摘要缓存时长：悬停频繁时避免每次打后端。 */
const CACHE_MS = 15000

export interface FooterActionProps {
  wide: boolean
}

/** host 侧 /requirements/summary 的条目投影。 */
interface SummaryItem {
  id: string
  title: string
  status: string
  category: string | null
  sourceSessionId: string | null
  windowCode: string | null
  tasksDone: number
  tasksActive: number
  tasksTotal: number
  percentage: number
  updatedAt: number
}

const STATUS_LABEL: Record<string, string> = {
  draft: '立项', brainstorming: '需求分析', design: '设计', decomposing: '拆分',
  implementing: '实施中', accepting: '待验收', done: '完成',
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

/* ---- 悬停下拉：进行中需求速览 + 会话跳转 ---- */
.dsh-reqboard-foot-wrap { position: relative; }
.dsh-reqboard-drop {
  position: absolute; bottom: calc(100% + 6px); left: 0; z-index: 2400;
  width: 296px; max-height: 56vh; overflow-y: auto;
  background: var(--dsw-bg, #fff); border: 1px solid var(--dsw-border, rgba(128,128,128,.25));
  border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,.20); padding: 6px;
  display: flex; flex-direction: column; gap: 2px;
}
.dsh-reqboard-foot-wrap.rail .dsh-reqboard-drop { left: calc(100% + 6px); bottom: 0; }
.dsh-reqboard-drop-head {
  display: flex; align-items: center; gap: 6px; padding: 6px 8px 8px;
  font-size: 11px; color: var(--dsw-text-secondary, #999); font-weight: 600;
}
.dsh-reqboard-drop-head .n { margin-left: auto; font-weight: 400; }
.dsh-reqboard-item {
  display: flex; flex-direction: column; gap: 5px; width: 100%; text-align: left;
  border: none; background: transparent; color: inherit; font: inherit;
  padding: 8px; border-radius: 7px; cursor: pointer;
}
.dsh-reqboard-item:hover { background: var(--dsw-hover, rgba(128,128,128,.10)); }
.dsh-reqboard-item-top { display: flex; align-items: center; gap: 6px; }
.dsh-reqboard-item-title {
  font-size: 12px; font-weight: 600; color: var(--dsw-text-primary, #222);
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dsh-reqboard-badge {
  flex: none; font-size: 10px; padding: 1px 7px; border-radius: 9px;
  background: rgba(128,128,128,.16); color: var(--dsw-text-primary, #444); font-weight: 600;
}
.dsh-reqboard-badge[data-status="implementing"] { background: rgba(74,125,255,.18); color: #2f5fd0; }
.dsh-reqboard-badge[data-status="design"] { background: rgba(240,160,32,.20); color: #a86a00; }
.dsh-reqboard-badge[data-status="brainstorming"] { background: rgba(142,68,173,.18); color: #6f2f8c; }
.dsh-reqboard-badge[data-status="accepting"] { background: rgba(23,162,184,.18); color: #0e7c8f; }
.dsh-reqboard-badge[data-status="done"] { background: rgba(40,167,69,.18); color: #1e7e34; }
.dsh-reqboard-item-meta {
  display: flex; align-items: center; gap: 6px; font-size: 10px;
  color: var(--dsw-text-secondary, #999);
}
.dsh-reqboard-win {
  font-family: ui-monospace, monospace; padding: 0 4px; border-radius: 4px;
  background: rgba(128,128,128,.14);
}
.dsh-reqboard-jump { margin-left: auto; color: #4a7dff; font-weight: 600; }
/* 来源会话已归档：整条压暗、窗口码划掉、右侧写「已归档」（点击只打开看板） */
.dsh-reqboard-item.is-archived .dsh-reqboard-item-title { color: var(--dsw-text-secondary, #888); }
.dsh-reqboard-item.is-archived .dsh-reqboard-badge { opacity: .6; }
.dsh-reqboard-win.is-archived {
  text-decoration: line-through; opacity: .65; background: transparent;
  border: 1px dashed var(--dsw-border, rgba(128,128,128,.35));
}
.dsh-reqboard-jump.is-archived { color: var(--dsw-text-secondary, #999); font-weight: 400; }
.dsh-reqboard-bar { display: flex; align-items: center; gap: 7px; }
.dsh-reqboard-bar-track {
  flex: 1; height: 4px; border-radius: 2px; overflow: hidden; background: rgba(128,128,128,.20);
}
.dsh-reqboard-bar-fill { display: block; height: 100%; background: linear-gradient(90deg,#4a7dff,#8e44ad); }
.dsh-reqboard-bar-num { font-size: 10px; color: var(--dsw-text-secondary, #999); font-variant-numeric: tabular-nums; }
.dsh-reqboard-empty { padding: 18px 8px; text-align: center; font-size: 12px; color: var(--dsw-text-secondary, #999); }
.dsh-reqboard-drop-foot {
  margin-top: 2px; padding: 7px 8px 3px; border-top: 1px solid var(--dsw-border, rgba(128,128,128,.16));
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; color: var(--dsw-text-secondary, #999);
}
.dsh-reqboard-drop-foot button {
  border: none; background: transparent; color: #4a7dff; font: inherit; font-size: 11px;
  cursor: pointer; padding: 2px 4px; border-radius: 4px;
}
.dsh-reqboard-drop-foot button:hover { background: rgba(74,125,255,.12); }
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

  const [hover, setHover] = useState<boolean>(false)
  const [items, setItems] = useState<SummaryItem[] | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const cacheAt = useRef<number>(0)
  const openTimer = useRef<number | null>(null)
  const closeTimer = useRef<number | null>(null)
  // 已归档会话 id（每次拉摘要时同步刷新）：这些条目的「跳转」不可用 → 置灰
  const archivedRef = useRef<ReadonlySet<string>>(new Set<string>())

  const load = useCallback(async (force: boolean): Promise<void> => {
    if (!force && cacheAt.current > 0 && Date.now() - cacheAt.current < CACHE_MS) return
    try {
      const res = await fetch(`${BASE}/requirements/summary`, { signal: AbortSignal.timeout(8000) })
      const json = (await res.json().catch(() => ({}))) as { success?: boolean; data?: { requirements?: SummaryItem[] }; error?: string }
      if (json.success === true) {
        archivedRef.current = archivedSessionIds()
        setItems(json.data?.requirements ?? [])
        setErr(null)
        cacheAt.current = Date.now()
      } else {
        setErr(json.error ?? '加载失败')
      }
    } catch (e) {
      setErr(String(e))
    }
  }, [])

  const onEnter = useCallback((): void => {
    if (closeTimer.current !== null) { window.clearTimeout(closeTimer.current); closeTimer.current = null }
    if (hover) return
    openTimer.current = window.setTimeout(() => { setHover(true); void load(false) }, 120)
  }, [hover, load])

  const onLeave = useCallback((): void => {
    if (openTimer.current !== null) { window.clearTimeout(openTimer.current); openTimer.current = null }
    closeTimer.current = window.setTimeout(() => setHover(false), 200)
  }, [])

  const onItem = useCallback((item: SummaryItem): void => {
    const sid = item.sourceSessionId
    // 无来源窗口（人工建卡）/ 来源会话已归档 → 都没法跳转，直接打开看板
    if (sid === null || sid.length === 0 || archivedRef.current.has(sid)) {
      window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { open: true } }))
      return
    }
    void jumpToSession(windowServiceAccess(), sid).then(result => {
      if (result === 'archived') window.alert('该会话已归档（日志保留，侧栏不可见）')
      else if (result === 'missing') window.alert('该会话不在当前列表（可能已删除）')
      else if (result === 'unavailable') window.alert('会话服务暂不可用，已打开项目看板')
      if (result !== 'opened') window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: { open: true } }))
    })
  }, [])

  const button = createElement(
    'button',
    {
      type: 'button',
      className: wide ? 'dsh-reqboard-foot wide' : 'dsh-reqboard-foot rail',
      title: `${label}（悬停查看进行中需求）`,
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

  if (!hover) {
    return createElement(
      'div',
      {
        className: `dsh-reqboard-foot-wrap${wide ? '' : ' rail'}`,
        onMouseEnter: onEnter,
        onMouseLeave: onLeave,
      },
      button,
    )
  }

  // ---- 下拉内容 ----
  const list: ReactNode = items === null
    ? createElement('div', { className: 'dsh-reqboard-empty' }, err === null ? '加载中…' : `加载失败：${err}`)
    : items.length === 0
      ? createElement('div', { className: 'dsh-reqboard-empty' }, '暂无进行中的需求')
      : items.map(item => {
          const pct = Number.isFinite(item.percentage) ? item.percentage : 0
          const sid = item.sourceSessionId
          const hasWindow = sid !== null && sid.length > 0
          // 来源会话已归档 → 跳不过去（日志保留、侧栏不可见）：按钮置灰、文案改「已归档」
          const archived = hasWindow && archivedRef.current.has(sid)
          return createElement(
            'button',
            {
              key: item.id,
              type: 'button',
              className: `dsh-reqboard-item${archived ? ' is-archived' : ''}`,
              title: archived
                ? `${item.id}《${item.title}》— 来源会话 ${sid} 已归档，无法跳转（点击打开看板）`
                : hasWindow
                  ? `${item.id}《${item.title}》— 点击跳转到会话 ${sid}`
                  : `${item.id}《${item.title}》— 人工建卡，无来源会话（点击打开看板）`,
              onClick: () => onItem(item),
            },
            createElement('div', { className: 'dsh-reqboard-item-top', key: 'top' }, [
              createElement('span', { className: 'dsh-reqboard-item-title', key: 't' }, `${item.id} ${item.title}`),
              createElement('span', { className: 'dsh-reqboard-badge', 'data-status': item.status, key: 'b' },
                STATUS_LABEL[item.status] ?? item.status),
            ]),
            createElement('div', { className: 'dsh-reqboard-item-meta', key: 'meta' }, [
              item.windowCode !== null
                ? createElement('span',
                    { className: `dsh-reqboard-win${archived ? ' is-archived' : ''}`, key: 'w',
                      title: archived ? '该会话已归档' : undefined },
                    item.windowCode)
                : createElement('span', { key: 'w' }, '人工建卡'),
              createElement('span', { key: 's' },
                item.tasksTotal > 0 ? `${item.tasksTotal} 任务${item.tasksActive > 0 ? ` · ${item.tasksActive} 进行中` : ''}` : '未拆分'),
              createElement('span',
                { className: `dsh-reqboard-jump${archived ? ' is-archived' : ''}`, key: 'j' },
                archived ? '已归档' : (hasWindow ? '跳转 →' : '看板 →')),
            ]),
            createElement('div', { className: 'dsh-reqboard-bar', key: 'bar' }, [
              createElement('span', { className: 'dsh-reqboard-bar-track', key: 'tr' },
                createElement('i', { className: 'dsh-reqboard-bar-fill', style: { width: `${pct}%` } })),
              createElement('span', { className: 'dsh-reqboard-bar-num', key: 'n' },
                `${item.tasksDone}/${item.tasksTotal}`),
            ]),
          )
        })

  const drop = createElement(
    'div',
    {
      className: 'dsh-reqboard-drop',
      onMouseEnter: onEnter,
      onMouseLeave: onLeave,
    },
    [
      createElement('div', { className: 'dsh-reqboard-drop-head', key: 'h' }, [
        createElement('span', { key: 'a' }, '进行中需求'),
        createElement('span', { className: 'n', key: 'b' }, items === null ? '' : String(items.length)),
      ]),
      list,
      createElement('div', { className: 'dsh-reqboard-drop-foot', key: 'f' }, [
        createElement('span', { key: 'l' }, '点击条目跳转会话'),
        createElement('button', {
          key: 'r', type: 'button',
          onClick: () => { void load(true) },
        }, '刷新'),
      ]),
    ],
  )

  return createElement(
    'div',
    {
      className: `dsh-reqboard-foot-wrap${wide ? '' : ' rail'}`,
      onMouseEnter: onEnter,
      onMouseLeave: onLeave,
    },
    [button, drop],
  )
}
