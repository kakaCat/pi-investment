/**
 * 领域基础值对象：操作者（REQ-47939a t2）。
 *
 * 为什么先搬它：两级状态机的转移判定必须知道"谁在发起"——ActorKind 是
 * RequirementStatus / TaskStatus 两个规约的共同入参，ActorRef 是台账与事件时间线的
 * 审计载体。把它放在 domain 最底层，状态机规约才能不依赖 shared（domain 不许 import
 * shared，见 tests/layer-boundary.test.ts）。
 *
 * 纯类型文件，零 import（domain 硬约束）。
 */

/** 操作者：human=人在看板操作；agent=agent 会话；system=编排器 rollup 自动推进。 */
export type ActorKind = 'human' | 'agent' | 'system'

export interface ActorRef {
  kind: ActorKind
  /** agent 操作时的会话 id（审计用） */
  sessionId?: string
}
