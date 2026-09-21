/**
 * 注入留痕（REQ-422af1 t6，INV-6）—— "这次到底注入了什么"的可查台账。
 *
 * 本模块是**纯逻辑**（记录类型 + ring buffer + 只读查询 + 条目组装）：不 import node:
 * （application 层硬约束，tests/layer-boundary.test.ts 机械检查）。落盘由适配器
 * adapters/InjectionLogFile.ts 实现（原子写 + 串行队列），本模块不碰 fs、不取时间
 * （at 由适配器落章）。
 *
 * 容量有界：ring buffer 保留最近 INJECTION_LOG_CAP=500 条（高频写入不放大文件）。
 *
 * @module dsh-pmboard/application/internal/injection-log
 */
import { HIT_LEVEL_LABELS, type ResolvedPrompt } from '../../domain/prompt/index.js'
import { fmt } from '../../domain/text/fmt.js'

/** ring buffer 保留条数（与 design/architecture.md §2 一致）。 */
export const INJECTION_LOG_CAP = 500

/** 留痕文件的相对位置（相对 DSH 主目录）。 */
export const INJECTION_LOG_REL = 'state/prompt-injection-log.json'

/** 一条注入留痕（十字段）。 */
export interface InjectionLogEntry {
  /** 写入时刻（epoch ms；由适配器注入的 clock 落章） */
  at: number
  windowKey: string
  stage: string
  difficulty: string
  category: string
  routeKey: string
  /** 命中层级标签（exact/②/③/④/⑤） */
  hitLevel: string
  fragmentIds: string[]
  charCount: number
  /** 因预算被裁掉的片段 id */
  trimmed: string[]
  /** 难度推断依据（FR-16）。可选：兼容历史条目（当时没有推断）。 */
  difficultyReasons?: string[]
}

/** 写入侧入参（不含 at——时间由适配器统一落章）。 */
export type InjectionLogInput = Omit<InjectionLogEntry, 'at'>

/** 留痕端口：注入点只调 record（同步返回，落盘由实现方串行化）。 */
export interface InjectionLogPort {
  record(entry: InjectionLogInput): void
}

/**
 * 留痕的**只读**端口（REQ-422af1 t11）：看板只读回查「本次注入了什么」，
 * 不引入任何写操作——读侧与写侧在类型上就分开，避免看板顺手多出一个写入口。
 */
export interface InjectionLogReadPort {
  /** 只读全量（缺文件 → []；损坏 → 抛错，由调用方决定是否降级）。 */
  readAll(): Promise<InjectionLogEntry[]>
}

/** 十字段字段名（读回校验 / 单测断言共用单点）。 */
export const INJECTION_LOG_FIELDS: readonly (keyof InjectionLogEntry)[] = [
  'at', 'windowKey', 'stage', 'difficulty', 'category', 'routeKey', 'hitLevel', 'fragmentIds', 'charCount', 'trimmed',
]

/**
 * 由解析结果组装留痕入参。difficulty/category 从 routeKey 拆出（routeKey 的单一事实源
 * 就在解析结果里，避免调用方再传一遍造成漂移）。
 */
export function injectionLogInputFromResolved(resolved: ResolvedPrompt, windowKey: string): InjectionLogInput {
  const [stage, difficulty, category] = resolved.routeKey.split('/')
  return {
    windowKey,
    stage: stage ?? '',
    difficulty: difficulty ?? '',
    category: category ?? '',
    routeKey: resolved.routeKey,
    hitLevel: HIT_LEVEL_LABELS[resolved.hitLevel],
    fragmentIds: [...resolved.fragmentIds],
    charCount: resolved.charCount,
    trimmed: [...resolved.trimmed],
    ...(resolved.difficultyReasons !== undefined && resolved.difficultyReasons.length > 0
      ? { difficultyReasons: [...resolved.difficultyReasons] }
      : {}),
  }
}

/** ring buffer 追加：保留最近 cap 条（超界丢最旧）。cap 非法 → 响亮抛错。 */
export function appendToInjectionLog(
  existing: readonly InjectionLogEntry[],
  entry: InjectionLogEntry,
  cap: number = INJECTION_LOG_CAP,
): InjectionLogEntry[] {
  if (!Number.isInteger(cap) || cap <= 0) {
    throw new Error(fmt('injection-log cap 必须是正整数，收到 {cap}', { cap }))
  }
  const next = [...existing, entry]
  return next.length > cap ? next.slice(next.length - cap) : next
}

/** 只读查询：最近 k 条（保持写入顺序，旧→新）。k 非法 → 响亮抛错。 */
export function queryInjectionLog(entries: readonly InjectionLogEntry[], k: number): InjectionLogEntry[] {
  if (!Number.isInteger(k) || k < 0) {
    throw new Error(fmt('injection-log 查询条数必须是非负整数，收到 {k}', { k }))
  }
  return entries.slice(Math.max(0, entries.length - k))
}

/** 一条记录是否含全部十字段且类型正确（读回时防残缺记录混入）。 */
export function isInjectionLogEntry(raw: unknown): raw is InjectionLogEntry {
  if (typeof raw !== 'object' || raw === null) return false
  const o = raw as Record<string, unknown>
  if (typeof o.at !== 'number' || !Number.isFinite(o.at)) return false
  for (const key of ['windowKey', 'stage', 'difficulty', 'category', 'routeKey', 'hitLevel'] as const) {
    if (typeof o[key] !== 'string') return false
  }
  if (typeof o.charCount !== 'number' || !Number.isFinite(o.charCount)) return false
  if (!Array.isArray(o.fragmentIds) || !o.fragmentIds.every((x) => typeof x === 'string')) return false
  if (!Array.isArray(o.trimmed) || !o.trimmed.every((x) => typeof x === 'string')) return false
  return true
}
