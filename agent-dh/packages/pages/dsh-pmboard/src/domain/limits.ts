/**
 * 具名数值上限（REQ-47939a 返工：专门解决"魔法数字"）。
 *
 * 为什么要具名：`600000`/`30000`/`120`/`60_000` 这类字面量散在工具、用例、路由里时，
 * 读代码的人无法判断"这个数字是超时、是节流、还是上限"，改一处也不知道别处是否同源。
 * 具名之后：数值语义写在名字上，且**同一条上限只有一处定义**（INV-2 同理）。
 *
 * 边界：只收"有语义、会被多处引用或需要解释"的数值。纯粹的局部算术（如 1 个元素、
 * 下标偏移）不必进本文件。
 *
 * @module dsh-pmboard/domain/limits
 */

export const LIMITS = {
  /** 需求/任务标题最大长度（字符）。 */
  titleMax: 120,
  /** 一般文本字段最大长度（字符）。 */
  textMax: 4000,
  /** 产物路径最大长度（字符）。 */
  pathMax: 400,
  /** 验收证据条数下限/上限。 */
  evidenceMin: 1,
  evidenceMax: 20,
  /** 验收单每批弹框项数：缺省与上限（上限同时是弹框不超载的保护）。 */
  sheetBatchDefault: 5,
  sheetBatchMax: 10,
  /** done 凭证门的批量关闭节流窗口（毫秒）。 */
  doneThrottleMs: 60_000,
  /** 产物登记后未确认时的提醒延迟（毫秒）。 */
  confirmReminderMs: 30 * 60_000,
  /** 文字确认证据的有效时间窗（毫秒）。 */
  confirmEvidenceWindowMs: 60 * 60_000,
  /**
   * 弹框题干长度纪律（2026-09-17 用户实测：卡片限高、题干与选项共享滚动区——
   * 题干过长会把选项挤出可视区，用户表现为"不能选择"并取消）。
   */
  popupCriterionMax: 120,
  popupEvidenceMax: 40,
  popupQuestionMax: 220,
  /** 推进事件链（REQ-4842fe FR-11/FR-12）：单飞锁 stale、连续 noop 熔断、父卡并发上限、单次调用步数上限。 */
  advanceLockStaleMs: 15 * 60_000,
  advanceNoopBreaker: 5,
  advanceMaxParallelParents: 3,
  advanceMaxStepsPerCall: 20,
  /** 工具超时（毫秒）：读类 / 写入类 / 需人弹框类。 */
  timeoutReadMs: 15_000,
  timeoutWriteMs: 30_000,
  timeoutInteractiveMs: 600_000,
  timeoutSheetMs: 900_000,
} as const

/** 单文件行数上限（尺寸门禁用；与 tests/size-budget.test.ts 同源）。 */
export const MAX_FILE_LINES = 400
