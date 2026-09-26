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
import { renderAddressSection } from '../../domain/template/index.js'
import type { RequirementRecord, StageArtifact } from '../../shared/protocol.js'
import type { NodeInput } from '../../../../../tools/reqboard/src/dive/node-input.js'

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
  /**
   * 断点（T-1 / FR-6）：当前阶段 + 未完成动作 + 中断原因 + 时间；无断点 = 空串。
   * 输入包据此**条件追加**「## 断点」节——老需求（无字段）输出逐字节不变。
   */
  breakpoint: string
}

const NONE_UPSTREAM = '（无已确认产物）'
const NONE_OPEN = '（无）'
const NONE_EVIDENCE = '（无）'
const NO_REQUIREMENT = '（无归属需求，台账投影不可用）'

function artifactLabel(a: StageArtifact): string {
  return fmt('{kind}（{path}）', { kind: a.kind, path: a.path })
}

/**
 * 台账投影：从需求记录投影出五字段 + 断点（FR-6），**不含任何对话内容**（INV-9）。
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
      breakpoint: '',
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
    breakpoint: breakpointText(requirement),
  }
}

/**
 * 断点节文本（T-1 / FR-6）：含阶段 / 未完成动作 / 中断原因 / 时间四要素。无断点 → 空串
 * （调用方据此不追加该节，保证存量需求输出与改造前逐字节一致）。
 */
function breakpointText(requirement: RequirementRecord | undefined): string {
  const bp = requirement?.interruption
  if (bp === undefined) return ''
  return fmt(
    [
      '## 断点',
      '- 当前阶段：{stage}',
      '- 未完成动作：{action}',
      '- 中断原因：{reason}',
      '- 记录时间：{at}',
    ].join('\n'),
    { stage: bp.stage, action: bp.pendingAction, reason: bp.reason, at: new Date(bp.at).toISOString() },
  )
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
  /** 模板根绝对路径（T-5）；缺省 = 输入包不追加地址小节（与改造前逐字节一致）。 */
  templateRoot?: string
  /** 当前任务卡投影（实施节点的上游必读）。 */
  currentTask?: { id?: string; title?: string; cardDoc?: string }
  /** FR-8：RTM 追溯快照（由用例读盘后注入；缺省 = 不追加该节，逐字节保持旧输出）。 */
  rtm?: NodeInput
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
  // FR-6：仅当需求带断点时追加该节；无断点 → 空数组（逐字节保持旧输出）。
  const breakpointSection = projection.breakpoint.length > 0 ? [...projection.breakpoint.split('\n'), ''] : []
  const docText = input.requirementDoc.length > 0
    ? input.requirementDoc
    : fmt(DOC_UNAVAILABLE, { path: input.requirementDocPath })
  // 进入本阶段的第一个动作（domain 单点 STAGE_CHAIN.entry）——与 H4 唤醒消息同源：
  // H2 真压缩过时唤醒消息只说"纪律在输入包里"，这里就必须真的带上"第一步干什么"。
  const entryLine = STAGE_CHAIN[input.stage].entry.length > 0
    ? fmt('进入本阶段的第一步：{e}', { e: STAGE_CHAIN[input.stage].entry })
    : ''
  const baseText = fmt(
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
      ...breakpointSection,
      '## 下一步',
      '{next}',
      ...(entryLine.length > 0 ? [entryLine] : []),
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
  // FR-8：注入 RTM 追溯快照（未注入/无 next_action → 不追加，旧输出逐字节不变）。
  const rtmSection = renderRtmSection(input.rtm)
  const withRtm = rtmSection.length > 0 ? baseText + '\n' + rtmSection : baseText
  // T-5（FR-8/FR-12）：地址小节与系统段/H3 共用同一纯函数；空集不追加（逐字节兼容）。
  const addressSection = renderAddressFor(input)
  const text = addressSection.length > 0 ? withRtm + '\n\n' + addressSection : withRtm
  return { text, resolved, projection }
}

/**
 * FR-8：RTM 追溯快照小节。
 * 只渲染"决策要看的东西"（下一步建议 + 覆盖度/状态/产出摘要），不塞整份 RTM——
 * 输入包体积是 token 成本，完整数据按需读文件。
 */
function renderRtmSection(rtm: NodeInput | undefined): string {
  if (rtm === undefined || rtm.next_action === undefined || rtm.next_action.length === 0) return ''
  const snapshot: Record<string, unknown> = {}
  if (rtm.coverage !== undefined) snapshot.coverage = rtm.coverage
  if (rtm.status !== undefined) snapshot.status = rtm.status
  if (rtm.outputs !== undefined) snapshot.outputs = rtm.outputs
  const lines = [
    '## RTM 追溯快照（FR-8 · ' + rtm.stage + ' · ' + rtm.mode + '）',
    '',
    '- 下一步建议：' + rtm.next_action,
  ]
  if (Object.keys(snapshot).length > 0) lines.push('', '```json', JSON.stringify(snapshot), '```')
  lines.push('')
  return lines.join('\n')
}

/** 输入包侧的地址节渲染（渲染异常 → 不追加，不静默破坏输入包）。 */
function renderAddressFor(input: NodeInputPackageInput): string {
  if (input.templateRoot === undefined) return ''
  try {
    return renderAddressSection({
      stage: input.stage,
      category: input.category,
      ...(input.requirement === undefined ? {} : { requirement: input.requirement }),
      ...(input.currentTask === undefined ? {} : { currentTask: input.currentTask }),
      templateRoot: input.templateRoot,
    })
  } catch {
    return ''
  }
}

/**
 * 需求文档相对路径（REQ-260922012924-2e29 FR-2）。
 *
 * 解析优先级：`docLinks.requirement`（显式链接，最高）→ `docBasePath` 拼接 → 缺省
 * `docs/requirements/<REQ>/`。docBasePath 拼接契约（design/interfaces.md）：
 *  ① `<REQ>` 占位符全部替换为需求 id；
 *  ② docBasePath **无** `<REQ>` 时追加 `<id>/` 子目录（防多需求撞同一 requirement.md）；
 *  ③ 尾部斜杠归一；④文件名恒 `requirement.md`。
 * 兼容：无 docBasePath 的老记录走缺省分支，输出与改造前逐字节一致。
 */
export function requirementDocPath(requirement: RequirementRecord | undefined): string {
  if (requirement === undefined) return ''
  if (requirement.docLinks?.requirement !== undefined) return requirement.docLinks.requirement
  const raw = requirement.docBasePath ?? 'docs/requirements/<REQ>/'
  const hasPlaceholder = raw.includes('<REQ>')
  const base = raw.replaceAll('<REQ>', requirement.id)
  const withId = hasPlaceholder ? base : base.replace(/\/?$/, '/') + requirement.id + '/'
  return withId.replace(/\/?$/, '/') + 'requirement.md'
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
