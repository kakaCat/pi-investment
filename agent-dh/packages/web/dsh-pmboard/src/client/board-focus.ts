/**
 * 看板「一次性定位」交接持有器（REQ-260928222643-4d34 · FR-2 · 设计 I-1 / T-2 / T-3）。
 *
 * 为什么需要它：看板视图状态 \`mode\` 是 board-mount 挂载闭包内的**局部变量**，而宿主是
 * keyed 插槽（切走即卸载）。因此「面板点击时（此时看板尚未挂载）把 REQ id 交给看板」只能
 * 经模块级持有器：面板 \`requestBoardFocus(reqId)\` 登记，看板挂载时 \`takeBoardFocus()\` 消费。
 * 与既有 \`page/page-runtime.ts\` 同款依赖纪律（模块级持有器，不新增全局量）。
 *
 * 一次性语义：读后立即清空；不落浏览器存储、不进 URL、不挂 window 属性。
 * 故刷新页面或再次进入看板必然回到默认视图——不得形成粘滞状态（需求「数据契约」）。
 *
 * 依赖纪律：本模块**零 import**。
 *
 * @module dsh-pmboard/client/board-focus
 */

/** 至多一条「待被看板消费的定位意图」；undefined = 无意图。 */
let pendingReqId: string | undefined

/** 登记一次「请把看板定位到该需求」的意图。空串/纯空白 → 视为清除（不登记）。 */
export function requestBoardFocus(reqId: string): void {
  const id = typeof reqId === 'string' ? reqId.trim() : ''
  pendingReqId = id.length > 0 ? id : undefined
}

/** 取走意图并立即清空（消费即清）。无意图 → undefined。 */
export function takeBoardFocus(): string | undefined {
  const id = pendingReqId
  pendingReqId = undefined
  return id
}

/** 清空意图（失败路径与测试收尾；幂等）。 */
export function clearBoardFocus(): void {
  pendingReqId = undefined
}

/** 只读探测（**不消费**）——仅供单测与诊断；生产路径不得用它判断后仍假设未被消费。 */
export function peekBoardFocus(): string | undefined {
  return pendingReqId
}
