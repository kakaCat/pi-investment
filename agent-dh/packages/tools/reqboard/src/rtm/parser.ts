/**
 * 文档标注解析器（REQ-260926140539-457b FR-3 / FR-4）。
 *
 * 只解析**标注**，不做业务判断：`**FR-N: 标题`（需求点）、
 * 设计章节标题 + `serves: FR-x`（设计服务哪些 FR）、`covers: t-xxx`（测试覆盖哪些任务）。
 * 解析失败一律降级为空集合（FR-9），由覆盖度统计把缺口**响亮**暴露为 uncovered。
 *
 * @module @pi-investment/reqboard/rtm/parser
 */
import type { DesignSection, FR, RTMTaskLike, TestCase } from './types.js'

/** 设计/测试文档输入。 */
export interface ParseFile {
  /** 需求目录内相对路径，如 design/architecture.md */
  path: string
  content: string
}

const FR_LINE = /^(?:\*\*|\s*#{2,6}\s*)\s*FR-(\d+)\s*[:：]\s*(.+?)\s*\**\s*$/
const HEADING = /^(#{2,6})\s+(.+?)\s*$/
const SERVES_INLINE = /serves\s*[:：]\s*([^。；;]*)/g
const FR_TOKEN = /FR-\d+/g
const TASK_TOKEN = /t-[0-9a-z]{4,}/g

/** 去掉行尾多余标记（** 等）。 */
function tidy(text: string): string {
  return text.replace(/\*+\s*$/, '').trim()
}

/** 从一段文本里取出所有 FR-x。 */
export function extractFRTokens(text: string): string[] {
  return [...new Set(text.match(FR_TOKEN) ?? [])]
}

/** 从一段文本里取出所有 t-xxxx 任务 id。 */
export function extractTaskTokens(text: string): string[] {
  return [...new Set(text.match(TASK_TOKEN) ?? [])]
}

/** 是否为代码围栏行（``` 开头）。 */
function isFence(line: string): boolean {
  const t = line.trimStart()
  return t.charCodeAt(0) === 96 && t.charCodeAt(1) === 96 && t.charCodeAt(2) === 96
}

/**
 * 解析 requirement.md 提取功能点列表。
 * 匹配行首的 `**FR-1: 标题` 或 `### FR-1: 标题`；代码围栏内的示例不计。
 */
export function parseRequirementFRs(content: string, source = 'requirement.md'): FR[] {
  const out: FR[] = []
  const seen = new Set<string>()
  let fence = false
  let frontMatter = false
  let sawFrontMatter = false
  const lines = content.split(/\r?\n/)
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? ''
    if (i === 0 && line.trim() === '---') {
      frontMatter = true
      sawFrontMatter = true
      continue
    }
    if (frontMatter) {
      if (line.trim() === '---') frontMatter = false
      continue
    }
    if (isFence(line)) {
      fence = !fence
      continue
    }
    if (fence) continue
    const m = FR_LINE.exec(line)
    if (m === null) continue
    const id = `FR-${m[1]}`
    if (seen.has(id)) continue
    seen.add(id)
    out.push({ id, title: tidy(m[2] ?? ''), source, line: i + 1 })
  }
  void sawFrontMatter
  return out
}

/** 把标题文本转成稳定的 section 标识（无编号时用）。 */
function slugify(title: string): string {
  return title
    .replace(/[\s]+/g, '-')
    .replace(/[^\p{L}\p{N}-]/gu, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 60)
}

/**
 * 解析设计文档：提取带编号的章节标题，以及该章节的 serves 标注
 * （标题同行 `... serves: FR-1, FR-2` 或紧随其后的独立 `serves:` 行）。
 */
export function parseDesignSections(files: readonly ParseFile[]): DesignSection[] {
  const byRef = new Map<string, DesignSection>()
  for (const file of files) {
    let current: DesignSection | null = null
    let fence = false
    let frontMatter = false
    const lines = file.content.split(/\r?\n/)
    const flush = () => {
      if (current === null) return
      const key = current.ref
      const prev = byRef.get(key)
      if (prev === undefined) byRef.set(key, current)
      else prev.serves = [...new Set([...prev.serves, ...current.serves])]
    }
    for (let i = 0; i < lines.length; i += 1) {
      const line = lines[i] ?? ''
      if (i === 0 && line.trim() === '---') {
        frontMatter = true
        continue
      }
      if (frontMatter) {
        if (line.trim() === '---') frontMatter = false
        continue
      }
      if (isFence(line)) {
        fence = !fence
        continue
      }
      if (fence) continue

      const h = HEADING.exec(line)
      if (h !== null) {
        flush()
        const raw = h[2] ?? ''
        const serves: string[] = []
        let titleText = raw
        let mm: RegExpExecArray | null
        SERVES_INLINE.lastIndex = 0
        while ((mm = SERVES_INLINE.exec(raw)) !== null) {
          serves.push(...extractFRTokens(mm[1] ?? ''))
        }
        titleText = raw.replace(/serves\s*[:：][^。；;]*/g, '').trim()
        const num = /^(\d+(?:\.\d+)*)[.、]?\s*(.*)$/.exec(titleText)
        const section = num !== null ? (num[1] as string) : slugify(titleText)
        if (section.length === 0) {
          current = null
          continue
        }
        current = {
          ref: `${file.path}#${section}`,
          title: tidy(num !== null ? (num[2] ?? titleText) : titleText),
          serves: [...new Set(serves)],
          file: file.path,
          section,
        }
        continue
      }
      if (current === null) continue
      const sv = /serves\s*[:：]\s*(.+)$/.exec(line)
      if (sv !== null) {
        current.serves = [...new Set([...current.serves, ...extractFRTokens(sv[1] ?? '')])]
      }
    }
    flush()
  }
  return [...byRef.values()]
}

/** 任务声明服务的 FR（serves / requirement_refs 归一）。 */
export function taskServes(task: RTMTaskLike): string[] {
  return [...new Set(task.serves ?? [])]
}

/** 每个任务直接声明实现的设计章节（task.implements）。 */
export function parseTaskImplements(tasks: readonly RTMTaskLike[]): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const t of tasks) {
    if (typeof t.implements === 'string' && t.implements.length > 0) out[t.id] = [t.implements]
  }
  return out
}

/**
 * 解析测试文档提取用例（`covers: t-xxx` / `validates: FR-x`）。
 * 用例 id 优先取最近标题里的 TC-N，否则按出现顺序编号。
 */
export function parseTestCovers(files: readonly ParseFile[]): TestCase[] {
  const out: TestCase[] = []
  const usedIds = new Set<string>()
  let seq = 0
  const nextId = (): string => {
    let id = ''
    do {
      seq += 1
      id = `TC-${seq}`
    } while (usedIds.has(id))
    return id
  }
  for (const file of files) {
    let currentTitle = ''
    let currentId = ''
    let pendingCovers: string[] = []
    let pendingValidates: string[] = []
    let fence = false
    const flush = () => {
      if (pendingCovers.length === 0) {
        pendingCovers = []
        pendingValidates = []
        return
      }
      const id = currentId.length > 0 && !usedIds.has(currentId) ? currentId : nextId()
      usedIds.add(id)
      out.push({
        id,
        title: currentTitle.length > 0 ? currentTitle : id,
        covers: [...new Set(pendingCovers)],
        validates: [...new Set(pendingValidates)],
        source: file.path,
      })
      pendingCovers = []
      pendingValidates = []
    }
    const lines = file.content.split(/\r?\n/)
    for (const line of lines) {
      if (isFence(line)) {
        fence = !fence
        continue
      }
      if (fence) continue
      const h = HEADING.exec(line)
      if (h !== null) {
        flush()
        currentTitle = tidy((h[2] ?? '').replace(/serves\s*[:：][^。；;]*/g, ''))
        const tc = /(?:^|\s)(TC-\d+)/.exec(h[2] ?? '')
        currentId = tc !== null ? (tc[1] as string) : ''
        continue
      }
      const cv = /\bcovers\s*[:：]\s*(.+)$/.exec(line)
      if (cv !== null) pendingCovers.push(...extractTaskTokens(cv[1] ?? ''))
      const vd = /\bvalidates\s*[:：]\s*(.+)$/.exec(line)
      if (vd !== null) pendingValidates.push(...extractFRTokens(vd[1] ?? ''))
    }
    flush()
  }
  return out
}

/**
 * 解析 decomposition.md §1「根编号 ↔ 任务卡」对照表，得到 任务 → FR 的 serves 映射。
 * 表行形如：| FR-1 | t-8c8edc | 实现 ... |
 */
export function parseDecompositionServes(content: string): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const line of content.split(/\r?\n/)) {
    const cells = line.split('|').map(c => c.trim())
    if (cells.length < 4) continue
    for (let i = 1; i < cells.length - 1; i += 1) {
      const fr = cells[i] ?? ''
      const task = cells[i + 1] ?? ''
      if (!/^FR-\d+$/.test(fr) || !/^t-[0-9a-z]{4,}$/.test(task)) continue
      const list = out[task] ?? []
      if (!list.includes(fr)) list.push(fr)
      out[task] = list
    }
  }
  return out
}
