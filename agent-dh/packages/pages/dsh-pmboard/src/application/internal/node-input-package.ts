/**
 * 节点输入包构造（REQ-422af1 t9 / INV-9）——节点边界遗弃后模型可见面的**唯一新起点**。
 *
 * 内容 = 路由结果（resolveStagePrompt） + 需求文档投影 + 台账投影；**不读会话历史**，
 * 不引用任何前序对话摘录（INV-9）。这是"遗弃上下文后仍能续跑"的前提：新窗口只看本包
 * 也能说出当前节点、上游结论、下一步用哪个工具。
 *
 * 纯函数 + 端口只读投影：不 import node:/@deepseek-ai/（application 层硬约束），
 * 不碰时间与随机数。用例编排在 use-cases/IsolateNodeContext.ts。
 *
 * @module dsh-pmboard/application/internal/node-input-package
 */
import {
  STAGE_CHAIN,
  resolveStagePrompt,
  type Category,
  type Difficulty,
  type PromptStage,
  type ResolvedPrompt,
} from '../../domain/prompt/index.js'
import { fmt } from '../../domain/text/fmt.js'
import type { RequirementRecord, StageArtifact } from '../../shared/protocol.js'

/** 台账投影（INV-8 五字段的输入包侧承载）。 */
export interface LedgerProjection {
  /** 当前节点 */
  currentStage: string
  /** 上游结论：已确认产物 */
  upstream: string
  /** 未决问题：未确认产物 + 阻塞 + 文档待同步 */
  openQuestions: string
  /** 下一步：链声明 */
  next: string
  /** 证据指针：产物路径 */
  evidence: string
}

const NONE_UPSTREAM = '（无已确认产物）'
const NONE_OPEN = '（无）'
const NONE_EVIDENCE = '（无）'
const NO_REQUIREMENT = '（无归属需求，台账投影不可用）'

function artifactLabel(a: StageArtifact): string {
  return fmt('{kind}（{path}）', { kind: a.kind, path: a.path })
}

/**
 * 台账投影：只从需求记录投影出五字段，**不含任何对话内容**（INV-9）。
 * requirement 缺失（窗口还没有绑定需求）→ 如实标注"无归属需求"，不静默留空。
 */
export function projectLedger(requirement: RequirementRecord | undefined, stage: PromptStage): LedgerProjection {
  const chain = STAGE_CHAIN[stage]
  if (requirement === undefined) {
    return {
      currentStage: stage,
      upstream: NO_REQUIREMENT,
      openQuestions: NO_REQUIREMENT,
      next: chain.label,
      evidence: NONE_EVIDENCE,
    }
  }
  const artifacts = requirement.artifacts ?? []
  const confirmed = artifacts.filter(a => a.confirmedAt !== undefined)
  const unconfirmed = artifacts.filter(a => a.confirmedAt === undefined)
  const blockers: string[] = []
  if (requirement.blocked) {
    blockers.push(fmt('需求被标记阻塞：{reason}', { reason: requirement.blockedReason ?? '（未写原因）' }))
  }
  for (const p of requirement.docSyncPending ?? []) {
    blockers.push(fmt('文档待同步：{source}', { source: p.source }))
  }
  return {
    currentStage: stage,
    upstream: confirmed.length > 0 ? confirmed.map(artifactLabel).join('；') : NONE_UPSTREAM,
    openQuestions: [...unconfirmed.map(artifactLabel), ...blockers].join('；') || NONE_OPEN,
    next: chain.label,
    evidence: artifacts.length > 0 ? artifacts.map(a => a.path).join('；') : NONE_EVIDENCE,
  }
}

export interface NodeInputPackageInput {
  stage: PromptStage
  difficulty?: Difficulty
  category?: Category
  budget?: number
  requirement?: RequirementRecord
  /** 需求文档投影（已读出的文本；空串 = 不可用，会如实标注）。 */
  requirementDoc: string
  /** 需求文档路径（渲染与标注用）。 */
  requirementDocPath: string
}

export interface NodeInputPackage {
  text: string
  resolved: ResolvedPrompt
  projection: LedgerProjection
}

const DOC_UNAVAILABLE = '（需求文档不可用或为空：{path}）'

/** 构造节点输入包（INV-9）：路由结果 + 需求文档投影 + 台账投影。 */
export function buildNodeInputPackage(input: NodeInputPackageInput): NodeInputPackage {
  const resolved = resolveStagePrompt({
    stage: input.stage,
    ...(input.difficulty === undefined ? {} : { difficulty: input.difficulty }),
    ...(input.category === undefined ? {} : { category: input.category }),
    ...(input.budget === undefined ? {} : { budget: input.budget }),
  })
  const projection = projectLedger(input.requirement, input.stage)
  const docText = input.requirementDoc.length > 0
    ? input.requirementDoc
    : fmt(DOC_UNAVAILABLE, { path: input.requirementDocPath })
  const text = fmt(
    [
      '# 节点输入包 · {reqId} · {stage}',
      '',
      '> 本包是节点边界后的唯一新起点：内容只来自「路由提示词 + 需求文档 + 台账投影」，',
      '> 不含前序对话摘录。若本窗口被遗弃，按本包即可续跑。',
      '',
      '## 当前节点',
      '{currentStage}（difficulty={difficulty}，category={category}）',
      '',
      '## 上游结论',
      '{upstream}',
      '',
      '## 未决问题',
      '{openQuestions}',
      '',
      '## 下一步',
      '{next}',
      '',
      '## 证据指针',
      '{evidence}',
      '',
      '## 路由提示词（routeKey={routeKey}，命中层级={hitLevel}）',
      '{routeText}',
      '',
      '## 需求文档（{docPath}）',
      '{docText}',
    ].join('\n'),
    {
      reqId: input.requirement?.id ?? '（无）',
      stage: input.stage,
      currentStage: projection.currentStage,
      difficulty: input.difficulty ?? '*',
      category: input.category ?? '*',
      upstream: projection.upstream,
      openQuestions: projection.openQuestions,
      next: projection.next,
      evidence: projection.evidence,
      routeKey: resolved.routeKey,
      hitLevel: String(resolved.hitLevel),
      routeText: resolved.text,
      docPath: input.requirementDocPath,
      docText,
    },
  )
  return { text, resolved, projection }
}

/** 需求文档相对路径（显式 docLinks.requirement 优先）。 */
export function requirementDocPath(requirement: RequirementRecord | undefined): string {
  if (requirement === undefined) return ''
  return requirement.docLinks?.requirement ?? fmt('docs/requirements/{id}/requirement.md', { id: requirement.id })
}

/** D-12 ②：给人可操作的等价路径（开新窗口 + 粘贴输入包）。 */
export function newWindowInstruction(packageText: string): string {
  return fmt(
    [
      '【节点隔离降级 · 请开新窗口】当前窗口触达不到会话 surface，无法执行整段替换。',
      '请在**新窗口**里粘贴下面的节点输入包作为第一条消息，即可等价续跑（输入包自足，无需携带本窗口历史）：',
      '',
      '----- 节点输入包开始 -----',
      '{pkg}',
      '----- 节点输入包结束 -----',
    ].join('\n'),
    { pkg: packageText },
  )
}
