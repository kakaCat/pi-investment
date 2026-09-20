/**
 * 人工闸门领域 · 单个闸门的形状（REQ-e3b6a0 t2 / FR-10）。
 *
 * 为什么单独成域：此前"门"的知识散在四处——AskConfirm 的私有 ADVANCE_MAP（能推进到哪）、
 * ArtifactSpec 的 ARTIFACT_CONFIRM_GATES（要哪个产物）、RequirementStatus 的
 * HUMAN_ONLY_REQ_TRANSITIONS（谁能发起）、support 的问题卡文案表（被拒时指路）。
 * 四份真相必然漂移，故收敛为本域的两份数据（GateSpec + GateCatalog）。
 *
 * 分层：domain 最内层，**零 I/O、零框架**（tests/layer-boundary.test.ts 机械门禁：
 * 不许 import node: / @deepseek-ai/* / @pi-investment/* / ../application|adapters|tools|http|client|host|shared）。
 *
 * @module dsh-pmboard/domain/gate/GateSpec
 */
import type { ArtifactKind } from '../artifact/ArtifactSpec.js'
import type { RequirementStatus } from '../requirement/RequirementStatus.js'

/** 五道人工闸门的稳定标识（G0 立项门 + 四道产物确认门）。 */
export type GateId = 'G0' | 'G1' | 'G2' | 'G3' | 'G4'

/** 确认通道：session = 会话弹框（pm 专有）/ board = 看板一键。 */
export type GateChannel = 'session' | 'board'

/**
 * 答案语义族——决定"答案怎么解读"，而不是"怎么显示"：
 *  - affirmative：单问，首个选项 = 肯定项（其余为修改/补充/澄清/暂停）
 *  - per-item：多问，每问独立通过/不通过 + 意见（验收单逐项裁决）
 *  - form：多问取值（立项三问：名称/类型/难度），非判定
 */
export type VerdictShape = 'affirmative' | 'per-item' | 'form'

/** 单个闸门。`from` 缺省 = 尚未绑定需求（G0 立项门）。 */
export interface GateSpec {
  readonly id: GateId
  readonly label: string
  readonly from?: RequirementStatus
  readonly to: RequirementStatus
  /** 须已确认的产物 kind；缺省 = 无产物可落章（G0 创建即立项）。 */
  readonly requiredKind?: ArtifactKind
  readonly channels: readonly GateChannel[]
  readonly verdictShape: VerdictShape
  /** 该转移是否"代码级仅人可发起"（HUMAN_ONLY_REQ_TRANSITIONS 成员）。 */
  readonly humanOnly: boolean
  /** 会话弹框肯定答复后是否允许自动推进到 to（旧 AskConfirm.ADVANCE_MAP 的白名单）。 */
  readonly autoAdvance: boolean
  /** 被拒时的问题卡文案（"挡并指路"用）。 */
  readonly questionCard: string
}

/** 该闸门的转移键（`from>to`）；G0 无 from → 返回 undefined。 */
export function transitionKeyOf(gate: GateSpec): string | undefined {
  return gate.from === undefined ? undefined : gate.from + '>' + gate.to
}

/** 用户在弹框里的一条作答（与 application 的 AskAnswer 结构兼容，domain 不反向依赖上层）。 */
export interface GateAnswer {
  readonly id?: string
  readonly selected?: readonly string[]
  readonly custom?: string
}

/**
 * 一次闸门作答的完整上下文——**后置链（GatePostChain）的输入契约**。
 *
 * 时序纪律：Phase A 只登记"哪个门被作答"；`from`/`to`/`verdict` 在 Phase B 执行时
 * 以台账**实时状态**为准（作答时推进可能尚未落库），故此处它们允许在 Phase B 被刷新。
 */
export interface ConfirmContext {
  /** 作答窗口（agent id）。 */
  readonly windowKey: string
  readonly gate: GateId
  /** 作答前状态；G0 时缺省（尚未绑定需求）。 */
  readonly from?: RequirementStatus
  /** 目标状态。 */
  readonly to: RequirementStatus
  /** 归属需求；G0 由 H1 产出后回填（故可变）。 */
  requirementId?: string
  /**
   * 肯定项 / 非肯定项（决定是否推进与是否压缩）。
   *
   * **Phase A 可留空**：装饰器只登记「哪道门被作答」，无权断言结果（作答与推进落库之间还隔着
   * 用例的落章与迁移）——Phase B 由 H1（h1-advance）以台账实时状态回填。
   */
  verdict?: 'affirmative' | 'negative'
  readonly answers: readonly GateAnswer[]
  /** 作答时刻（幂等键的一半，由调用方注入的 Clock 落章）。 */
  readonly decidedAt: number
}

/** 幂等键：同一次作答只允许跑一轮链。 */
export function pendingKeyOf(ctx: Pick<ConfirmContext, 'windowKey' | 'gate' | 'decidedAt'>): string {
  return ctx.windowKey + '|' + ctx.gate + '|' + String(ctx.decidedAt)
}
