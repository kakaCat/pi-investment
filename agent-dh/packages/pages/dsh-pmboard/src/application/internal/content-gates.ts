/**
 * 内容校验闸门 —— 纯函数，零 IO（REQ-d3e61a T-2 / D-ARCH-2, D-DATA-1/2, D-IF-1）
 *
 * 与 artifact-gates.ts 的两级「登记态」闸门正交：本模块读**文档正文**，判定
 * 条款覆盖 / 编号串联 / 验收四件套 / E2E 覆盖。调用方负责读文件（DocRepository.read），
 * 把字符串传进来——因此本模块不依赖 fs、不抛异常、可被门禁与看板复用。
 *
 * 关键实现约束：**必须跳过代码围栏块**（三反引号或三波浪线围起来的区域）——
 * 文档里贴一段代码就可能出现行首井号或竖线，那都不是结构，误判会导致门禁乱拦。
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
const DEF_LINE_RE = /^\s*(?:[-*+]\s+)?\*\*((?:FR|BUG|RF|SP|DOC|CH)-\d+)\b/

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

function naturalSort(ids: readonly string[]): string[] {
  return [...new Set(ids)].sort((a, b) => {
    const ka = idKey(a); const kb = idKey(b)
    if (ka.prefix !== kb.prefix) return ka.prefix < kb.prefix ? -1 : 1
    if (ka.domain !== kb.domain) return ka.domain < kb.domain ? -1 : 1
    return ka.num - kb.num
  })
}

/** 提取根编号**定义位**（标题 / **FR-1 ...** 定义行）。不扫描泛指引用，避免误报。 */
export function extractClauseDefinitions(doc: ParsedDoc): string[] {
  const set = new Set<string>()
  for (const h of doc.headings) {
    const m = DEF_LINE_RE.exec('**' + h.text)
    if (m !== null) set.add(m[1])
  }
  for (const line of doc.bodyLines) {
    const m = DEF_LINE_RE.exec(line)
    if (m !== null) set.add(m[1])
  }
  return naturalSort([...set])
}

/** 显式裁剪标记（R1 允许把条款登记为"本轮裁剪/非目标"，并写明理由）。 */
export const SKIP_MARKERS = ['本轮不做', '本轮裁剪', '非目标', '本轮不实现', '不做（'] as const

/**
 * 取"已显式裁剪"的根编号：条款**定义行或其紧随 2 行**里出现裁剪标记即算。
 * 覆盖门禁拦的是"无记录"，不是"不许多做少做"——标了裁剪就不拦。
 */
export function extractSkippedClauses(doc: ParsedDoc): string[] {
  const lines = doc.bodyLines
  const out = new Set<string>()
  lines.forEach((line, i) => {
    const m = DEF_LINE_RE.exec(line)
    if (m === null) return
    // 只看本条款自己的行 + 紧随的 2 行，**撞到下一条款定义即停**——
    // 否则下一条的「本轮不做」会误染上一条（实测踩过）。
    const win = [line]
    for (let j = i + 1; j < lines.length && j <= i + 2; j++) {
      if (DEF_LINE_RE.test(lines[j])) break
      win.push(lines[j])
    }
    if (SKIP_MARKERS.some(k => win.join('\n').includes(k))) out.add(m[1])
  })
  return naturalSort([...out])
}

/** 提取 serves 声明（serves: FR-1, D-ARCH-2）。 */
export function extractServes(text: string): string[] {
  const m = /serves\s*[:：]\s*([^\n|]*)/i.exec(text)
  if (m === null) return []
  return naturalSort(collectIds(m[1]))
}

/**
 * 汇总一份文档声明的 serves——三个来源合并（去重、自然排序）：
 *   ① 标题行里的 serves: ...（设计文档章节、拆分文档标题）
 *   ② 表格中表头名为 serves 的列（覆盖对照表的行级映射）
 *   ③ front-matter 的 requirement_refs / serves（文档级映射）
 * 三者合并是刻意的：规范允许文档级与行级映射并存，缺任一来源都算没声明。
 */
export function extractServesFrom(doc: ParsedDoc, opts: { frontmatterKeys?: readonly string[] } = {}): string[] {
  const out: string[] = []
  const keys = opts.frontmatterKeys ?? ['requirement_refs', 'serves']
  for (const h of doc.headings) out.push(...extractServes(h.text))
  for (const t of doc.tables) {
    const i = t.header.findIndex(x => x.trim().toLowerCase() === 'serves')
    if (i < 0) continue
    for (const row of t.rows) {
      for (const id of collectIds(row[i] ?? '')) out.push(id)
    }
  }
  for (const k of keys) {
    const v = doc.frontmatter[k]
    if (v !== undefined) for (const id of collectIds(v)) out.push(id)
  }
  return naturalSort(out)
}

/**
 * 编号模式（单一事实源）：根编号按类型前缀；技术设计编号带「域」段 D-<域>-<n>；
 * 其余下游编号单段。**D-ARCH-2 这类必须认**——只写 D-\d+ 会漏掉全部设计章节编号。
 */
const ID_PATTERN = '(?:FR|BUG|RF|SP|DOC|CH)-\\d+|D-[A-Z]+-\\d+|(?:T|BE|FE|TC|E)-\\d+|t-[0-9a-f]{6}'

/** 从任意文本里收集编号（根 + 下游），保持出现顺序。 */
export function collectIds(text: string): string[] {
  const ids = text.match(new RegExp('\\b(?:' + ID_PATTERN + ')\\b', 'g'))
  return ids === null ? [] : ids
}

/** 条款覆盖：roots 中既未被 covered 覆盖、也未登记 skip 的 = 缺口。 */
export function checkClauseCoverage(
  roots: readonly string[],
  covered: readonly string[],
  opts: { skipped?: readonly string[] } = {},
): { gaps: string[] } {
  const cov = new Set(covered); const skip = new Set(opts.skipped ?? [])
  return { gaps: naturalSort(roots.filter(r => !cov.has(r) && !skip.has(r))) }
}

/** 编号串联：serves 指向不存在 = 悬空；根编号无人指向 = 孤儿。 */
export function checkNumberChain(items: readonly NumberedItem[]): { dangling: string[]; orphans: string[] } {
  const ids = new Set(items.map(i => i.id))
  const dangling: string[] = []
  const hasDownstream = new Set<string>()
  for (const it of items) {
    for (const s of it.serves) {
      if (!ids.has(s)) dangling.push(it.id + '→' + s)
      hasDownstream.add(s)
    }
  }
  const orphans = items.filter(i => isRootId(i.id) && !hasDownstream.has(i.id)).map(i => i.id)
  return { dangling: [...new Set(dangling)].sort(), orphans: naturalSort(orphans) }
}

/** 验收四件套：验什么 / 对应编号 / 怎么验 / 预期。缺任一 → 计入 missing。 */
export const ACCEPTANCE_KIT = ['验什么', '对应编号', '怎么验', '预期'] as const

export function checkAcceptanceKit(verification: ParsedDoc): { missing: string[] } {
  const missing: string[] = []
  const table = verification.tables.find(
    t => t.header.some(h => h.includes('怎么验')) || t.header.some(h => h.includes('验什么')),
  )
  if (table === undefined) {
    return { missing: ['整表：找不到验收四件套表（表头需含 验什么/对应编号/怎么验/预期）'] }
  }
  const col: Record<string, number> = {}
  for (const name of ACCEPTANCE_KIT) {
    const i = table.header.findIndex(h => h.includes(name))
    col[name] = i
    if (i < 0) missing.push('表头缺列：' + name)
  }
  const iRef = col['对应编号']
  table.rows.forEach((row, n) => {
    const key = iRef >= 0 && (row[iRef] ?? '').length > 0 ? row[iRef] : '第' + (n + 2) + '行'
    for (const name of ACCEPTANCE_KIT) {
      const i = col[name]
      if (i >= 0 && (row[i] ?? '').trim().length === 0) missing.push(key + '：缺「' + name + '」')
    }
  })
  return { missing }
}

/** 业务三要素字段名（任务卡必须让非工程读者看懂的三件事）。 */
export const TRIAD = ['在做什么', '解决什么问题', '得到什么结果'] as const

/** 已知的"纯技术名词堆叠"特征词（来自本仓真实坏卡；保守列举，避免误伤）。 */
export const TECH_TITLE_TOKENS = ['张表', '加列', 'metric 化', '纯函数', '序列化', '抽象层', 'DTO', 'schema', 'handler', 'repo 层'] as const

/**
 * 标题是否像"工程名词堆叠"（**建议级**，不作硬拦——硬拦只用于字段缺失，避免形式主义）。
 * 判据保守：整条无中文（纯英文标题）或命中已知技术词表。
 */
export function looksTechnical(title: string): boolean {
  const t = title.trim()
  if (t.length === 0) return false
  if (!/[\u4e00-\u9fa5]/.test(t)) return true
  return TECH_TITLE_TOKENS.some(tok => t.includes(tok))
}

/**
 * 取出三要素各字段的正文（按标题或 **粗体标签** 定位；取到下一个字段/标题前）。
 * 找不到字段 → 值为 undefined，与"字段在但为空"区分开。
 */
export function triadFields(doc: ParsedDoc): Record<string, string | undefined> {
  const lines = doc.bodyLines
  const at = new Map<string, number>()
  lines.forEach((line, i) => {
    for (const name of TRIAD) {
      if (at.has(name)) continue
      const asHeading = new RegExp('^#{1,6}\\s*' + name + '\\s*$').test(line.trim())
      const asBold = new RegExp('^\\s*(?:[-*+]\\s+)?\\*\\*' + name + '\\*\\*').test(line)
      if (asHeading || asBold) at.set(name, i)
    }
  })
  const out: Record<string, string | undefined> = {}
  for (const name of TRIAD) {
    const i = at.get(name)
    if (i === undefined) { out[name] = undefined; continue }
    // 字段行**同行剩余内容** + 后续行，直到下一个字段/标题
    let text = lines[i].replace(/^#{1,6}\s*/, '').replace(/^\s*(?:[-*+]\s+)?/, '').replace(/\*\*/g, '')
    text = text.split(name).slice(1).join(name).trim()
    for (let j = i + 1; j < lines.length; j++) {
      const l = lines[j]
      if (/^#{1,6}\s/.test(l)) break
      if (TRIAD.some(n => new RegExp('^\\s*(?:[-*+]\\s+)?\\*\\*' + n + '\\*\\*').test(l))) break
      text += '\n' + l
    }
    out[name] = text.trim()
  }
  return out
}

/**
 * 任务卡三要素校验（FR-6 的机械部分）：
 *   - **硬拦**：任一字段缺失或正文为空；
 *   - **建议**：标题像工程名词堆叠 → 计入 warnings（不阻断，避免形式主义）。
 */
export function checkTaskCardTriad(doc: ParsedDoc): { missing: string[]; warnings: string[] } {
  const fields = triadFields(doc)
  const missing: string[] = []
  for (const name of TRIAD) {
    const v = fields[name]
    if (v === undefined) missing.push('缺字段：' + name)
    else if (v.length === 0) missing.push('字段为空：' + name)
  }
  const warnings: string[] = []
  const title = (doc.frontmatter['title'] ?? doc.headings[0]?.text ?? '').trim()
  if (looksTechnical(title)) {
    warnings.push('标题像工程名词堆叠（建议改写成业务动作）：' + title)
  }
  return { missing, warnings }
}

/**
 * 设计文档章节可追溯校验（FR-5 / FR-8 的机械部分）：
 * **每个 H2 及以上章节都必须标注服务哪条功能点**（\`serves: FR-4\`，可多值）。
 * 缺标注的章节 = 孤儿章节 → design_orphan。
 *
 * 刻意**只校验标注存在与否，不校验文风**——"语言强度按层"是给人的写作指引（提示词分片承载），
 * 不该由机器判散文好坏（否则就是形式主义）。H1 视为文档标题不参与（文档级 serves 写在 H1 或
 * front-matter 的 requirement_refs）。
 */
export function checkDesignSectionsHaveServes(doc: ParsedDoc): { missing: string[] } {
  const missing: string[] = []
  for (const h of doc.headings) {
    if (h.level < 2) continue
    if (extractServes(h.text).length === 0) missing.push(h.text.trim().length > 0 ? h.text.trim() : '第' + h.line + '行')
  }
  return { missing }
}

/** E2E 覆盖：测试策略表里是否存在层级含 E2E 的行。 */
export function checkE2ECoverage(requirement: ParsedDoc): { hasE2E: boolean } {
  for (const t of requirement.tables) {
    const iLv = t.header.findIndex(h => h.includes('层级'))
    if (iLv < 0) continue
    for (const row of t.rows) {
      if ((row[iLv] ?? '').toUpperCase().includes('E2E')) return { hasE2E: true }
    }
  }
  return { hasE2E: false }
}
