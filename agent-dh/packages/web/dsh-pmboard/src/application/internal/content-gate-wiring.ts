/**
 * 内容闸门的**取数 + 组装**层（REQ-d3e61a）——读文档、拼参数、产 GateFailure。
 *
 * 三层职责（尺寸门禁 ≤400 行，故按职责拆分，依赖方向单向）：
 *   - content-gates.ts        纯判定（给定文本 → 缺口），零 IO
 *   - content-trace.ts        编号图分析（追溯 / 三方一致性 / 接收标记），零 IO
 *   - content-gate-wiring.ts  **本文件**：取数与闸门组装（唯一碰文件系统的地方）
 *
 * 为保持既有 import 不变，本文件**再导出** content-trace 的分析 API。
 *
 * @module dsh-pmboard/application/internal/content-gate-wiring
 */
import type { RequirementRecord } from '../../shared/protocol.js'
import type { GateFailure } from './artifact-gates.js'
import {
  parseDocument,
  extractClauseDefinitions,
  extractClauseDefinitionOccurrences,
  extractSkippedClauses,
  checkClauseCoverage,
  checkNumberChain,
  checkDesignSectionsHaveServes,
  checkE2ECoverage,
  extractServes,
  collectIds,
  checkClauseSequence,
  checkClauseDuplicates,
  type DocsReader,
  type NumberedItem,
  type ParsedDoc,
} from './content-gates.js'
import { collectTaskRefs, taskRefsFromDecomposition } from './content-trace.js'
import { fmt } from '../../domain/text/fmt.js'

// 分析 API 再导出（调用方继续从本模块 import，不必改）
export {
  traceNumber,
  buildConsistencyRows,
  consistencyGaps,
  taskRefsFromDecomposition,
  collectTaskRefs,
  clauseReceiveStatus,
  unreceivedClauses,
  isRootKind,
  ROOT_PREFIXES_LIKE,
} from './content-trace.js'
export type {
  ConsistencyRow,
  ConsistencyTaskLike,
  ReceiveState,
  ClauseReceiveStatus,
  ReceiveTaskLike,
} from './content-trace.js'
export type { DocsEntry, DocsReader } from './content-gates.js'

/** 读任务对象上的 requirement_refs（同时认 snake_case 与 camelCase，避免写法不一致导致静默漏判）。 */
export function requirementRefsOf(raw: unknown): string[] {
  if (typeof raw !== 'object' || raw === null) return []
  const o = raw as Record<string, unknown>
  const v = o['requirement_refs'] ?? o['requirementRefs']
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}

/**
 * 覆盖门禁（FR-1）：拆分提交前，核对**需求里每条根编号都有落点**——
 * 要么被至少一张任务卡用 requirement_refs 接收，要么被显式标「本轮不做」。
 *
 * 放行条件（任一即跳过，避免误拦）：存量需求 / 需求文档不存在 / 文档里没有编号条款。
 */
export async function assertClauseCoverageGate(
  docs: DocsReader,
  req: RequirementRecord,
  rawTasks: readonly unknown[],
): Promise<GateFailure | undefined> {
  const isLegacy = req.artifacts === undefined || req.artifacts.length === 0
  if (isLegacy) return undefined

  const path = 'docs/requirements/' + req.id + '/requirement.md'
  if (!docs.exists(path)) return undefined

  const doc = parseDocument(await docs.read(path))
  const roots = extractClauseDefinitions(doc)
  if (roots.length === 0) return undefined

  // FR-1（REQ-84bea5）：从"任务对象 ∪ decomposition.md RTM"读取 refs（双源合并）
  const refsFromTasks = rawTasks.flatMap(requirementRefsOf)
  const decompositionPath = 'docs/requirements/' + req.id + '/decomposition.md'
  const refsFromRTM = docs.exists(decompositionPath)
    ? taskRefsFromDecomposition(parseDocument(await docs.read(decompositionPath))).flatMap(t => t.requirement_refs ?? [])
    : []
  const covered = [...new Set([...refsFromTasks, ...refsFromRTM])]
  const skipped = extractSkippedClauses(doc)
  const { gaps } = checkClauseCoverage(roots, covered, { skipped })
  if (gaps.length === 0) return undefined

  return {
    code: 'requirement_uncovered',
    kind: 'decomposition',
    gaps,
    message: fmt(
      'reqboard_decompose 未执行：以下需求条款既没有被任何任务卡接收、也没有标「本轮不做」——{gaps}。请给对应任务卡加 requirement_refs=[...]；确需本轮不做的，在该条款旁显式写明「本轮不做」并给出理由。',
      { gaps: gaps.join(', ') },
    ),
  }
}

// REQ-2d1c74 的闸门独立成模块（尺寸门禁），此处再导出保持既有 import 路径不变
export { checkDesignCompletenessGate, checkDesignDecompositionGate, assertArtifactOpenable } from './design-gates.js'


/**
 * 设计章节可追溯门禁（FR-5，硬拦）：**每个二级章节都必须标注服务哪条功能点**。
 * 缺标注 = 孤儿章节 → design_orphan。
 */
export async function checkDesignServesGate(docs: DocsReader, req: RequirementRecord): Promise<GateFailure | undefined> {
  const isLegacy = req.artifacts === undefined || req.artifacts.length === 0
  if (isLegacy) return undefined

  const designDir = 'docs/requirements/' + req.id + '/design'
  const names = (docs.list?.(designDir) ?? [])
    .filter(e => e.isFile !== false && (e.name ?? '').endsWith('.md'))
    .map(e => e.name ?? '')
    .filter(n => n.length > 0)
  if (names.length === 0) return undefined

  const missing: string[] = []
  for (const name of names) {
    const p = designDir + '/' + name
    if (!docs.exists(p)) continue
    const doc = parseDocument(await docs.read(p))
    for (const sec of checkDesignSectionsHaveServes(doc).missing) missing.push(name + ' → ' + sec)
  }
  if (missing.length === 0) return undefined

  return {
    code: 'design_orphan',
    kind: 'plan',
    gaps: missing,
    message: fmt(
      '提交未执行：以下设计章节**没有标注服务哪条功能点**（缺 serves）——{list}。请给每个二级章节补 serves: FR-#（多值逗号分隔）；确实不服务任何条款的章节应删掉或合并。',
      { list: missing.join('；') },
    ),
  }
}

/**
 * 需求文档格式校验门禁（编号规范强制）——在 submit(requirement) 时立即校验，
 * 避免让用户确认不合格的文档。系统负责格式，人负责内容。
 *
 * 校验项：
 *  1. 必须有根编号（FR-/BUG-/...）
 *  2. 编号不能跳号（连续性）
 *  3. 编号不能重复（唯一性）
 */
export async function checkRequirementDocFormatGate(
  docs: DocsReader,
  req: RequirementRecord,
): Promise<GateFailure | undefined> {
  const isLegacy = req.artifacts === undefined || req.artifacts.length === 0
  if (isLegacy) return undefined

  const path = 'docs/requirements/' + req.id + '/requirement.md'
  if (!docs.exists(path)) return undefined

  const doc = parseDocument(await docs.read(path))
  const roots = extractClauseDefinitions(doc)
  // 判重必须用**不去重**的清单：roots 已 Set 去重，喂给 checkClauseDuplicates 会让计数恒 ≤1（原本的死法）。
  const occurrences = extractClauseDefinitionOccurrences(doc)

  // 🚨 门禁 1：必须有根编号
  if (roots.length === 0) {
    return {
      code: 'requirement_missing_clauses',
      kind: 'requirement',
      message:
        'reqboard_requirement_submit 未执行：需求文档缺少功能编号。' +
        '请为每个功能点添加编号（格式：### FR-1: 功能名称 或 **FR-1: 功能名称**）。' +
        '根据需求类型使用对应前缀：FR（功能）/ BUG（缺陷）/ RF（重构）/ SP（调研）/ DOC（文档）/ CH（维护）',
    }
  }

  // 🚨 门禁 2：编号连续性（不能跳号）
  const sequenceGaps = checkClauseSequence(roots)
  if (sequenceGaps.length > 0) {
    return {
      code: 'requirement_clause_sequence_gap',
      kind: 'requirement',
      gaps: sequenceGaps,
      message:
        'reqboard_requirement_submit 未执行：需求编号不连续（跳号）——' +
        sequenceGaps.join('、') +
        '。请补上缺失的编号，或调整现有编号使其连续（如 FR-1, FR-2, FR-3...）',
    }
  }

  // 🚨 门禁 3：编号唯一性（不能重复）
  const duplicates = checkClauseDuplicates(occurrences)
  if (duplicates.length > 0) {
    return {
      code: 'requirement_clause_duplicates',
      kind: 'requirement',
      gaps: duplicates,
      message:
        'reqboard_requirement_submit 未执行：需求编号重复——' +
        duplicates.join('、') +
        '。每个编号只能出现一次，请检查并合并重复的条款',
    }
  }

  return undefined
}

/**
 * 测试文件是否在**文件头部**声明了覆盖的条款/卡。只扫前 20 行——约定是顶部注释块，
 * 不追求逐函数级标注（那会变成负担且无人维护）。
 */
export function testFileHasServesHeader(text: string): boolean {
  const head = text.split(/\r?\n/).slice(0, 20).join('\n')
  return extractServes(head).length > 0
}

/** 从 design/test-cases.md 的「实际文件」列取测试文件路径。 */
export function testFilesFromDesign(doc: ParsedDoc): string[] {
  const out = new Set<string>()
  for (const t of doc.tables) {
    const i = t.header.findIndex(h => h.includes('实际文件') || h.includes('测试文件') || h === '文件')
    if (i < 0) continue
    for (const row of t.rows) {
      for (const m of (row[i] ?? '').matchAll(/[\w./-]+\.(?:ts|tsx|js|py)/g)) out.add(m[0])
    }
  }
  return [...out].sort()
}

/**
 * 孤儿用例：设计文件里点名了、但**文件头部没声明覆盖条款**的测试文件。
 * 按规范是**警告级**（不阻断），但必须作为可见项出现在验收面上。
 */
export async function collectOrphanTestFiles(docs: DocsReader, req: RequirementRecord): Promise<string[]> {
  const p = 'docs/requirements/' + req.id + '/design/test-cases.md'
  if (!docs.exists(p)) return []
  const files = testFilesFromDesign(parseDocument(await docs.read(p)))
  const orphans: string[] = []
  for (const f of files) {
    if (!docs.exists(f)) continue
    if (!testFileHasServesHeader(await docs.read(f))) orphans.push(f)
  }
  return orphans
}

/**
 * E2E 覆盖读数（FR-11）：从需求文档测试策略表读「有没有 E2E 行」。
 * 返回 undefined = 读数未知（文档缺失/为空）——此时不追加可见项，避免噪声。
 */
export async function e2eCoverageOf(docs: DocsReader, req: RequirementRecord): Promise<boolean | undefined> {
  const p = 'docs/requirements/' + req.id + '/requirement.md'
  if (!docs.exists(p)) return undefined
  const text = await docs.read(p)
  if (text.trim().length === 0) return undefined
  return checkE2ECoverage(parseDocument(text)).hasE2E
}

/** 收集本次需求涉及的全部「带编号条目」：需求条款（根）+ 设计文档各章节（其 serves 指向上游）。 */
export async function collectNumberedItems(docs: DocsReader, req: RequirementRecord): Promise<NumberedItem[]> {
  const base = 'docs/requirements/' + req.id
  const items: NumberedItem[] = []

  const reqPath = base + '/requirement.md'
  if (docs.exists(reqPath)) {
    const doc = parseDocument(await docs.read(reqPath))
    for (const id of extractClauseDefinitions(doc)) items.push({ id, serves: [], kind: 'requirement' })
  }

  const designDir = base + '/design'
  const names = (docs.list?.(designDir) ?? [])
    .filter(e => e.isFile !== false && (e.name ?? '').endsWith('.md'))
    .map(e => e.name ?? '')
    .filter(n => n.length > 0)
  for (const name of names) {
    const p = designDir + '/' + name
    if (!docs.exists(p)) continue
    const doc = parseDocument(await docs.read(p))
    for (const h of doc.headings) {
      if (h.level < 2) continue
      const id = collectIds(h.text)[0]
      if (id === undefined) continue
      items.push({ id, serves: extractServes(h.text), kind: 'design' })
    }
  }
  return items
}

// ---------------------------------------------------------------------------
// 结单证据锚定（FR-4 / T-6）：证据不是"我做了"，而是"这条需求因此被满足了"
// ---------------------------------------------------------------------------

/** 可核验锚点（比计划期的断言词更严）：路径 / 命令 / 数据查询 / 明确的通过计数。 */
export const EVIDENCE_ANCHOR = /\.(ts|tsx|js|mjs|cjs|md|html|json|py|go|css|sh)\b|\b(npx|npm|pnpm|vitest|node|curl|grep|python3?|bash|pytest|sql)\b|SELECT\s|diff\s|\d+\s*(passed|通过)/i

/**
 * 结单证据锚定缺口（FR-4）：证据必须**可定位**——含本卡交付的条款编号，或含可核验锚点
 * （命令 / 路径 / 数据）。"测试通过""已完成"这类空话无法定位到条款，等于没证据。
 *
 * **只在有 RTM 绑定（clauseIds 非空）时生效**：没有绑定的需求无从判"该定位到哪条"，
 * 不做追溯惩罚（与其它内容闸门同语义）。
 */
export function evidenceAnchorGap(clauseIds: readonly string[], evidence: readonly string[]): string | undefined {
  if (clauseIds.length === 0) return undefined
  const texts = evidence.map(e => e.trim()).filter(e => e.length > 0)
  if (texts.length === 0) {
    return '结单证据为空——必须给可核验证据（命令+输出摘要 / 报告路径 / 数据前后对比）'
  }
  const byClause = texts.some(t => clauseIds.some(c => t.includes(c)))
  const byAnchor = texts.some(t => EVIDENCE_ANCHOR.test(t))
  if (byClause || byAnchor) return undefined
  return '证据不可定位（既无条款编号 ' + clauseIds.join('/') + '，也无命令/路径/数据锚点）：' + texts[0].slice(0, 60)
}

/** 结单证据锚定的入参（状态判定在 application 层——tools/ 层不许出现状态字面量）。 */
export interface DoneAnchorInput {
  taskId: string
  /** 目标状态（由调用方原样透传，判定在本模块做） */
  to: string
  tasks: readonly { id: string; requirementId: string; lastReport?: { completed?: readonly string[]; filesChanged?: readonly string[] } | undefined }[]
  boundRequirementIds: readonly string[]
}

/**
 * 结单前的证据锚定校验（FR-4 / T-6）。返回缺口文案（undefined = 通过）。
 *
 * 状态判定刻意留在本层（application）：架构门禁规定 **tools/ 与 http/ 内不得出现状态字面量**，
 * 工具壳只调用、不判断。
 */
export async function doneEvidenceAnchorFailure(docs: DocsReader, input: DoneAnchorInput): Promise<string | undefined> {
  if (input.to !== 'done') return undefined
  const task = input.tasks.find(t => t.id === input.taskId)
  if (task === undefined) return undefined
  if (!input.boundRequirementIds.includes(task.requirementId)) return undefined
  const refs = await collectTaskRefs(docs, { id: task.requirementId })
  const clauseIds = refs.find(r => r.id === task.id)?.requirement_refs ?? []
  const evidence = [...(task.lastReport?.completed ?? []), ...(task.lastReport?.filesChanged ?? [])]
  return evidenceAnchorGap(clauseIds, evidence)
}

/** 编号串联检查结果：failure=悬空（拒）；orphans=根编号无下游（**不拒**，交调用方标红）。 */
export interface NumberChainReport {
  failure?: GateFailure
  orphans: string[]
  items: NumberedItem[]
}

/**
 * 编号串联门禁（FR-2）：**不悬空**硬拦、**不孤儿**只标红。
 * 刻意不把孤儿做成硬拦——多写一份设计却暂时没有下游，是过程状态，不该锁死提交。
 */
export async function checkNumberChainGate(docs: DocsReader, req: RequirementRecord): Promise<NumberChainReport> {
  const isLegacy = req.artifacts === undefined || req.artifacts.length === 0
  if (isLegacy) return { orphans: [], items: [] }

  const items = await collectNumberedItems(docs, req)
  if (items.length === 0) return { orphans: [], items }

  const { dangling, orphans } = checkNumberChain(items)
  if (dangling.length === 0) return { orphans, items }

  return {
    orphans,
    items,
    failure: {
      code: 'dangling_reference',
      kind: 'plan',
      gaps: dangling,
      message: fmt(
        '提交未执行：以下编号引用**悬空**（serves 指向不存在的编号）——{list}。请改为引用真实存在的编号，或先在需求文档补上被引用的那一条。',
        { list: dangling.join('；') },
      ),
    },
  }
}
