/**
 * 分类文档集（REQ-d3e61a T-13 / T-14 · FR-15）：立项类型决定要哪些文档、每份写什么必填节。
 *
 * **两层结构**（T-14 定的形）：
 *   BASE（COMMON_ROOT_SECTIONS）——所有类型都必须有的根文档节，**只定义一次**；
 *   DELTA（CATEGORY_DELTAS）——只有该类型才有的节 + 该类型要求的设计文档。
 *   门禁校验 = BASE + DELTA[类型]。
 *
 * 为什么两层：六份完整副本必然各自漂移（本仓有"两份真相"的教训）。BASE 抽出来后，
 * **删掉 BASE 里任何一条 → 六类同时拒绝**——这既是纪律也是可测的性质。
 *
 * 为什么另立模块而不改 protocol.ts：该文件正被另一窗口占用。本模块是**新增的并列能力**，
 * 不替换既有阶段档案，只回答"这个类型的文档有没有交齐"。
 *
 * 标记载体（同卡）：**逐条状态只存表格行**；front-matter 只放文档级索引——
 * 两处都写必然漂移，故提供 frontmatterStateViolations() 机械探测。
 *
 * @module dsh-pmboard/application/internal/category-doc-sets
 */
import { fmt } from '../../domain/text/fmt.js'

/** BASE：共同骨架——所有立项类型都必须有的根文档节。**只在这里定义一次**。 */
export const COMMON_ROOT_SECTIONS: readonly string[] = ['边界']

// 为什么只留「边界」：它是六类**唯一真正共同**的必填节——"不做什么"是范围纪律的唯一防线，
// feature 的 PRD、bug 的缺陷报告、spike 的调研笔记都得回答它。其余节都是类型专属（见 DELTA）。
// 骨架条目少不代表约束弱：**删除任何一条都会让六类同时拒绝**（tests/base-delta.test.ts 锁死这条性质）。

/** 条件必交设计文档（REQ-2d1c74 FR-1）：需求声明含对应端侧改动时才要求。 */
export interface ConditionalDesignDoc {
  /** 文件名（位于 design/ 目录），目前只有 frontend.md / backend.md */
  name: string
  /** 触发条件：需求声明的端侧 */
  side: 'frontend' | 'backend'
}

export interface CategoryDocDelta {
  category: string
  /** 类型专属必填节（不含 BASE） */
  rootSectionsDelta: readonly string[]
  /** 必须存在的设计文档（文件名，位于 docs/requirements/<REQ>/design/） */
  requiredDesignDocs: readonly string[]
  /** 条件必交：需求声明（front-matter sides）含对应端侧时才要求（REQ-2d1c74 FR-1） */
  conditionalDesignDocs?: readonly ConditionalDesignDoc[]
}

/**
 * 设计文档策略（REQ-2d1c74 FR-1）：从 requirement.md front-matter 解析的端侧声明与豁免声明。
 * 豁免表**原样保留**（含无效条目）——有效性在 missingCategoryDocs 判定时才结论，
 * 无效豁免要在缺失清单里注明，先过滤就把证据弄丢了。
 */
export interface DesignDocPolicy {
  /** 端侧声明（值域 {frontend, backend}，其余忽略） */
  sides: readonly string[]
  /** 豁免表：文件名 → 理由（design_exempt 的 `文件名=理由` 分号分隔表） */
  exempt: Readonly<Record<string, string>>
}

const VALID_SIDES: ReadonlySet<string> = new Set(['frontend', 'backend'])

/** 从 requirement.md front-matter 解析端侧声明与豁免声明（纯函数，零 IO）。 */
export function designDocPolicyFrom(frontmatter: Readonly<Record<string, string>>): DesignDocPolicy {
  const sides = (frontmatter['sides'] ?? '')
    .split(',')
    .map(s => s.trim())
    .filter(s => VALID_SIDES.has(s))
  const exempt: Record<string, string> = {}
  for (const pair of (frontmatter['design_exempt'] ?? '').split(';')) {
    const trimmed = pair.trim()
    if (trimmed === '') continue
    const eq = trimmed.indexOf('=')
    if (eq <= 0) continue // 无等号或空键 → 畸形条目，跳过（按未豁免处理）
    const key = trimmed.slice(0, eq).trim()
    const reason = trimmed.slice(eq + 1).trim()
    exempt[key] = reason
  }
  return { sides, exempt }
}

/** 该类型 + 端侧声明下的有效设计文档清单（必交 ∪ sides 命中的条件必交），供闸门与呈现投影共用。 */
export function effectiveDesignDocs(
  category: string | undefined,
  sides: readonly string[] = [],
): { name: string; conditional?: 'frontend' | 'backend' }[] {
  const delta = deltaFor(category)
  if (delta === undefined) return []
  const docs: { name: string; conditional?: 'frontend' | 'backend' }[] = delta.requiredDesignDocs.map(name => ({ name }))
  for (const c of delta.conditionalDesignDocs ?? []) {
    if (sides.includes(c.side)) docs.push({ name: c.name, conditional: c.side })
  }
  return docs
}

/**
 * DELTA：类型增量。与规范 §0.3 一一对应——
 *   feature  产品定义/用户/功能点 + 全套设计
 *   bug      **复现步骤** / 期望 vs 实际 / 根因 / 回归（免 PRD 那套用户角色，但不取消追溯）
 *   refactor 现状 / 目标结构 / **行为不变式** + 架构与迁移
 *   spike    待答问题 / 结论
 *   doc      目标读者 / 大纲
 *   chore    完成判据（最简）
 */
export const CATEGORY_DELTAS: readonly CategoryDocDelta[] = [
  // REQ-2d1c74 FR-1：feature 全套 = 五份必交（补 use-cases.md）+ 端侧条件必交（frontend/backend）。
  { category: 'feature', rootSectionsDelta: ['产品定义', '用户与角色', '功能点'], requiredDesignDocs: ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md'], conditionalDesignDocs: [{ name: 'frontend.md', side: 'frontend' }, { name: 'backend.md', side: 'backend' }] },
  { category: 'bug', rootSectionsDelta: ['复现步骤', '根因', '回归'], requiredDesignDocs: [] },
  { category: 'refactor', rootSectionsDelta: ['现状', '目标结构', '行为不变式'], requiredDesignDocs: ['architecture.md', 'migration.md'] },
  { category: 'spike', rootSectionsDelta: ['待答问题', '结论'], requiredDesignDocs: [] },
  { category: 'doc', rootSectionsDelta: ['目标读者', '大纲'], requiredDesignDocs: [] },
  { category: 'chore', rootSectionsDelta: ['完成判据'], requiredDesignDocs: [] },
]

/** 取某类型的 DELTA（未知类型 → undefined，不拦）。 */
export function deltaFor(category: string | undefined): CategoryDocDelta | undefined {
  if (category === undefined) return undefined
  return CATEGORY_DELTAS.find(s => s.category === category)
}

/** 该类型要求的根文档必填节 = BASE + DELTA。base 可注入（便于验证"删掉 BASE 会怎样"）。 */
export function requiredRootSectionsFor(
  category: string | undefined,
  base: readonly string[] = COMMON_ROOT_SECTIONS,
): string[] {
  const delta = deltaFor(category)
  if (delta === undefined) return []
  return [...base, ...delta.rootSectionsDelta]
}

export interface CategoryDocCheckInput {
  category?: string
  /** 根文档是否存在（不存在 → 还没到可判阶段，不报缺失） */
  rootExists: boolean
  rootText: string
  designNames: readonly string[]
  /** 注入 BASE（默认共同骨架）；传 [] 即"把 BASE 删空" */
  base?: readonly string[]
  /** 端侧声明（REQ-2d1c74 FR-1）：命中后对应条件必交文档转为必交 */
  sides?: readonly string[]
  /** 豁免表（REQ-2d1c74 FR-1）：文件名 → 理由；未知键/空理由 = 豁免无效 */
  exempt?: Readonly<Record<string, string>>
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * 根文档里是否存在某**节**。刻意用"标题 + 可选编号"的精确匹配，而不是子串包含——
 * 子串会让 spike 的必填节「待答问题」冒充 BASE 的「问题」，导致节被删掉却判为存在（实测踩过）。
 */
export function hasRootSection(rootText: string, name: string): boolean {
  const re = new RegExp('^#{1,6}\\s*(?:[0-9]+\\s*[.、]\\s*)?' + escapeRe(name) + '\\s*(?:[（(:：].*)?$', 'm')
  return re.test(rootText)
}

/** 缺失清单（人读文案） = BASE + DELTA 的根文档节 + DELTA 的设计文档。 */
export function missingCategoryDocs(input: CategoryDocCheckInput): string[] {
  const delta = deltaFor(input.category)
  if (delta === undefined) return []
  if (!input.rootExists) return []

  const missing: string[] = []
  for (const sec of requiredRootSectionsFor(input.category, input.base)) {
    if (!hasRootSection(input.rootText, sec)) missing.push(fmt('requirement.md 缺必填节「{sec}」', { sec }))
  }
  // REQ-2d1c74 FR-1：有效必交 = 必交 ∪ sides 命中的条件必交 − 有效豁免。
  // 豁免有效性：键命中该类型文档集（必交 ∪ 全部条件必交）且理由非空；
  // 未知键/空理由 = 豁免无效，按未豁免处理并在缺失清单中注明（数据模型设计 §2）。
  const knownDocs = new Set([
    ...delta.requiredDesignDocs,
    ...(delta.conditionalDesignDocs ?? []).map(c => c.name),
  ])
  const exempt = input.exempt ?? {}
  for (const { name: doc } of effectiveDesignDocs(input.category, input.sides ?? [])) {
    if (input.designNames.includes(doc)) continue
    const reason = exempt[doc]
    if (reason !== undefined && reason.trim() !== '') continue // 有效豁免
    if (reason !== undefined) {
      missing.push(fmt('design/{doc} 未交（豁免无效：理由为空）', { doc }))
    } else {
      missing.push(fmt('design/{doc} 未交', { doc }))
    }
  }
  for (const key of Object.keys(exempt)) {
    if (!knownDocs.has(key)) missing.push(fmt('design_exempt 含未知键「{key}」（不在该类型文档集内，豁免不生效）', { key }))
  }
  return missing
}

/**
 * 标记载体规则（T-14）：**逐条状态只存表格行**。front-matter 只放**文档级**索引
 * （req_id / title / status / owner / category …）。
 *
 * 违反形态：把逐条状态塞进 front-matter——键里带编号（如 FR1_status / t-aaa111_evidence）。
 * 两处都写必然漂移（本仓"两份真相"教训），故机械探测并回报。
 */
export const FRONTMATTER_PER_ITEM_KEY = /(?:FR|BUG|RF|SP|DOC|CH|TC)-?\d|^t-[0-9a-f]{6}/i

export function frontmatterStateViolations(frontmatter: Readonly<Record<string, string>>): string[] {
  return Object.keys(frontmatter).filter(k => FRONTMATTER_PER_ITEM_KEY.test(k))
}
