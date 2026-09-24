/**
 * 提示词加载路由唯一入口（REQ-422af1 t3，INV-1）。
 *
 * 注入点只许调 resolveStagePrompt()：分片库来自构建期内联产物（generated/fragments.ts），
 * 解析算法在 router.ts（纯函数）。本模块做"真库绑定 + 元数据校验"，不重复算法。
 *
 * @module dsh-pmboard/domain/prompt
 */
import { GENERATED_FRAGMENTS, type GeneratedFragment } from './generated/fragments.js'
import { inferDifficulty, difficultyMismatch } from './difficulty-inference.js'
import { heavierDifficulty } from './difficulty-mapping.js'
import { resolveFragmentPlan } from './router.js'
import { fmt } from '../text/fmt.js'
import {
  CATEGORIES,
  DIFFICULTIES,
  PROMPT_STAGES,
  type Category,
  type Difficulty,
  type Fragment,
  type PromptStage,
  type ResolvedPrompt,
  type StagePromptRequest,
  type Wildcard,
} from './types.js'

export * from './types.js'
export * from './chain.js'
export { resolveFragmentPlan } from './router.js'
export { applyBudget, assembleText, DEFAULT_PROMPT_BUDGET, isFloor } from './budget.js'

/** 校验 + 收窄生成物的字符串元数据（非法值响亮抛错，不静默当成通配）。 */
function toFragment(generated: GeneratedFragment): Fragment {
  const stage: PromptStage | Wildcard =
    generated.stage === '*' ? '*' : ((PROMPT_STAGES as readonly string[]).includes(generated.stage) ? (generated.stage as PromptStage) : fail('stage', generated))
  const difficulty: Difficulty | Wildcard =
    generated.difficulty === '*' ? '*' : ((DIFFICULTIES as readonly string[]).includes(generated.difficulty) ? (generated.difficulty as Difficulty) : fail('difficulty', generated))
  const category: Category | Wildcard =
    generated.category === '*' ? '*' : ((CATEGORIES as readonly string[]).includes(generated.category) ? (generated.category as Category) : fail('category', generated))
  if (generated.priority !== 'floor' && typeof generated.priority !== 'number') {
    fail('priority', generated)
  }
  return {
    id: generated.id,
    stage,
    difficulty,
    category,
    priority: generated.priority,
    text: generated.text,
    // 组合引用（P2/t8）：类型档的 ① 路由壳只带 include，把节点内容与类型档正文串进同一次注入。
    ...(generated.include === undefined ? {} : { include: generated.include }),
  }
}

function fail(field: string, generated: GeneratedFragment): never {
  throw new Error(fmt('分片 {id} 的 {field} 非法：{value}', {
    id: generated.id, field, value: String(generated[field as keyof GeneratedFragment]),
  }))
}

/** 真分片库（构建期内联；id 唯一）。 */
export const FRAGMENT_LIBRARY: readonly Fragment[] = GENERATED_FRAGMENTS.map(toFragment)

/** 唯一取词入口：resolveStagePrompt(req[, library])。 */
/**
 * 取词难度优先级（REQ-e3b6a0 t6 增补 declaredDifficulty）：
 *  ① 显式 `difficulty`（调用方直给，最高优先，既有语义不变）；
 *  ② `declaredDifficulty` 与"文本推断档"**取重不取轻**（FR-4：宁可多给纪律，不可少给）；
 *  ③ 只有其中一个 → 用它；
 *  ④ 都没有 → 交由 `resolveFragmentPlan` 走 DEFAULT_DIFFICULTY（与改造前完全一致）。
 */
export function resolveStagePrompt(
  req: StagePromptRequest,
  library: readonly Fragment[] = FRAGMENT_LIBRARY,
): ResolvedPrompt {
  const inferred = req.requirement === undefined ? undefined : inferDifficulty(req.requirement)
  const declared = req.declaredDifficulty
  const reasons: string[] = []

  let effectiveDifficulty: Difficulty | undefined = req.difficulty
  if (effectiveDifficulty === undefined && (declared !== undefined || inferred !== undefined)) {
    if (declared !== undefined && inferred !== undefined) {
      const harder = heavierDifficulty(declared, inferred.difficulty)
      if (harder !== declared) {
        reasons.push(fmt('声明档 {declared} 与文本推断档 {inferred} 冲突，按取重不取轻取 {harder}', {
          declared, inferred: inferred.difficulty, harder,
        }))
      }
      effectiveDifficulty = harder
    } else {
      effectiveDifficulty = declared ?? (inferred === undefined ? undefined : inferred.difficulty)
    }
  }
  if (declared !== undefined) reasons.push(fmt('声明难度已映射为取词档 {d}', { d: declared }))
  if (inferred !== undefined) reasons.push(...inferred.reasons)

  const effective: StagePromptRequest = effectiveDifficulty === undefined ? req : { ...req, difficulty: effectiveDifficulty }
  const resolved = resolveFragmentPlan(library, effective)

  // 留痕：显式传的难度与文本推断冲突时，**响亮但不断流**（写进依据，看板可查）。
  const warn = inferred === undefined || req.difficulty === undefined ? undefined : difficultyMismatch(inferred, req.difficulty)
  if (warn !== undefined) reasons.push(warn)
  return reasons.length === 0 ? resolved : { ...resolved, difficultyReasons: reasons }
}

export type { WorktreeEvent, WorktreeEventContext } from './worktree-events.js'
export { WORKTREE_EVENT_TEMPLATES, renderWorktreePrompt } from './worktree-events.js'
