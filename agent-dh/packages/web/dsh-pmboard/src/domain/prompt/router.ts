/**
 * 回退链解析（REQ-422af1 t3）—— 唯一取词算法的纯函数实现。
 *
 * 回退链（难度优先于类型）：
 *   ① (stage, difficulty, category)  精确
 *   ② (stage, difficulty, *)         该类型无专属 → 用难度档
 *   ③ (stage, *, category)           该难度无专属 → 用类型档
 *   ④ (stage, *, *)                  该节点兜底档
 *   ⑤ (*, *, *)                      全局铁律 —— **合并**（不是替代），任何请求都并入
 * ①-④ 取**首个命中**层；⑤ 恒并入。命中层级记 1-4；只有 ①-④ 全空才记 5。
 *
 * 纪律：本模块是纯函数（无 I/O、无 Date.now、无 node:），可单测；分片库由调用方注入
 * （index.ts 用构建期生成的真库），故五种命中层级都能用合成分片精确构造。
 *
 * @module dsh-pmboard/domain/prompt/router
 */
import { applyBudget, assembleText } from './budget.js'
import { fmt } from '../text/fmt.js'
import {
  HIT_LEVEL_LABELS,
  DEFAULT_CATEGORY,
  DEFAULT_DIFFICULTY,
  type Fragment,
  type HitLevel,
  type ResolvedPrompt,
  type StagePromptRequest,
  type Wildcard,
} from './types.js'

interface LevelSpec {
  readonly level: HitLevel
  readonly stage: string
  readonly difficulty: string
  readonly category: string
}

function matches(fragment: Fragment, spec: LevelSpec): boolean {
  return fragment.stage === spec.stage && fragment.difficulty === spec.difficulty && fragment.category === spec.category
}

/** 展开 include 引用 + 去重（同 id 只注入一次；重复引用不报错，未知引用响亮抛错）。 */
function expandIncludes(library: readonly Fragment[], base: readonly Fragment[]): Fragment[] {
  const byId = new Map<string, Fragment>()
  for (const f of library) byId.set(f.id, f)
  const out: Fragment[] = []
  const seen = new Set<string>()
  const push = (fragment: Fragment): void => {
    if (seen.has(fragment.id)) return
    seen.add(fragment.id)
    out.push(fragment)
    for (const dep of fragment.include ?? []) {
      const target = byId.get(dep)
      if (target === undefined) {
        throw new Error(fmt('分片 include 指向不存在的 id：{dep}（来自 {id}）', { dep, id: fragment.id }))
      }
      push(target)
    }
  }
  for (const f of base) push(f)
  return out
}

/**
 * 纯核心：在给定分片库上解析。
 * 返回 text/fragmentIds/routeKey/hitLevel/charCount/trimmed（+ 可选 overBudget 标记）。
 */
export function resolveFragmentPlan(library: readonly Fragment[], req: StagePromptRequest): ResolvedPrompt {
  const difficulty = req.difficulty ?? DEFAULT_DIFFICULTY
  const category = req.category ?? DEFAULT_CATEGORY
  const levels: readonly LevelSpec[] = [
    { level: 1, stage: req.stage, difficulty, category },
    { level: 2, stage: req.stage, difficulty, category: '*' as Wildcard },
    { level: 3, stage: req.stage, difficulty: '*' as Wildcard, category },
    { level: 4, stage: req.stage, difficulty: '*' as Wildcard, category: '*' as Wildcard },
    { level: 5, stage: '*' as Wildcard, difficulty: '*' as Wildcard, category: '*' as Wildcard },
  ]
  let hitLevel: HitLevel = 5
  let selected: readonly Fragment[] = []
  for (const spec of levels.slice(0, 4)) {
    const found = library.filter((f) => matches(f, spec))
    if (found.length > 0) {
      selected = found
      hitLevel = spec.level
      break
    }
  }
  // ⑤ 恒并入（全局铁律是保底层，与节点内容并存），且**永远排在节点内容之后**：
  // 注入顺序 = ①-④ 选中片段（按 id 稳定排序，保证 vendor 原文 → overrides）→ ⑤ 全局铁律。
  // 不能把 ⑤ 与 selected 混在一起按 id 排序——节点名在 'common' 之后的（design 等）
  // 会让铁律排到节点内容前面，与 design/fragments.md §9 的三段顺序冲突。
  const byId = (a: Fragment, b: Fragment): number => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
  const global = library.filter((f) => matches(f, levels[4]!))
  const ordered = [...selected].slice().sort(byId).concat([...global].slice().sort(byId))
  const merged = expandIncludes(library, ordered)
  const outcome = applyBudget(merged, req.budget)
  const text = assembleText(outcome.kept)
  return {
    text,
    fragmentIds: outcome.kept.map((f) => f.id),
    routeKey: req.stage + '/' + difficulty + '/' + category,
    hitLevel,
    charCount: text.length,
    trimmed: outcome.trimmed,
    ...(outcome.overBudget === undefined ? {} : { overBudget: outcome.overBudget }),
  }
}

export { HIT_LEVEL_LABELS }
