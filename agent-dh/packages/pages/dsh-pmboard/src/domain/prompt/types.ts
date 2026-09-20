/**
 * 提示词加载路由的领域类型与常量（REQ-422af1 t3）。
 *
 * 纯类型 + 常量：不 import node:/@deepseek-ai/，不碰时间与随机数（domain 层硬约束，
 * tests/layer-boundary.test.ts 机械检查）。路由键 = (节点, 难度, 类型)。
 *
 * @module dsh-pmboard/domain/prompt/types
 */
import type { RequirementCategory } from '../requirement/Requirement.js'
// 阶段键的权威定义在叶子模块 domain/stage/StagePromptSpec（供 shared/protocol 值再导出而不打包分片）。
import { ALL_STAGE_PROMPT_KEYS, type StagePromptKey } from '../stage/StagePromptSpec.js'

/** 通配符（回退链里未指定的维度）。 */
export type Wildcard = '*'

/** 难度两档：决定"仪式强度"（轻档精简、重档完整）。 */
export type Difficulty = 'light' | 'heavy'

/** 立项类型（沿用需求分类，不新增维度）。 */
export type Category = RequirementCategory

/**
 * 可注入节点（6 个）。draft 是入口态、done 是 legacy，都不注入纪律提示词——
 * 与既有 StagePromptKey 语义一致，故这里是提示词域的单一事实源。
 */
/** 可注入节点（6 个）——别名到叶子模块的阶段键，保持单一事实源。 */
export type PromptStage = StagePromptKey

/** 全部可注入节点（顺序 = 流水线顺序）。 */
export const PROMPT_STAGES: readonly PromptStage[] = ALL_STAGE_PROMPT_KEYS

/**
 * 该状态是否是可注入节点。draft（入口态）、done（legacy）与 canceled 都**不是**——
 * 它们不该拿到任何阶段纪律。⑤ 全局铁律现已有正文，若注入点不先过这道闸，
 * draft 会只捞到铁律文本（无节点内容）而被误判成"有提示词"。
 */
export function isPromptStage(value: unknown): value is PromptStage {
  return typeof value === 'string' && (PROMPT_STAGES as readonly string[]).includes(value)
}

export const DIFFICULTIES: readonly Difficulty[] = ['light', 'heavy']

/** 全部立项类型（与 CATEGORY_FLOW_PROFILES 的键一致）。 */
export const CATEGORIES: readonly Category[] = ['feature', 'bug', 'doc', 'refactor', 'spike', 'chore']

/** 缺省难度：无显式声明时保守取轻档（P1 起 light/heavy 已分化；升级由节点内纪律单向触发）。 */
export const DEFAULT_DIFFICULTY: Difficulty = 'light'
/** 缺省类型：与 flowProfileFor 的缺省一致（未标分类按 feature 走）。 */
export const DEFAULT_CATEGORY: Category = 'feature'

/**
 * 分片：一份可注入文本 + 路由元数据。
 * priority='floor' = 清单/闸门/红旗这类**保底件**，预算裁剪永不触碰。
 */
export interface Fragment {
  readonly id: string
  readonly stage: PromptStage | Wildcard
  readonly difficulty: Difficulty | Wildcard
  readonly category: Category | Wildcard
  readonly priority: number | 'floor'
  readonly text: string
  /** 组合引用：本分片依赖的其它分片 id（同一次注入里展开；重复引用只注入一次）。 */
  readonly include?: readonly string[]
}

/** 一次解析请求。difficulty/category 缺省时取 DEFAULT_*；budget 缺省 = 不裁剪。 */
export interface StagePromptRequest {
  readonly stage: PromptStage
  readonly difficulty?: Difficulty
  readonly category?: Category
  readonly budget?: number
  /**
   * 需求实质（标题 + 描述）。给了它、且未显式传 difficulty 时，难度**由需求推断**
   * （FR-16：动架构 / 跨多子系统 / 改数据模型 / 新增子系统 / 规模大 → heavy），
   * 不再静默回落 DEFAULT_DIFFICULTY。
   */
  readonly requirement?: { readonly title?: string; readonly description?: string }
  /**
   * 需求**声明**的取词档位（已由 difficultyFromDeclaredPrompt 映射；REQ-e3b6a0 t6）。
   * 与文本推断冲突时**取重不取轻**（宁可多给纪律）；与显式 `difficulty` 冲突时以显式为准。
   */
  readonly declaredDifficulty?: Difficulty
}

/** 命中层级：1=①精确 / 2=②难度档 / 3=③类型档 / 4=④节点兜底 / 5=⑤全局铁律（合并）。 */
export type HitLevel = 1 | 2 | 3 | 4 | 5

/** 命中层级的人类可读标签（留痕与文档用）。 */
export const HIT_LEVEL_LABELS: Readonly<Record<HitLevel, string>> = {
  1: 'exact', 2: '②', 3: '③', 4: '④', 5: '⑤',
}

/** 预算超限的结构化标记：连保底件都放不下时报出，不静默裁保底。 */
export interface BudgetOverflow {
  readonly reason: 'floor-exceeds-budget'
  /** 保底件自身字符数 */
  readonly floorChars: number
  readonly budget: number
}

/** 解析结果（对外契约）。 */
export interface ResolvedPrompt {
  /** 注入文本（非空片段以空行分隔拼接；空片段不产生字符）。 */
  readonly text: string
  /** 实际注入的分片 id（去重、顺序稳定） */
  readonly fragmentIds: readonly string[]
  /** 请求路由键 stage/difficulty/category */
  readonly routeKey: string
  readonly hitLevel: HitLevel
  readonly charCount: number
  /** 因预算被裁掉的分片 id */
  readonly trimmed: readonly string[]
  /** 连保底都超预算时的结构化超限标记（存在即未静默） */
  readonly overBudget?: BudgetOverflow
  /** 难度推断依据（FR-16）。非空 = 本次难度按需求实质推断，供注入留痕与看板核查。 */
  readonly difficultyReasons?: readonly string[]
}
