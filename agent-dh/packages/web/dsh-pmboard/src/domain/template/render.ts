/**
 * 地址段渲染（REQ-260922213356-4a45 T-2 / design S-3、I-3）。
 *
 * 逐字契约（锁定单测）：空集返回空串（不产生任何空白/表头）；两清单任一非空才输出对应块。
 * 常驻的只是指针（名 + 一句话用途 + 绝对地址），模板正文不内联（FR-13，成本恒定）。
 *
 * @module dsh-pmboard/domain/template/render
 */
import { resolveNodeTemplates, resolveUpstreamDocs } from './resolve.js'
import { fmt } from '../text/fmt.js'
import type { AddressSectionInput } from './types.js'

const HEADING = '## 本节点文档（模板地址 · 先读再动手）'
const TEMPLATE_BLOCK = '产出模板（绝对地址，用 read 直接打开照写）：'
const UPSTREAM_BLOCK = '上游必读（先读再动手）：'

/** 模板根规范化：去尾斜杠；非绝对路径 → 响亮抛错（RISK-1：相对路径 read 打不开）。 */
function normalizeRoot(root: string): string {
  const trimmed = root.replace(/\/+$/, '')
  if (trimmed.length === 0 || !trimmed.startsWith('/')) {
    throw new Error(fmt('renderAddressSection：templateRoot 必须是绝对路径，收到 {root}', { root: JSON.stringify(root) }))
  }
  return trimmed
}

/** relPath 形态护栏：非空、不含 ..、不以 / 开头（防路径穿越）。 */
function assertRelPath(relPath: string): void {
  if (relPath.length === 0 || relPath.includes('..') || relPath.startsWith('/')) {
    throw new Error(fmt('renderAddressSection：非法模板相对名 {relPath}', { relPath: JSON.stringify(relPath) }))
  }
}

/**
 * 渲染地址段；两清单皆空 → 返回空串（调用方不得补空白/表头）。
 * 有模板条目但 templateRoot 不可用时抛错，由调用方降级留痕（不静默）。
 */
export function renderAddressSection(input: AddressSectionInput): string {
  const templates = resolveNodeTemplates(input.stage, input.category)
  const docs = resolveUpstreamDocs(input.requirement, input.stage, input.currentTask)
  if (templates.length === 0 && docs.length === 0) return ''

  const lines: string[] = [HEADING]
  if (templates.length > 0) {
    const root = normalizeRoot(input.templateRoot)
    lines.push('', TEMPLATE_BLOCK)
    for (const t of templates) {
      assertRelPath(t.relPath)
      lines.push('- ' + t.title + '：' + root + '/' + t.relPath + ' —— ' + t.purpose)
    }
  }
  if (docs.length > 0) {
    lines.push('', UPSTREAM_BLOCK)
    for (const d of docs) lines.push('- ' + d.title + '：' + d.path)
  }
  return lines.join('\n')
}
