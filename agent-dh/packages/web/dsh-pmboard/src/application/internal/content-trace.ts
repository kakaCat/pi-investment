/**
 * 编号图分析（REQ-d3e61a）：双向追溯、三方一致性、需求侧接收标记。
 *
 * 从 content-gate-wiring.ts 拆出（尺寸门禁：宿主单文件 ≤400 行）。拆分依据是**职责**：
 *   - content-gates.ts        纯判定（给定文本 → 缺口）
 *   - content-trace.ts        编号图分析（给定编号图 → 追溯/一致性/接收状态）
 *   - content-gate-wiring.ts  取数 + 闸门组装（读文档 → 产出 GateFailure）
 * 三者的依赖方向单向：wiring → trace → gates。
 *
 * @module dsh-pmboard/application/internal/content-trace
 */
import {
  parseDocument,
  collectIds,
  type DocsReader,
  type NumberedItem,
  type ParsedDoc,
} from './content-gates.js'
import { fmt } from '../../domain/text/fmt.js'

export const ROOT_PREFIXES_LIKE = ['FR', 'BUG', 'RF', 'SP', 'DOC', 'CH'] as const

/** 根编号判定（与 content-gates.isRootId 同语义，此处本地判以免额外耦合）。 */
export function isRootKind(id: string): boolean {
  return ROOT_PREFIXES_LIKE.some(p => id.startsWith(p + '-'))
}

/** 双向查询：给一个编号 → 向下列出全部子孙、向上回溯到根（都做去重与排序）。 */
export function traceNumber(items: readonly NumberedItem[], id: string): { down: string[]; up: string[] } {
  const byId = new Map(items.map(i => [i.id, i]))
  const children = new Map<string, string[]>()
  for (const it of items) {
    for (const s of it.serves) children.set(s, [...(children.get(s) ?? []), it.id])
  }
  const down = new Set<string>()
  const q = [...(children.get(id) ?? [])]
  while (q.length > 0) {
    const cur = q.shift() as string
    if (down.has(cur)) continue
    down.add(cur)
    q.push(...(children.get(cur) ?? []))
  }
  const up = new Set<string>()
  const stack = [id]
  while (stack.length > 0) {
    const cur = stack.pop() as string
    if (up.has(cur)) continue
    up.add(cur)
    for (const s of byId.get(cur)?.serves ?? []) stack.push(s)
  }
  up.delete(id)
  return { down: [...down].sort(), up: [...up].sort() }
}

// ---------------------------------------------------------------------------
// 三方一致性（FR-9 / T-8）：做什么 × 怎么做 × 实际做了什么
// ---------------------------------------------------------------------------

/** 任务侧最小投影（比对用，不依赖 TaskRecord 全字段）。 */
export interface ConsistencyTaskLike {
  id: string
  requirement_refs?: readonly string[]
  requirementRefs?: readonly string[]
  /**
   * 文档里这一行的任务标题。存在的理由：RTM 表的「任务编号」列在实际需求里可能是**计划键**
   * （如 T-5）而不是台账 id（如 t-8e3513）——那是人写拆分计划时的编号法。没有它，取消的卡会被
   * 当成"认不出的外部 id"继续算作已接收，红永远红不出来。
   */
  title?: string
}

/** 一行三方对照。 */
export interface ConsistencyRow {
  requirementId: string
  designIds: string[]
  taskIds: string[]
  verdict: 'consistent' | 'design_missing' | 'impl_missing' | 'out_of_scope' | 'mismatch'
}

/**
 * 三方比对：**验收不是"做完了吗"，而是"做的和说的、设计的，一致吗"**。
 * 四类不一致都必须**显式出现**（不允许沉默）。
 */
export function buildConsistencyRows(
  items: readonly NumberedItem[],
  tasks: readonly ConsistencyTaskLike[],
): ConsistencyRow[] {
  const existing = new Set(items.map(i => i.id))
  const roots = items.filter(i => isRootKind(i.id))
  const designItems = items.filter(i => i.kind === 'design')

  const refsOf = (t: ConsistencyTaskLike): string[] =>
    [...(t.requirement_refs ?? []), ...(t.requirementRefs ?? [])]

  const rows: ConsistencyRow[] = roots.map(root => {
    const designIds = designItems.filter(d => d.serves.includes(root.id)).map(d => d.id)
    const taskIds = tasks.filter(t => refsOf(t).includes(root.id)).map(t => t.id)
    let verdict: ConsistencyRow['verdict'] = 'consistent'
    if (designIds.length === 0) verdict = 'design_missing'
    else if (taskIds.length === 0) verdict = 'impl_missing'
    return { requirementId: root.id, designIds, taskIds, verdict }
  })

  for (const t of tasks) {
    if (refsOf(t).length === 0) rows.push({ requirementId: '', designIds: [], taskIds: [t.id], verdict: 'out_of_scope' })
  }
  for (const d of designItems) {
    for (const s of d.serves) {
      if (!existing.has(s)) rows.push({ requirementId: s, designIds: [d.id], taskIds: [], verdict: 'mismatch' })
    }
  }
  return rows
}

/** 三方一致性缺口（人读文案，进验收单可见项）。一致 → 空数组。 */
export function consistencyGaps(rows: readonly ConsistencyRow[]): string[] {
  const out: string[] = []
  for (const r of rows) {
    if (r.verdict === 'consistent') continue
    if (r.verdict === 'out_of_scope') { out.push(fmt('{task} 超范围：没有任何需求编号承接它（做了没说要做的）', { task: r.taskIds[0] })); continue }
    if (r.verdict === 'mismatch') { out.push(fmt('{design} 悬空引用：它声称服务的编号 {req} 不存在', { design: r.designIds[0], req: r.requirementId })); continue }
    // 两类缺失分别判定并**各报一条**：R9 的形态正是"既无设计、也无实施"，只报一条会漏掉一半信息
    if (r.designIds.length === 0) out.push(fmt('{req} 设计缺失：没有任何设计章节服务它（知道要做什么，不知道怎么做的）', { req: r.requirementId }))
    if (r.taskIds.length === 0) out.push(fmt('{req} 实施缺失：没有任何任务卡接收它（设计好了没做）', { req: r.requirementId }))
  }
  return out
}

/**
 * 从 decomposition.md 的 RTM 覆盖表读「任务 ↔ 根编号」绑定（T-3 起由 decompose 自动生成）。
 * 为什么从这里读：TaskRecord 不存该绑定，而 RTM 表本就是这个绑定的规范载体（标准 §三）。
 * 
 * REQ-260926205654-163a：增加对任务定义中 serves 声明的识别（避免 LLM 手写 requirement_refs 字段时出错）。
 * 双源合并：① RTM 表格（原有）+ ② 任务定义段落中的 **serves: FR-1, FR-2** 或 **requirement_refs**: [...]
 */
export function taskRefsFromDecomposition(doc: ParsedDoc): ConsistencyTaskLike[] {
  const byId = new Map<string, { roots: Set<string>; title: string }>()
  
  // ── 数据源 1：RTM 表格（原有逻辑，保持不变） ──────────────────────
  for (const t of doc.tables) {
    const iRoot = t.header.findIndex(h => h.includes('根编号') || h.includes('需求条款') || h.includes('需求编号'))
    const iTask = t.header.findIndex(h => h.includes('任务') && (h.includes('编号') || h.includes('id') || h.includes('ID')))
    if (iRoot < 0 || iTask < 0) continue
    // 标题列可有可无：机器生成的 RTM 用「任务 id」，人手写的计划表用「任务编号 + 任务标题」
    const iTitle = t.header.findIndex(h => h.includes('标题'))
    for (const row of t.rows) {
      const rootCell = (row[iRoot] ?? '').trim()
      if (rootCell.length === 0 || rootCell.startsWith('—')) continue
      const root = collectIds(rootCell).find(isRootKind)
      const taskId = collectIds(row[iTask] ?? '')[0]
      if (root === undefined || taskId === undefined) continue
      const title = iTitle >= 0 ? (row[iTitle] ?? '').trim().replace(/\*\*/g, '') : ''
      const cur = byId.get(taskId) ?? { roots: new Set<string>(), title }
      cur.roots.add(root)
      if (cur.title.length === 0) cur.title = title
      byId.set(taskId, cur)
    }
  }
  
  // ── 数据源 2：任务定义段落中的 serves 声明（REQ-260926205654-163a 新增） ──
  // 识别模式：
  //   **key**: t1
  //   **serves: FR-1, FR-2**  或  **requirement_refs**: ["FR-1", "FR-2"]
  // 在 key 定义后的 10 行内查找 serves/requirement_refs 声明
  
  const lines = doc.bodyLines
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    
    // 识别 **key**: t1
    const keyMatch = line.match(/^\*\*key\*\*\s*[:：]\s*([a-z0-9_-]+)/i)
    if (!keyMatch) continue
    
    const taskKey = keyMatch[1]
    
    // 在接下来的 10 行内查找 serves 或 requirement_refs
    for (let j = i + 1; j < Math.min(i + 11, lines.length); j++) {
      const nextLine = lines[j]
      
      // 识别 **serves: FR-1, FR-2** 或 **requirement_refs**: ["FR-1"]
      const servesMatch = nextLine.match(/^\*\*(?:serves|requirement_refs)\*\*\s*[:：]\s*(.+)$/i)
      if (servesMatch) {
        // 使用 collectIds 提取所有 FR/BUG/RF/SP/DOC/CH 编号
        const allIds = collectIds(servesMatch[1])
        const rootIds = allIds.filter(isRootKind)
        
        if (rootIds.length > 0) {
          const cur = byId.get(taskKey) ?? { roots: new Set<string>(), title: '' }
          for (const id of rootIds) cur.roots.add(id)
          byId.set(taskKey, cur)
        }
        break
      }
      
      // 遇到下一个任务定义则停止搜索
      if (/^\*\*key\*\*\s*[:：]/i.test(nextLine)) break
    }
  }
  
  return [...byId.entries()].map(([id, v]) => ({
    id,
    requirement_refs: [...v.roots].sort(),
    ...(v.title.length > 0 ? { title: v.title } : {}),
  }))
}

/** 读该需求的 RTM 绑定（decomposition.md 缺失 → 空数组，调用方据此判"无法比对"）。 */
export async function collectTaskRefs(docs: DocsReader, req: { id: string }): Promise<ConsistencyTaskLike[]> {
  const p = 'docs/requirements/' + req.id + '/decomposition.md'
  if (!docs.exists(p)) return []
  return taskRefsFromDecomposition(parseDocument(await docs.read(p)))
}

// ---------------------------------------------------------------------------
// 需求侧接收标记（FR-3 / T-5）：**需求上直接看出谁接了**
// ---------------------------------------------------------------------------

export type ReceiveState = 'done' | 'received' | 'skipped' | 'unreceived'

export interface ClauseReceiveStatus {
  clause: string
  state: ReceiveState
  /** 接收它的任务 id（未接收 → 空数组） */
  by: string[]
}

/** 任务最小投影（判"已完成+证据"用）。 */
export interface ReceiveTaskLike {
  id: string
  status: string
  /** 台账任务的标题（把文档里的计划键解析回任务 id 用） */
  title?: string
  lastReport?: { completed?: readonly string[]; filesChanged?: readonly string[] } | undefined
}

/**
 * 逐条款接收状态（FR-3）。四态与规范一致：
 *   done       已完成（接收它的卡全结单，且至少一条带证据）
 *   received   已被任务接收（列出卡 id）
 *   skipped    本轮裁剪（需求文档里标了理由）
 *   unreceived **未被接收（红）**——既无卡接收、也未裁剪，**这正是 R9 蒸发时的形态**
 */
export function clauseReceiveStatus(
  roots: readonly string[],
  taskRefs: readonly ConsistencyTaskLike[],
  tasks: readonly ReceiveTaskLike[],
  skipped: readonly string[] = [],
): ClauseReceiveStatus[] {
  const byId = new Map(tasks.map(t => [t.id, t]))
  const refsOf = (t: ConsistencyTaskLike): string[] => [...(t.requirement_refs ?? []), ...(t.requirementRefs ?? [])]
  // 文档里的任务标识可能是**计划键**（如 T-5）而不是台账 id（如 t-8e3513）：先按 id 认，认不出再
  // 用标题做**唯一**匹配解析回台账。两者都认不出时保留原文——宁可不标红，也不要把外来的
  // 编号误判成"无人接收"（那会把红变成噪声，最后人人无视红）。
  const titleIndex = new Map<string, string[]>()
  for (const t of tasks) {
    const k = t.title
    if (k === undefined || k.length === 0) continue
    titleIndex.set(k, [...(titleIndex.get(k) ?? []), t.id])
  }
  const resolve = (ref: ConsistencyTaskLike): string => {
    if (byId.has(ref.id)) return ref.id
    const k = ref.title
    if (k !== undefined && k.length > 0) {
      const ids = titleIndex.get(k)
      if (ids !== undefined && ids.length === 1) return ids[0]
    }
    return ref.id
  }
  // 已取消的卡**不再算"交付了这条"**（T-5 验收场景原话：取消某张卡对某条的交付 → 该条回落为
  // 未被接收）。只在"台账里确实存在且已取消"时剔除：台账未覆盖该 id 时维持原判定，
  // 否则只传相关卡的调用方会被误判成"无人接收"。
  return roots.map(clause => {
    const receivers = [...new Set(
      taskRefs.filter(t => refsOf(t).includes(clause)).map(resolve),
    )].filter(id => byId.get(id)?.status !== 'canceled')
    if (receivers.length === 0) {
      return skipped.includes(clause)
        ? { clause, state: 'skipped' as const, by: [] }
        : { clause, state: 'unreceived' as const, by: [] }
    }
    const allDone = receivers.every(id => byId.get(id)?.status === 'done')
    const hasEvidence = receivers.some(id => {
      const r = byId.get(id)?.lastReport
      return r !== undefined && ((r.completed?.length ?? 0) > 0 || (r.filesChanged?.length ?? 0) > 0)
    })
    return allDone && hasEvidence
      ? { clause, state: 'done' as const, by: receivers }
      : { clause, state: 'received' as const, by: receivers }
  })
}

/** 未被接收的条款（红）——调用方据此显眼提示。 */
export function unreceivedClauses(status: readonly ClauseReceiveStatus[]): string[] {
  return status.filter(s => s.state === 'unreceived').map(s => s.clause)
}

// ---------------------------------------------------------------------------
// 设计章节追溯（需求追溯性改进 - 2026-09-26）
// ---------------------------------------------------------------------------

/**
 * 设计章节信息
 */
export interface DesignSection {
  /** 文件路径（如 design/architecture.md） */
  file: string
  /** 章节编号（如 "1.1", "2.3"） */
  section: string
  /** 标题层级（1-6，对应 # 的个数） */
  headingLevel: number
  /** 章节标题（不含编号） */
  title: string
  /** 服务的需求条款（如 ["FR-1", "FR-2"]） */
  serves: string[]
  /** 章节完整内容（到下一个同级标题为止） */
  content: string
}

/**
 * 从设计文档提取所有标注了 serves 的章节
 * 
 * 支持两种标注格式：
 * 1. 行内反引号：## 1. Title `serves: FR-1, FR-2`
 * 2. HTML 注释：## 1. Title <!-- serves: FR-1 -->
 * 
 * @param designDocContent 设计文档内容
 * @param filePath 文件路径（用于返回值）
 * @returns 提取的章节列表
 */
export function extractDesignSections(designDocContent: string, filePath: string): DesignSection[] {
  const lines = designDocContent.split('\n')
  const sections: DesignSection[] = []
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    
    // 匹配标题行
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (!headingMatch) continue
    
    const level = headingMatch[1].length
    const titlePart = headingMatch[2]
    
    // 提取 serves 标注（支持两种格式）
    let serves: string[] = []
    
    // 格式1：反引号 `serves: FR-1, FR-2`
    const backticksMatch = titlePart.match(/`serves:\s*([^`]+)`/)
    if (backticksMatch) {
      serves = backticksMatch[1].split(/[,，]\s*/).map(s => s.trim()).filter(s => s.length > 0)
    } else {
      // 格式2：HTML 注释 <!-- serves: FR-1 -->
      const commentMatch = titlePart.match(/<!--\s*serves:\s*([^-]+)\s*-->/)
      if (commentMatch) {
        serves = commentMatch[1].split(/[,，]\s*/).map(s => s.trim()).filter(s => s.length > 0)
      }
    }
    
    if (serves.length === 0) continue
    
    // 提取章节编号和标题
    const cleanTitle = titlePart
      .replace(/`serves:[^`]+`/, '')
      .replace(/<!--\s*serves:[^-]+-->/, '')
      .trim()
    
    const numberMatch = cleanTitle.match(/^(\d+(?:\.\d+)*)\s+/)
    const sectionNum = numberMatch ? numberMatch[1] : ''
    const title = cleanTitle.replace(/^\d+(?:\.\d+)*\s+/, '').trim()
    
    // 提取章节内容（到下一个同级或更高级标题）
    let contentEnd = i + 1
    const nextHeadingPattern = new RegExp(`^#{1,${level}}\\s+`)
    while (contentEnd < lines.length && !nextHeadingPattern.test(lines[contentEnd])) {
      contentEnd++
    }
    const content = lines.slice(i + 1, contentEnd).join('\n')
    
    sections.push({
      file: filePath,
      section: sectionNum,
      headingLevel: level,
      title,
      serves,
      content
    })
  }
  
  return sections
}

/**
 * 从多个设计文档提取所有章节
 * 
 * @param docs DocsReader 实例
 * @param designDir 设计文档目录（如 docs/requirements/REQ-xxx/design）
 * @returns 所有设计章节
 */
export function extractAllDesignSections(docs: DocsReader, designDir: string): DesignSection[] {
  const allSections: DesignSection[] = []
  
  // 列出设计目录下的所有 .md 文件
  const entries = docs.list?.(designDir) ?? []
  const designFiles = entries
    .filter(e => e.isFile !== false && (e.name ?? '').endsWith('.md'))
    .map(e => e.name ?? '')
    .filter(n => n.length > 0)
  
  // 逐个文件提取章节
  for (const fileName of designFiles) {
    const filePath = `${designDir}/${fileName}`
    const content = docs.read?.(filePath)
    if (!content) continue
    
    const sections = extractDesignSections(content, filePath)
    allSections.push(...sections)
  }
  
  return allSections
}

/**
 * 根据需求条款查找对应的设计章节
 * 
 * @param sections 所有设计章节
 * @param frRefs 需求条款列表（如 ["FR-1", "FR-2"]）
 * @returns 服务这些条款的设计章节
 */
export function findDesignSectionsForFRs(
  sections: readonly DesignSection[],
  frRefs: readonly string[]
): DesignSection[] {
  return sections.filter(s =>
    s.serves.some(fr => frRefs.includes(fr))
  )
}

/**
 * 检查设计覆盖度：所有 FR 是否都有设计章节
 * 
 * @param frList 所有需求条款
 * @param sections 所有设计章节
 * @returns 未被设计覆盖的 FR
 */
export function checkDesignCoverage(
  frList: readonly string[],
  sections: readonly DesignSection[]
): string[] {
  const coveredFRs = new Set<string>()
  for (const section of sections) {
    for (const fr of section.serves) {
      coveredFRs.add(fr)
    }
  }
  
  return frList.filter(fr => !coveredFRs.has(fr))
}

/**
 * 检查实施覆盖度：所有设计章节是否都有任务实现
 * 
 * @param sections 所有设计章节
 * @param taskDesignRefs 任务的设计落点引用（如 ["design/architecture#1.1"]）
 * @returns 未被任务实现的设计章节引用
 */
export function checkImplementationCoverage(
  sections: readonly DesignSection[],
  taskDesignRefs: readonly string[]
): string[] {
  const gaps: string[] = []
  
  for (const section of sections) {
    const sectionRef = `${section.file}#${section.section}`
    const implemented = taskDesignRefs.some(ref => ref === sectionRef)
    if (!implemented) {
      gaps.push(sectionRef)
    }
  }
  
  return gaps
}
