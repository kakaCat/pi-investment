/**
 * 需求文档里的「条款接收状态」表格（REQ-d3e61a T-5 / PRD FR-3）。
 *
 * 为什么写回需求文档而不只是看板：FR-3 的原话是「需求功能点**自身**带接收状态，随卡的生命周期
 * 自动更新」。只让看板红、文档不红，等于缺口只在"打开看板时"才存在——R9 之所以能溜过四个节点，
 * 恰恰因为**任何面**上都没有"没人接"的痕迹。文档是需求方最先打开的那一面。
 *
 * 幂等与安全：只碰 begin/end 标记之间那一段，标记之外一个字都不改（批准过的正文不能被机器重排）；
 * 标记不存在时插在 §6 功能点末尾，**找不到锚点就退化为文末追加**，绝不覆盖正文。
 *
 * @module dsh-pmboard/application/internal/requirement-marks-doc
 */
import type { ClauseMarkRow, RequirementMarksView } from '../../shared/protocol.js'
import { fmt } from '../../domain/text/fmt.js'

/** 机器维护段的起止标记（内容为 HTML 注释，渲染文档时不可见，但 grep/脚本可见）。 */
export const MARKS_BEGIN = '<!-- reqboard:marks:begin 机器维护，请勿手改 -->'
export const MARKS_END = '<!-- reqboard:marks:end -->'

/** 机器维护段的标题（人读需求文档时看到的那一行）。 */
export const MARKS_TITLE = '#### 条款接收状态（随卡的生命周期自动更新）'

/** 四态各自的显示文案——「未被接收」必须一眼可辨（红）。 */
const STATE_LABEL: Record<ClauseMarkRow['state'], string> = {
  done: '✅ 已完成（有证据）',
  received: '✅ 已接收',
  skipped: '⏭ 本轮裁剪',
  unreceived: '🔴 **未被接收**',
}

/** 逐条接收状态 → 表格行（三列：编号 / 接收状态 / 承载任务）。 */
export function marksTableRows(view: RequirementMarksView): string[] {
  return view.clauses.map(c => {
    const by = c.by.length > 0 ? c.by.join('、') : '—'
    return '| ' + [c.clause, STATE_LABEL[c.state], by].join(' | ') + ' |'
  })
}

/** 渲染整段机器维护块（含红名单小结；没有条款时不渲染空表）。 */
export function renderMarksBlock(view: RequirementMarksView): string {
  if (view.clauses.length === 0) {
    const why = view.available ? '本需求文档尚未定义功能点编号' : '需求文档不存在'
    return [MARKS_BEGIN, '', MARKS_TITLE, '', '> ' + why + '。', '', MARKS_END].join('\n')
  }
  const lines = [
    MARKS_BEGIN,
    '',
    MARKS_TITLE,
    '',
    '| 编号 | 接收状态 | 承载任务 |',
    '|------|---------|---------|',
    ...marksTableRows(view),
    '',
  ]
  lines.push(
    view.unreceived.length === 0
      ? fmt('> 无未接收条款（{n} 条全部有落点）。', { n: view.clauses.length })
      : fmt('> 🔴 **未被接收（{n} 条）**：{list}', { n: view.unreceived.length, list: view.unreceived.join('、') }),
  )
  lines.push('', MARKS_END)
  return lines.join('\n')
}

/** 找出现有机器维护段的行号区间（缺一半或顺序颠倒 → undefined，按"没有"处理并整段重插）。 */
export function marksBlockRange(text: string): { start: number; end: number } | undefined {
  const lines = text.split('\n')
  const start = lines.findIndex(l => l.trim() === MARKS_BEGIN)
  const end = lines.findIndex(l => l.trim() === MARKS_END)
  return start >= 0 && end > start ? { start, end } : undefined
}

/** 机器维护段是否已存在（幂等判定与测试用）。 */
export function hasMarksBlock(text: string): boolean {
  return marksBlockRange(text) !== undefined
}

/** 该需求文档当前记录的逐条状态（回读机器维护段；未写过 → 空数组）。 */
export function readMarksBlockStates(text: string): Array<{ clause: string; state: string; by: string }> {
  const range = marksBlockRange(text)
  if (range === undefined) return []
  const out: Array<{ clause: string; state: string; by: string }> = []
  for (const raw of text.split('\n').slice(range.start, range.end + 1)) {
    const cells = raw.trim().split('|').map(s => s.trim()).filter(s => s.length > 0)
    if (cells.length !== 3 || !/^(?:FR|BUG|RF|SP|DOC|CH)-\d+$/.test(cells[0])) continue
    out.push({ clause: cells[0], state: cells[1], by: cells[2] })
  }
  return out
}

function trimTail(lines: readonly string[]): string[] {
  const out = [...lines]
  while (out.length > 0 && out[out.length - 1].trim() === '') out.pop()
  return out
}

/**
 * 把渲染好的块写入文档：已有标记段 → 原地替换；否则插入 §6 功能点之后、下一个 \`## \` 标题之前。
 * 锚点缺失时退化为文末追加——**任何情况下都不删除正文**。
 */
export function upsertMarksBlock(text: string, block: string): string {
  const lines = text.split('\n')
  const blockLines = block.split('\n')
  const range = marksBlockRange(text)
  if (range !== undefined) {
    return [...lines.slice(0, range.start), ...blockLines, ...lines.slice(range.end + 1)].join('\n')
  }
  const sec6 = lines.findIndex(l => /^##\s+6[.、\s]/.test(l))
  let at = lines.length
  if (sec6 >= 0) {
    for (let i = sec6 + 1; i < lines.length; i++) {
      if (/^##\s/.test(lines[i])) { at = i; break }
    }
  }
  const head = trimTail(lines.slice(0, at))
  const tail = [...lines.slice(at)]
  while (tail.length > 0 && tail[0].trim() === '') tail.shift()
  return [...head, '', ...blockLines, '', ...tail].join('\n')
}
