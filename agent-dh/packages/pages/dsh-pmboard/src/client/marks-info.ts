/**
 * 「🏷 条款接收状态」块渲染（REQ-d3e61a T-5 / PRD FR-3）——需求详情页的人读面。
 *
 * 未被接收（红）必须一眼可辨：REQ-c9f899 的 R9 溜过四个节点，正是因为**没有任何一面**
 * 显示"这条没人接"。所以这里既不折叠也不省略，红名单直接写进摘要行。
 *
 * @module dsh-pmboard/client/marks-info
 */
import { esc } from './html.js'
import type { ClauseMarkRow, RequirementMarksView } from '../shared/protocol.ts'
import { fmt } from '../domain/text/fmt.ts'

/** 四态显示文案与颜色类（与 domain 的四态同语义；unreceived 是唯一带 alert 的）。 */
const STATE_LABEL: Record<ClauseMarkRow['state'], { text: string; cls: string }> = {
  done: { text: '✅ 已完成（有证据）', cls: 'dsh-pm-mk-done' },
  received: { text: '✅ 已接收', cls: 'dsh-pm-mk-received' },
  skipped: { text: '⏭ 本轮裁剪', cls: 'dsh-pm-mk-skipped' },
  unreceived: { text: '🔴 未被接收', cls: 'dsh-pm-mk-unreceived' },
}

/** 空态/加载态占位（统一出口，避免各处自造文案）。 */
export function renderMarksPlaceholder(text: string): string {
  return '<div class="dsh-pm-note">' + esc(text) + '</div>'
}

/** 渲染逐条接收状态表（含红名单摘要行）。 */
export function renderMarksBlock(view: RequirementMarksView): string {
  if (!view.available) {
    return renderMarksPlaceholder('读不到条款数据（需求文档缺失）——这不等于"全部未被接收"')
  }
  if (view.clauses.length === 0) {
    return renderMarksPlaceholder('本需求文档尚未定义功能点根编号（§6 功能点用 FR-# 定义，才能逐条追踪）')
  }
  const red = view.unreceived.length
  const summary = red === 0
    ? fmt('<div class="dsh-pm-mk-sum">共 {n} 条功能点，全部有落点。</div>', { n: view.clauses.length })
    : fmt('<div class="dsh-pm-mk-sum dsh-pm-mk-alert">🔴 未被接收 {n} 条：{list}</div>',
      { n: red, list: esc(view.unreceived.join('、')) })
  const rows = view.clauses.map(c => {
    const s = STATE_LABEL[c.state]
    const rowCls = c.state === 'unreceived' ? 'dsh-pm-mk-row is-unreceived' : 'dsh-pm-mk-row'
    const by = c.by.length > 0 ? esc(c.by.join('、')) : '—'
    return '<tr class="' + rowCls + '"><td class="dsh-pm-mk-id">' + esc(c.clause)
      + '</td><td class="' + s.cls + '">' + s.text
      + '</td><td class="dsh-pm-mk-by">' + by + '</td></tr>'
  })
  const table = fmt(
    '<table class="dsh-pm-mk-table"><thead><tr><th>编号</th><th>接收状态</th><th>承载任务</th></tr></thead><tbody>{rows}</tbody></table>',
    { rows: rows.join('') },
  )
  return summary + table
}
