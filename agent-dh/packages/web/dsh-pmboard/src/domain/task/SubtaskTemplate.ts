/**
 * 子卡模板映射表（REQ-4842fe t1）——子任务的**唯一契约起点**。
 *
 * 设计依据：design/data-model.md §2。三条口径：
 *  ① 映射表是**数据化配置**：新增卡类型 = 加一行（不改代码）；
 *  ② 未映射类型回退 dev → review（保守两卡，避免模板缺失时落空）；
 *  ③ 显式 stages 逃生舱口（FR-1b）：受控枚举、非空、去重，用于映射表盖不住的新流程。
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

export type ExplicitStagesVerdict =
  | { ok: true; value: StageKind[] }
  | { ok: false; error: string }

/**
 * 校验显式 stages 逃生舱口（FR-1b）：① 必须是数组且非空；② 元素取自受控枚举；③ 不得重复。
 * 返回结构化原因，调用方拼错误码 REQBOARD_STAGES_INVALID。
 */
export function validateExplicitStages(stages: readonly unknown[]): ExplicitStagesVerdict {
  if (!Array.isArray(stages)) return { ok: false, error: 'stages 必须是数组' }
  if (stages.length === 0) return { ok: false, error: 'stages 不得为空数组' }
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
