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
import { fmt } from '../../domain/text/fmt.js'

import { DEF_LINE_RE, isRootId, naturalSort } from './doc-parse.js'
import type { NumberedItem, ParsedDoc } from './doc-parse.js'

export * from './doc-parse.js'


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

/**
 * 提取根编号**定义位**的**全部出现**（同一编号出现几次就返回几次）。
 *
 * 为什么必须单独一个函数：extractClauseDefinitions 返回前做了 Set 去重，
 * 拿它的结果喂 checkClauseDuplicates 会让每个编号的计数恒 ≤1 —— 判重永远不会触发
 * （结构性死代码，不是阈值问题）。本函数与它解析口径完全一致，唯一差别是去重与否；
 * 刻意不合并成一个函数带开关，是为了让"判重吃哪一份"在调用处一眼可见。
 */
export function extractClauseDefinitionOccurrences(doc: ParsedDoc): string[] {
  const out: string[] = []
  for (const h of doc.headings) {
    const m = DEF_LINE_RE.exec('**' + h.text)
    if (m !== null) out.push(m[1])
  }
  for (const line of doc.bodyLines) {
    const m = DEF_LINE_RE.exec(line)
    if (m !== null) out.push(m[1])
  }
  return out
}

/** 显式裁剪标记（R1 允许把条款登记为"本轮裁剪/非目标"，并写明理由）。 */
export const SKIP_MARKERS = ['本轮不做', '本轮裁剪', '非目标', '本轮不实现', '不做（'] as const

/**
 * 去掉成对括号内的内容（中英文括号各扫两遍以吃掉嵌套）。
 *
 * 为什么必须去：条款定义行常把候选状态**枚举**出来——本需求的 FR-3 写的是
 * "自身带接收状态（已被任务接收 / 已完成+证据 / **本轮不做** / 未被接收（红））"，其中
 * "本轮不做"只是四态之一的名字，却被当成"本条已裁剪"，于是最该标红的那条永远标不出红
 * （实测：取消它的卡后状态是 skipped，不是 unreceived）。括号里是概念，括号外才是声明。
 */
function stripParens(text: string): string {
  let out = text
  for (let i = 0; i < 2; i++) out = out.replace(/（[^）]*）/g, '').replace(/\([^)]*\)/g, '')
  return out
}

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
    if (SKIP_MARKERS.some(k => stripParens(win.join('\n')).includes(k))) out.add(m[1])
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
 * 编号模式（单一事实源）：根编号按类型前缀；设计编号带「域」段 D-<域>-<n>；
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
    if (i < 0) missing.push(fmt('表头缺列：{name}', { name }))
  }
  const iRef = col['对应编号']
  table.rows.forEach((row, n) => {
    const key = iRef >= 0 && (row[iRef] ?? '').length > 0 ? row[iRef] : fmt('第{n}行', { n: n + 2 })
    for (const name of ACCEPTANCE_KIT) {
      const i = col[name]
      if (i >= 0 && (row[i] ?? '').trim().length === 0) missing.push(fmt('{key}：缺「{name}」', { key, name }))
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
    if (v === undefined) missing.push(fmt('缺字段：{name}', { name }))
    else if (v.length === 0) missing.push(fmt('字段为空：{name}', { name }))
  }
  const warnings: string[] = []
  const title = (doc.frontmatter['title'] ?? doc.headings[0]?.text ?? '').trim()
  if (looksTechnical(title)) {
    warnings.push(fmt('标题像工程名词堆叠（建议改写成业务动作）：{title}', { title }))
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
    if (extractServes(h.text).length === 0) missing.push(h.text.trim().length > 0 ? h.text.trim() : fmt('第{line}行', { line: h.line }))
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

/**
 * 检查编号连续性（FR-1, FR-2, FR-3... 不能跳号）。
 * 按前缀分组检查，每组独立连续。
 */
export function checkClauseSequence(roots: readonly string[]): string[] {
  const byPrefix = new Map<string, number[]>()

  for (const id of roots) {
    const match = /^([A-Z]+)-(\d+)$/.exec(id)
    if (match === null) continue
    const prefix = match[1]
    const num = parseInt(match[2], 10)
    if (!byPrefix.has(prefix)) byPrefix.set(prefix, [])
    byPrefix.get(prefix)!.push(num)
  }

  const gaps: string[] = []
  for (const [prefix, nums] of byPrefix) {
    nums.sort((a, b) => a - b)
    for (let i = 0; i < nums.length - 1; i++) {
      const curr = nums[i]
      const next = nums[i + 1]
      if (next - curr > 1) {
        // 跳号
        for (let missing = curr + 1; missing < next; missing++) {
          gaps.push(prefix + '-' + missing)
        }
      }
    }
  }

  return gaps
}


/**
 * 拆分内容特征检测（REQ-2d1c74 FR-3）：设计文档里出现任务表/拆分章节的证据清单（空 = 干净）。
 *
 * 特征集 v1（刻意保守，宁漏勿冤——本需求自己的设计文档也要能过）：
 *  ① 任务表表头：表头单元格含英文 depends_on，或同时含 acceptance 与 implementation
 *     （与 normalizePlanTasks 字段同名才算；中文散文提及不命中）；
 *  ② 拆分章节标题：H2+ 标题含「拆分计划」或「任务 DAG」（标题级强信号；正文提及不命中）。
 *
 * 围栏代码块不参与判定——parseDocument 已剥离（讨论本门禁时的示例只许活在代码块里，
 * 结构性特征（表格/标题）才算证据）。
 * 已知限制：手写中文表头的任务表漏检，列为后续增强（先保证零误伤）。
 */
export function detectDecompositionFeatures(doc: ParsedDoc): string[] {
  const hits: string[] = []
  for (const t of doc.tables) {
    const header = t.header.map(h => h.toLowerCase())
    if (header.some(h => h.includes('depends_on'))) {
      hits.push(fmt('任务表表头（depends_on 列，第 {line} 行）', { line: t.line }))
    } else if (header.some(h => h.includes('acceptance')) && header.some(h => h.includes('implementation'))) {
      hits.push(fmt('任务表表头（acceptance + implementation 列，第 {line} 行）', { line: t.line }))
    }
  }
  for (const h of doc.headings) {
    if (h.level < 2) continue
    if (h.text.includes('拆分计划') || h.text.includes('任务 DAG') || h.text.includes('任务DAG')) {
      hits.push(fmt('拆分章节标题（「{text}」，第 {line} 行）', { text: h.text, line: h.line }))
    }
  }
  return hits
}

/**
 * 检查编号唯一性（同一编号不能出现多次）。
 *
 * ⚠️ 入参必须是**未去重**的清单（用 extractClauseDefinitionOccurrences）。
 * 喂 extractClauseDefinitions 的输出会让计数恒 ≤1，判重静默失效。
 */
export function checkClauseDuplicates(roots: readonly string[]): string[] {
  const seen = new Map<string, number>()
  for (const id of roots) {
    seen.set(id, (seen.get(id) ?? 0) + 1)
  }
  return [...seen.entries()]
    .filter(([_, count]) => count > 1)
    .map(([id, count]) => id + '（出现' + count + '次）')
}