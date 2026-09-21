/**
 * 通用分页控件 —— 所有 DSH GUI page 共享。
 * 以 execution 版的智能省略号折叠为标准（支持 aria-current、上一页/下一页、总条数）。
 *
 * @module page-kit/client/pagination
 */

export interface PaginationOpts {
  page: number        // 当前页（1-based）
  total: number       // 总页数
  totalItems: number  // 总条数
  pageAttr: string    // data-xxx-page 属性名（如 'data-tkpage'）
  prevLabel?: string
  nextLabel?: string
}

/** 渲染分页 HTML 字符串（纯函数，innerHTML 用） */
export function renderPagination(opts: PaginationOpts): string {
  const { page, total, totalItems, pageAttr, prevLabel = '‹ 上一页', nextLabel = '下一页 ›' } = opts
  if (total <= 1) return ''

  const safePage = Math.min(Math.max(1, page), total)

  // 页码按钮生成器
  const numBtn = (p: number): string =>
    '<button type="button" class="tpg-num' + (p === safePage ? ' act' : '') + '"' +
    (p === safePage ? ' aria-current="page"' : '') +
    ' ' + pageAttr + '="' + p + '">' + p + '</button>'

  const nums: string[] = []
  if (total <= 7) {
    for (let p = 1; p <= total; p++) nums.push(numBtn(p))
  } else {
    const keys = [1, safePage - 1, safePage, safePage + 1, total]
      .filter(p => p >= 1 && p <= total)
      .sort((a, b) => a - b)
    const uniq: number[] = []
    for (const p of keys) if (!uniq.includes(p)) uniq.push(p)
    let last = 0
    for (const p of uniq) {
      if (last !== 0 && p - last > 1) nums.push('<span class="tpg-gap">…</span>')
      nums.push(numBtn(p))
      last = p
    }
  }

  return '<button type="button" class="tpg-arr" ' + pageAttr + '="' + (safePage - 1) + '"' +
    (safePage <= 1 ? ' disabled' : '') + '>' + prevLabel + '</button>' +
    '<span class="tpg-nums">' + nums.join('') + '</span>' +
    '<button type="button" class="tpg-arr" ' + pageAttr + '="' + (safePage + 1) + '"' +
    (safePage >= total ? ' disabled' : '') + '>' + nextLabel + '</button>' +
    '<span class="tpg-cnt">第 ' + safePage + '/' + total + ' 页 · 共 ' + totalItems + ' 条</span>'
}
