/**
 * 领域错误码（REQ-47939a t1）——唯一事实源，对应 design/domain-model.md §7。
 *
 * 为什么集中在 domain：错误码是"拒绝理由"的契约。散在各文件里就没法机械检查，
 * 也无法保证"同一语义在不同入口返回同一个码"（INV-2 同一规则只有一处实现，错误码同理）。
 *
 * 本文件是**纯数据 + 纯函数**：不 import 任何模块、不碰时间与随机数（domain 层的硬约束，
 * 由 tests/layer-boundary.test.ts 机械检查）。
 *
 * 构造约定（沿用全仓现有写法，见 docs/standards/tool-development.md）：
 *   Object.assign(new Error(message), { code })
 * 且 message 里自带 code 文本——跨包时 instanceof 不可靠，工具层读的是 message。
 *
 * 命名口径：本表只放**领域语义**码（小写）。工具层的传输层包装码（如 REQBOARD_BAD_STATUS）
 * 属于 tools/ 的职责，在 t8 落位，不在 domain 定义。
 */

/** 领域语义错误码（domain-model.md §7 逐条对应）。 */
export const REQBOARD_ERROR_CODES = {
  /** 入参非法（HTTP 400 / 工具拒绝） */
  invalidInput: 'invalid_input',
  /** 状态机拒绝非法转移（HTTP 409） */
  invalidTransition: 'invalid_transition',
  /** 人工闸门：该转移只能由人发起（HTTP 409，返回体带 gate_question 供弹框） */
  humanGate: 'human_gate',
  /** 需求不属本窗口（HTTP 403） */
  notBoundToWindow: 'not_bound_to_window',
  /** 窗口没有进行中的绑定需求（HTTP 404） */
  noBoundReq: 'no_bound_req',
  /** 产物未登记就要确认/推进（HTTP 409） */
  missingArtifact: 'missing_artifact',
  /** 计划未获批准就要拆分（HTTP 409） */
  planNotApproved: 'plan_not_approved',
  /** 重复拆分（INV-3，HTTP 409） */
  alreadyDecomposed: 'already_decomposed',
  /** done 凭证门拒绝（INV-4，HTTP 409，附缺失项清单） */
  doneEvidenceMissing: 'done_evidence_missing',
  /** 短窗口内连环关闭任务（HTTP 409） */
  bulkClose: 'bulk_close',
  /** 页面插件构建陈旧（HTTP 409） */
  staleBuild: 'stale_build',
  /** 验收单版本不符（HTTP 409） */
  versionMismatch: 'version_mismatch',
  /** 台账写入后状态异常（HTTP 500） */
  storeInconsistent: 'store_inconsistent',
  /** 迁移校验不通过（脚本退出码 1 + 回滚） */
  migrationFailed: 'migration_failed',
} as const

/** 领域错误码字面量联合。 */
export type ReqboardErrorCode = (typeof REQBOARD_ERROR_CODES)[keyof typeof REQBOARD_ERROR_CODES]

/** 构造带 code 的领域错误（唯一构造入口，避免各处手写 Object.assign）。 */
export function domainError(code: ReqboardErrorCode, message: string): Error {
  return Object.assign(new Error(message), { code })
}

/** 判定任意抛出物是否为携带某 code 的领域错误。 */
export function hasErrorCode(err: unknown, code: ReqboardErrorCode): boolean {
  return typeof err === 'object' && err !== null && (err as { code?: unknown }).code === code
}
