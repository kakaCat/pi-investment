/**
 * 文档结构解析原语 —— 纯函数，零 IO。
 *
 * 从 content-gates.ts 抽出（REQ-47939a A2「宿主单文件 ≤400 行」尺寸门禁）：
 * 这部分是门窗的**共同依赖**（门禁、trace、看板都解析同一套结构），
 * 与"具体校验哪一条规则"无关，故独立成模块；content-gates.ts 原样 re-export，
 * 既有 import 路径不变。
 */
export interface ParsedHeading { level: number; text: string; line: number }
export interface ParsedTable { header: string[]; rows: string[][]; line: number }
export interface ParsedDoc {
  frontmatter: Record<string, string>
  headings: ParsedHeading[]
  tables: ParsedTable[]
  /** 非代码块正文行（用于识别 **FR-1 ...** 这类定义行）。 */
  bodyLines: string[]
}

/** 目录项最小形状（与 ports.DocEntry 结构兼容）。 */
export interface DocsEntry { readonly name?: string; readonly isFile?: boolean }

/**
 * docs 端口的最小形状（只用到这三件，便于测试注入假实现）。
 * 放这里而不是 wiring 模块：它是 gates 与 trace 两个模块的**共同依赖**，下沉即无环。
 */
export interface DocsReader {
  exists(relPath: string): boolean
  read(relPath: string): Promise<string>
  /** 枚举目录（缺省实现视为空，便于最小假实现）。 */
  list?(relDir: string): readonly DocsEntry[]
}

export interface NumberedItem {
  id: string
  /** 上游编号（须指向真实存在者） */
  serves: string[]
  /** 本编号所属文档类别（需求 / 设计 / 拆分 / 任务 / 用例 / 证据 / 验收）。 */
  kind?: string
  title?: string
}

/** 根编号前缀（按立项类型）——见规范 §0.1 / §八。 */
export const ROOT_PREFIXES = ['FR', 'BUG', 'RF', 'SP', 'DOC', 'CH'] as const
/** 下游编号前缀（全类型统一）。 */
export const CHILD_PREFIXES = ['T', 'D', 'BE', 'FE', 'TC', 'E'] as const

const FENCE_RE = /^\s*(`{3,}|~{3,})/
const HEADING_RE = /^(#{1,6})\s+(.+)$/
const FM_DELIM_RE = /^---\s*$/
const TABLE_ROW_RE = /^\s*\|(.+)\|\s*$/
const TABLE_SEP_RE = /^\s*\|[\s:|-]+\|\s*$/
export const DEF_LINE_RE = /^\s*(?:[-*+]\s+)?\*\*((?:FR|BUG|RF|SP|DOC|CH)-\d+)\b/

/** 标记每一行是否处于代码围栏内（含围栏行本身）。 */
export function markCodeFences(lines: readonly string[]): boolean[] {
  const inFence = new Array<boolean>(lines.length).fill(false)
  let open: string | undefined
  for (let i = 0; i < lines.length; i++) {
    const m = FENCE_RE.exec(lines[i])
    if (open === undefined) {
      if (m !== null) { open = m[1][0]; inFence[i] = true }
    } else {
      inFence[i] = true
      if (m !== null && m[1][0] === open) open = undefined
    }
  }
  return inFence
}

function splitCells(line: string): string[] {
  const m = TABLE_ROW_RE.exec(line)
  if (m === null) return []
  return m[1].split('|').map(s => s.trim())
}

/** 解析文档为结构（纯函数）。 */
export function parseDocument(text: string): ParsedDoc {
  const lines = text.split(/\r?\n/)
  const inFence = markCodeFences(lines)
  const frontmatter: Record<string, string> = {}
  let start = 0
  if (lines.length > 0 && FM_DELIM_RE.test(lines[0])) {
    for (let i = 1; i < lines.length; i++) {
      if (FM_DELIM_RE.test(lines[i])) { start = i + 1; break }
      const idx = lines[i].indexOf(':')
      if (idx > 0) {
        const k = lines[i].slice(0, idx).trim()
        const v = lines[i].slice(idx + 1).trim()
        if (k.length > 0) frontmatter[k] = v
      }
    }
  }
  const headings: ParsedHeading[] = []
  const tables: ParsedTable[] = []
  const bodyLines: string[] = []
  for (let i = start; i < lines.length; i++) {
    if (inFence[i]) continue
    bodyLines.push(lines[i])
    const h = HEADING_RE.exec(lines[i])
    if (h !== null) headings.push({ level: h[1].length, text: h[2].trim(), line: i + 1 })
    if (TABLE_ROW_RE.test(lines[i])) {
      const next = lines[i + 1]
      if (next !== undefined && !inFence[i + 1] && TABLE_SEP_RE.test(next)) {
        const rows: string[][] = []
        let j = i + 2
        while (j < lines.length && !inFence[j] && TABLE_ROW_RE.test(lines[j])) { rows.push(splitCells(lines[j])); j++ }
        tables.push({ header: splitCells(lines[i]), rows, line: i + 1 })
        i = j - 1
      }
    }
  }
  return { frontmatter, headings, tables, bodyLines }
}

/** 是否根编号（按立项类型前缀）。 */
export function isRootId(id: string): boolean {
  return ROOT_PREFIXES.some(p => id.startsWith(p + '-'))
}

function idKey(id: string): { prefix: string; domain: string; num: number } {
  const parts = id.split('-')
  const last = Number(parts[parts.length - 1])
  return {
    prefix: parts[0] ?? '',
    domain: parts.length > 2 ? (parts[1] ?? '') : '',
    num: Number.isFinite(last) ? last : 0,
  }
}

export function naturalSort(ids: readonly string[]): string[] {
  return [...new Set(ids)].sort((a, b) => {
    const ka = idKey(a); const kb = idKey(b)
    if (ka.prefix !== kb.prefix) return ka.prefix < kb.prefix ? -1 : 1
    if (ka.domain !== kb.domain) return ka.domain < kb.domain ? -1 : 1
    return ka.num - kb.num
  })
}
