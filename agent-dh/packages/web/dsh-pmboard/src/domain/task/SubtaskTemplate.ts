/**
 * 子卡模板映射表（REQ-4842fe t1）——子任务的**唯一契约起点**。
 *
 * 设计依据：design/data-model.md §2。三条口径：
 *  ① 映射表是**数据化配置**：新增卡类型 = 加一行（不改代码）；
 *  ② 未映射类型回退 dev → review（保守两卡，避免模板缺失时落空）；
 *  ③ 显式 stages 逃生舱口（FR-1b）：受控枚举、去重，用于映射表盖不住的新流程；
 *     **空数组 = 显式声明本卡不落链（solo）**（2026-09-28 卡片层契约）。
 *
 * 本文件是纯数据 + 纯函数：不 import node:/@deepseek-ai/，不碰时间与随机数（沿用 domain 层纪律）。
 */

/** 受控 stageKind 枚举（顺序即语义分组：研发族 / 复核 / 测试族 / 调研族 / 数据族 / 运维族）。 */
export const STAGE_KINDS = [
  'dev',
  'integrate',
  'review',
  'test',
  'repro',
  'fix',
  'regress',
  'probe',
  'collect',
  'analyze',
  'prepare',
  'run',
  'verify',
  'change',
  'dryrun',
  'apply',
] as const

import { fmt } from '../text/fmt.js'

export type StageKind = (typeof STAGE_KINDS)[number]

const STAGE_KIND_SET: ReadonlySet<string> = new Set<string>(STAGE_KINDS)

/** 未映射类型的保守回退：先研发、再复核放行。 */
export const DEFAULT_FALLBACK_STAGES: readonly StageKind[] = ['dev', 'review']

/**
 * 卡类型 → 子卡集合（顺序即串行链序）。
 *
 * 顺序口径（2026-09-20 用户裁定）：review 在前、测试在后 —— 先复核设计与实现
 * 是否对齐（早发现偏离、改完再测不浪费），测试作为链尾放行门。故除 review-only 外，
 * 每种类型都以 review 收尾。
 */
export const SUBTASK_TEMPLATES: Readonly<Record<string, readonly StageKind[]>> = {
  feature: ['dev', 'integrate', 'review', 'test'],
  refactor: ['dev', 'integrate', 'review', 'test'],
  bug: ['repro', 'fix', 'review', 'regress'],
  doc: ['dev', 'review'],
  chore: ['dev', 'review'],
  spike: ['probe', 'review'],
  research: ['collect', 'analyze', 'review'],
  analysis: ['collect', 'analyze', 'review'],
  data: ['prepare', 'run', 'verify', 'review'],
  ops: ['change', 'dryrun', 'apply', 'verify', 'review'],
  'review-only': ['review'],
}

/** 阶段中文名（看板徽标与子卡标题用；单点避免前后端各写一份）。 */
export const STAGE_LABELS: Readonly<Record<StageKind, string>> = {
  dev: '研发',
  integrate: '联调',
  review: '复核',
  test: '测试',
  repro: '复现',
  fix: '修复',
  regress: '回归测试',
  probe: '探针',
  collect: '取数调研',
  analyze: '分析',
  prepare: '准备',
  run: '执行',
  verify: '校验',
  change: '变更',
  dryrun: '试运行',
  apply: '实施',
}

/** 各阶段默认验收模板：必须可证伪（含命令/断言锚点），不得是「功能正常」式空话。 */
export const STAGE_ACCEPTANCE: Readonly<Record<StageKind, string>> = {
  dev: '改动已落盘，相关测试或命令跑通并附输出摘要',
  integrate: '接口联调通过：给出请求样例与期望响应，实际返回与预期一致',
  review: '对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据',
  test: '目标命令输出全绿（贴命令与结果摘要）',
  repro: '存在一条先失败、修复后转绿的回归用例（贴两次输出）',
  fix: '回归用例转绿（贴命令与输出），且根因单独写明（症状与根因区分）',
  regress: '相关测试全量跑通，无新增失败（贴汇总输出）',
  probe: '给出一个可证伪问题的答案与证据（明确未验证边界）',
  collect: '数据样本量与来源已标注（对齐 R-013 来源与时点口径）',
  analyze: '结论含置信度与适用边界，并列出被证伪的假设',
  prepare: '方案或脚本改动可复现：命令加输出摘要',
  run: '执行完成且结果落库：记录条数或输出路径可复核',
  verify: '校验项逐条给出结果，异常项已列出并标注影响面',
  change: '变更内容与回滚方式已写明，并给出可执行的验证命令与输出',
  dryrun: '试运行输出与预期一致（贴命令与输出）',
  apply: '变更已生效：给出可复核的验证命令与输出',
}

/**
 * 阶段证据形态（子卡完工凭证 L2，D17 结构性死路收口）——**与 STAGE_KINDS 同处的唯一事实源**。
 *
 * 为什么要分流：子卡完工凭证原先把「有 filesChanged 且文件新鲜」当**唯一**证据形态，而
 * review / test / verify 这类阶段天然不产 diff（它们产出的是**结论**：复核意见、测试输出）→
 * 100% 死在凭证门、链必停（D17 实测）。证据形态按阶段分两类：
 *   'file'    = 写入族：必须落盘——filesChanged 非空且至少一个文件真实存在、mtime ≥ 链出身；
 *   'verdict' = 结论族：天然无 diff——完工结论（completed）非空即放行。
 *
 * 新增 stageKind 必须在 STAGE_KINDS 与本表**同时**登记（Record<StageKind,…> 让漏登记成为类型错误）；
 * 未登记的阶段在凭证门按写入族从严处理（保守方向：拒绝 > 误放）。
 */
export const STAGE_EVIDENCE_KIND: Readonly<Record<StageKind, 'file' | 'verdict'>> = {
  // 写入族：必须留下落盘改动
  dev: 'file',
  repro: 'file',
  fix: 'file',
  prepare: 'file',
  run: 'file',
  change: 'file',
  apply: 'file',
  // 结论族：产出是判断/输出，天然无 diff
  integrate: 'verdict',
  review: 'verdict',
  test: 'verdict',
  regress: 'verdict',
  probe: 'verdict',
  collect: 'verdict',
  analyze: 'verdict',
  verify: 'verdict',
  dryrun: 'verdict',
}

/** 阶段中文名（未知 stageKind 回退为原值，避免渲染崩）。 */
export function stageLabel(kind: StageKind): string {
  return STAGE_LABELS[kind] ?? kind
}

/** 卡类型 → 子卡集合；未映射/空值回退 dev → review。 */
export function stagesForCardType(type: string | undefined | null): readonly StageKind[] {
  if (type === undefined || type === null) return DEFAULT_FALLBACK_STAGES
  const key = String(type).trim().toLowerCase()
  const hit = SUBTASK_TEMPLATES[key]
  return hit ?? DEFAULT_FALLBACK_STAGES
}

/**
 * 卡 phase → 默认子卡段（REQ-260928185112-e20d，2026-09-28）。
 *
 * 为什么需要：`stagesForCardType` 只认**需求分类**，于是同一需求下所有父卡落同一套子卡链。
 * 2026-09-28 实测（REQ-260928185112-e20d：7 父卡 × 4 段 = 28 段，分类 refactor）：
 * 计划自述「零调用方纯新增」的卡照样挂联调段、phase=test 的验证卡照样先挂 dev 段、
 * phase=doc 的文档卡也是 4 段；6 张联调卡共 19.2 min **零文件产出**（占该需求有效执行时间 34%）。
 *
 * 口径：只收「阶段语义与需求分类明显不同」的相位；未列出的（implement / ui / data…）继续按
 * 需求分类走映射表——**不做静默降级**，避免悄悄削掉本来就该有的联调/测试段。
 * 显式 `stages` 永远优先于本表（逃生舱口）；`skipIntegration` 仍可再裁掉联调段。
 * 段序沿用 2026-09-20 用户裁定：复核在前、测试在后。
 */
export const PHASE_STAGES: Readonly<Record<string, readonly StageKind[]>> = {
  /** 文档卡：无接口可联调，也没有独立的测试段（与 SUBTASK_TEMPLATES.doc 同口径）。 */
  doc: SUBTASK_TEMPLATES.doc,
  /** 复核卡：产出就是复核结论（与 review-only 同口径）。 */
  review: SUBTASK_TEMPLATES['review-only'],
  /** 合并卡：不新增接口（与 chore 同口径）。 */
  merge: SUBTASK_TEMPLATES.chore,
  /** 分析/取数卡：取数 → 分析 → 复核，没有研发与联调段。 */
  analysis: SUBTASK_TEMPLATES.analysis,
  /** 验证卡：要写验证脚本(dev)→复核(review)→跑(test)，但**没有新接口可联调**，故不落 integrate。 */
  test: ['dev', 'review', 'test'],
}

/** 按父卡 phase 取默认子卡段；未映射（含 undefined/未知相位）→ undefined，由调用方退回需求分类映射表。 */
export function stagesForPhase(phase: string | undefined | null): readonly StageKind[] | undefined {
  if (phase === undefined || phase === null) return undefined
  return PHASE_STAGES[String(phase).trim().toLowerCase()]
}

/**
 * 按父卡 side 取默认子卡段（REQ-260928185112-e20d 统一方案）——只有 `doc` 侧有明确答案：
 * 纯文档卡既无接口可联调、也没有独立测试段（与 SUBTASK_TEMPLATES.doc 同口径）。
 *
 * 其余端侧（frontend/backend/fullstack）**一律返回 undefined**，回到需求分类口径——
 * "这张卡有没有接口面"是**计划侧才能声明的事实**（skipIntegration / stages），代码不猜：
 * 从端侧推断"是否要与别的模块对接"必然猜错，猜错就是静默削段。
 */
export function stagesForSide(side: string | undefined | null): readonly StageKind[] | undefined {
  if (side === undefined || side === null) return undefined
  return String(side).trim().toLowerCase() === 'doc' ? SUBTASK_TEMPLATES.doc : undefined
}

export type ExplicitStagesVerdict =
  | { ok: true; value: StageKind[] }
  | { ok: false; error: string }

/**
 * 校验显式 stages 逃生舱口（FR-1b）：① 必须是数组（**空数组 = 显式无链，合法**，2026-09-28）；
 * ② 元素取自受控枚举；③ 不得重复。返回结构化原因，调用方拼错误码 REQBOARD_STAGES_INVALID。
 */
export function validateExplicitStages(stages: readonly unknown[]): ExplicitStagesVerdict {
  if (!Array.isArray(stages)) return { ok: false, error: 'stages 必须是数组' }
  // 空数组 = **显式声明「本卡不落子卡链」（solo）**（2026-09-28 卡片层契约）：
  // `undefined` = 未指定（走 phase → side → 需求分类映射）；`[]` = 明确无链——两者必须可区分，
  // 否则"没子卡"永远分不清「不需子卡」与「需要但未生成」。
  if (stages.length === 0) return { ok: true, value: [] }
  const out: StageKind[] = []
  const seen = new Set<string>()
  for (const raw of stages) {
    const kind = String(raw ?? '').trim()
    if (!STAGE_KIND_SET.has(kind)) {
      return {
        ok: false,
        error: fmt('非法 stageKind：{kind}（受控枚举：{allowed}）', { kind, allowed: STAGE_KINDS.join(', ') }),
      }
    }
    if (seen.has(kind)) return { ok: false, error: fmt('stageKind 重复：{kind}', { kind }) }
    seen.add(kind)
    out.push(kind as StageKind)
  }
  return { ok: true, value: out }
}

/** 子卡规格（落库前的中间形态；id 由调用方在写台账时生成）。 */
export interface SubtaskSpec {
  /** 链上下标（0 起），用于生成 dependsOn */
  chainIndex: number
  stageKind: StageKind
  /** 子卡标题，如「研发」 */
  title: string
  /** 可证伪验收模板 */
  acceptance: string
  /** 依赖链上前一张的下标；null = 依赖父卡的外部依赖（由调用方继承） */
  dependsOnIndex: number | null
}

/**
 * 由有序 stageKind 生成子卡规格：链内依赖 = 前一张；首卡 dependsOnIndex=null（由调用方接父卡依赖）。
 * 空集合返回空数组（不落任何子卡）。
 */
export function buildSubtaskSpecs(stages: readonly StageKind[]): SubtaskSpec[] {
  return stages.map((stageKind, i) => ({
    chainIndex: i,
    stageKind,
    title: stageLabel(stageKind),
    acceptance: STAGE_ACCEPTANCE[stageKind],
    dependsOnIndex: i === 0 ? null : i - 1,
  }))
}
