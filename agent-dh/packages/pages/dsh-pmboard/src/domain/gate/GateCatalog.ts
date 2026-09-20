/**
 * 人工闸门目录（REQ-e3b6a0 t2 / FR-10）——**五道门的唯一事实源**。
 *
 * 收敛来源（四处 → 一处）：
 *  - AskConfirm.ts 私有 `ADVANCE_MAP`          → GateSpec.autoAdvance + advanceTargetFor()
 *  - ArtifactSpec.ts `ARTIFACT_CONFIRM_GATES`  → GateSpec.requiredKind + 本文件再导出
 *  - RequirementStatus `HUMAN_ONLY_...`        → GateSpec.humanOnly（本文件不 import 它，改由测试锁一致，避免值环）
 *  - support.ts 问题卡文案表                   → GateSpec.questionCard + questionCardFor()
 *
 * 为什么 HUMAN_ONLY 不直接引用：RequirementStatus 的断言函数要用它，若本文件 import 它的值、
 * 它又 import 本文件，就成值环。改为"各存一份 + 测试锁死相等"（test-cases.md 的同款纪律）。
 *
 * @module dsh-pmboard/domain/gate/GateCatalog
 */
import type { ArtifactKind } from '../artifact/ArtifactSpec.js'
import { fmt } from '../text/fmt.js'
import { type GateId, type GateSpec, transitionKeyOf } from './GateSpec.js'

/** 五道人工闸门（顺序 = 流水线顺序）。 */
export const GATE_CATALOG: readonly GateSpec[] = [
  {
    id: 'G0', label: '立项门',
    to: 'brainstorming',
    channels: ['session'],
    verdictShape: 'form',
    humanOnly: false,
    autoAdvance: false, // G0 的"推进"由 create 自带的 draft→brainstorming 完成
    questionCard: '立项三问（需求名称 / 类型 / 难度）已完成，是否创建立项？',
  },
  {
    id: 'G1', label: '确认需求文档',
    from: 'brainstorming', to: 'design',
    requiredKind: 'requirement',
    channels: ['session', 'board'],
    verdictShape: 'affirmative',
    humanOnly: true,
    autoAdvance: true,
    questionCard: '需求文档已完成，是否确认进入设计？',
  },
  {
    // 2026-09-21 用户裁定（w-2105d331 代录）：设计阶段只写设计文档，拆分计划归拆分阶段。
    // G2 从「批准拆分计划（kind=plan）」改为「确认设计文档（kind=design）」。
    id: 'G2', label: '确认设计文档',
    from: 'design', to: 'decomposing',
    requiredKind: 'design',
    channels: ['session', 'board'],
    verdictShape: 'affirmative',
    // design>decomposing **不在** HUMAN_ONLY：agent 可自行推进，但产物门（design 已确认）拦着
    humanOnly: false,
    autoAdvance: true,
    questionCard: '设计文档已完成，是否确认进入拆分？',
  },
  {
    // 2026-09-21 用户裁定：拆分计划（decomposition.md + 任务表）在拆分阶段提交并批准，
    // 批准 = decompose 落卡的唯一钥匙（批准即自动拆分+开跑，见 AskConfirm 门合并）。
    id: 'G3', label: '批准拆分计划',
    from: 'decomposing', to: 'implementing',
    requiredKind: 'decomposition',
    channels: ['session', 'board'],
    verdictShape: 'affirmative',
    humanOnly: true,
    autoAdvance: true,
    questionCard: '拆分计划已提交，是否批准落库任务卡并进入实施？',
  },
  {
    id: 'G4', label: '验收通过即归档',
    from: 'accepting', to: 'archived',
    requiredKind: 'verification',
    channels: ['session', 'board'],
    // G4 有两段交互：逐项裁决（per-item）+ 最终归档拍板（affirmative）；此处记主导语义
    verdictShape: 'per-item',
    humanOnly: true,
    autoAdvance: false, // 验收通过/归档由验收单流程代办，不在会话弹框的自动推进白名单里
    questionCard: '验收材料已提交，是否验收通过并归档？',
  },
]

/** 按 id 取闸门。 */
export function gateById(id: GateId): GateSpec | undefined {
  return GATE_CATALOG.find(g => g.id === id)
}

/** 按转移键取闸门（G0 无 from → 不参与）。 */
export function gateForTransition(from: string, to: string): GateSpec | undefined {
  return GATE_CATALOG.find(g => g.from === from && g.to === to)
}

/** 按作答前所处阶段取闸门（一个阶段至多是一道门的 from 端）。 */
export function gateFromStage(from: string): GateSpec | undefined {
  return GATE_CATALOG.find(g => g.from === from)
}

/** 转移键 → 闸门 id（拒绝信息用）。 */
export function gateIdForTransition(from: string, to: string): GateId | undefined {
  return gateForTransition(from, to)?.id
}

/**
 * 会话弹框肯定答复后允许自动推进到的目标状态（旧 AskConfirm.ADVANCE_MAP 的替代）。
 * 无对应闸门 / 该闸门不在自动推进白名单 → undefined（调用方按"无可自动推进的下一阶段"处理）。
 */
export function advanceTargetFor(from: string): string | undefined {
  const gate = GATE_CATALOG.find(g => g.from === from && g.autoAdvance)
  return gate?.to
}

/** 该转移是否"代码级仅人可发起"。 */
export function isHumanOnlyTransition(from: string, to: string): boolean {
  return gateForTransition(from, to)?.humanOnly === true
}

/**
 * 产物确认门表（**向后兼容再导出源**）：`from>to` → 须已确认的 ArtifactKind。
 * 由 GATE_CATALOG 派生，故闸门表的字面量定义在本文件**只有一处**（GATE_CATALOG）。
 */
export const ARTIFACT_CONFIRM_GATES: Readonly<Record<string, ArtifactKind>> = Object.freeze(
  Object.fromEntries(
    GATE_CATALOG
      .filter(g => g.from !== undefined && g.requiredKind !== undefined)
      .map(g => [transitionKeyOf(g) as string, g.requiredKind as ArtifactKind]),
  ) as Record<string, ArtifactKind>,
)

/**
 * 闸门问题卡（旧 support.gateQuestionCard 的文案来源）：move 被人工闸门拒绝时，返回可直接
 * 喂给 reqboard_ask_confirm 的调用参数——闸门从"只挡不引"升级为"挡并指路"。
 * 输出文案与收敛前**逐字等价**（tests/gate-catalog.test.ts 用旧实现逐条对拍）。
 */
export function questionCardFor(gateKind: string | undefined, from: string, to: string): string {
  const gate = gateForTransition(from, to)
  const question = gate?.questionCard ?? fmt('是否确认推进到 {to}？', { to })
  // 2026-09-21：「批准拆分计划」门已从 design>decomposing 挪到 decomposing>implementing
  const call = gateKind === 'plan' || (from === 'decomposing' && to === 'implementing')
    ? fmt("{ target: 'plan', question: '{question}' }", { question })
    : fmt("{ target: 'artifact', kind: '{kind}', question: '{question}' }", { kind: gateKind ?? 'requirement', question })
  return fmt('\n【问题卡】直接调 reqboard_ask_confirm 完成确认（用户点肯定项 → 自动落章并推进 {from} → {to}）：\n  reqboard_ask_confirm({call})', { from, to, call })
}
