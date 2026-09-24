/**
 * H3 注入「作答后所处阶段」纪律提示词（REQ-e3b6a0 t6 / FR-4）。
 *
 * 三条纪律：
 *  ① **取词唯一入口**：只调 `resolveStagePrompt`（INV-1），不新写文案常量表；
 *  ② **时序正确**：本 handler 在链里排在 H1（落章/推进）之后，故 `ctx.to` 就是"作答后所处阶段"；
 *  ③ **闸门一致**：先过 `isPromptStage` 与 `stageEnabledFor`（分类档案跳过的阶段不注入）。
 *
 * 产出去向：写进链的交换区 `scratch.promptText`，由 H4 按 D5 分流（H2 已压缩进输入包时只发摘要，
 * H2 跳过/降级时才随唤醒消息带全文）。同时按 INV-6 写注入留痕。
 *
 * @module dsh-pmboard/application/gate/handlers/h3-inject
 */
import { fmt } from '../../../domain/text/fmt.js'
import { isPromptStage, resolveStagePrompt, type ResolvedPrompt, type StagePromptRequest } from '../../../domain/prompt/index.js'
import { difficultyFromDeclaredPrompt } from '../../../domain/prompt/difficulty-mapping.js'
import { stageEnabledFor } from '../../../shared/protocol.js'
import type { RequirementRecord } from '../../../shared/protocol.js'
import type { ReqboardRepository } from '../../ports.js'
import { injectionLogInputFromResolved, type InjectionLogPort } from '../../internal/injection-log.js'
import { augmentResolvedPrompt } from '../../internal/injection-address.js'
import { isInProgressTask } from '../../../domain/status/Predicates.js'
import type { ChainInput, GateHandler, HandlerOutcome } from '../GatePostChain.js'
import { pickGateRequirement, reasonOf } from './shared.js'

export interface H3InjectDeps {
  repo: ReqboardRepository
  /** 注入留痕端口（INV-6）；未注入 = 不留痕（结果仍可从 scratch 断言）。 */
  injectionLog?: InjectionLogPort
  /** 取词入口（INV-1）；测试可换替身。 */
  resolve?: (req: StagePromptRequest) => ResolvedPrompt
  /** 模板根绝对路径（T-3）；缺省 = 不注入地址段（与改造前逐字一致）。 */
  templateRoot?: string
  /** 地址段开关（T-3；默认 true）。 */
  addressSectionEnabled?: boolean
}

/** 地址段增强（T-3）：开关关/根缺失 → 原样返回；渲染异常 → 原样返回（沿用既有降级留痕，不静默破坏）。 */
function withAddress(resolved: ResolvedPrompt, deps: H3InjectDeps, requirement: RequirementRecord, stage: StagePromptRequest['stage']): ResolvedPrompt {
  if (deps.addressSectionEnabled === false || deps.templateRoot === undefined) return resolved
  const currentTask = deps.repo.snapshot().tasks.find(t => t.requirementId === requirement.id && isInProgressTask(t))
  try {
    return augmentResolvedPrompt(resolved, {
      stage,
      category: requirement.category,
      requirement,
      ...(currentTask === undefined ? {} : { currentTask: { id: currentTask.id, title: currentTask.title, cardDoc: currentTask.cardDoc } }),
      templateRoot: deps.templateRoot,
    })
  } catch {
    return resolved
  }
}

/** 组装 H3 handler。**永不抛**：任何意外都被就地降级为 degraded。 */
export function createH3InjectHandler(deps: H3InjectDeps): GateHandler {
  const resolve = deps.resolve ?? resolveStagePrompt

  return {
    name: 'h3-inject',
    async run({ ctx, scratch }: ChainInput): Promise<HandlerOutcome> {
      try {
        if (!isPromptStage(ctx.to)) {
          return { kind: 'skip', code: 'not_prompt_stage', reason: fmt('阶段 {to} 无纪律提示词可注入', { to: ctx.to }) }
        }
        const requirement = pickGateRequirement(deps.repo, ctx)
        if (requirement === undefined) {
          return { kind: 'skip', code: 'no_requirement', reason: '本窗口无可归属需求，取词缺少需求实质' }
        }
        if (!stageEnabledFor(requirement.category, ctx.to)) {
          return { kind: 'skip', code: 'stage_disabled', reason: fmt('分类 {c} 的档案跳过阶段 {to}，不注入', { c: requirement.category ?? '（未标）', to: ctx.to }) }
        }
        // T-4（FR-10）：非肯定答复不注入「作答后所处阶段」的纪律——否则改一版反而收到下一节点的
        // 推进纪律（本轮实测缺陷）。verdict 缺省（H1 未跑到/异常）按保守的 negative 处理。
        if (ctx.verdict !== 'affirmative') {
          return { kind: 'skip', code: 'negative_verdict', reason: '非肯定答复：不注入下一节点纪律（FR-10）' }
        }
        const declared = difficultyFromDeclaredPrompt(requirement.promptDifficulty)
        const located = resolve({
          stage: ctx.to,
          category: requirement.category,
          requirement: { title: requirement.title, description: requirement.description },
          ...(declared === undefined ? {} : { declaredDifficulty: declared }),
        })
        if (located.text.length === 0) {
          return { kind: 'degraded', code: 'empty_prompt', reason: '取词结果为空（分片库缺该阶段）' }
        }
        const resolved = withAddress(located, deps, requirement, ctx.to)
        deps.injectionLog?.record(injectionLogInputFromResolved(resolved, ctx.windowKey))
        if (scratch !== undefined) scratch.promptText = resolved.text
        return { kind: 'continue' }
      } catch (error) {
        return { kind: 'degraded', code: 'h3_threw', reason: fmt('H3 注入异常：{err}', { err: reasonOf(error) }) }
      }
    },
  }
}
