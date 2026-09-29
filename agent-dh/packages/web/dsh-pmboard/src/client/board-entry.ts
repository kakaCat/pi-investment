/**
 * 节点面板「项目看板 ↗」入口的校验与失败提示（REQ-260928222643-4d34 · FR-3 · 设计 I-2 / I-6）。
 *
 * 纪律（机械保证「先校验、后切页」）：\`activateBoardEntry\` 只做校验与登记，**不切页**；
 * 顺序 = ① layout 可用性（无网络成本）→ ② reqId 形状（不拿空 id 打接口）→ ③ 台账可达性
 * （唯一需要 IO 的一步）→ ④ 登记一次性定位意图。任一前置失败 → {ok:false} 且**零副作用**。
 *
 * 纯函数 + 依赖注入：无 React / 无 DOM / 不直接 fetch（便于单测；文案与 board-mount
 * 既有的 jumpResultMessage 同款约定，但本需求要求**可见**，故由调用方就地渲染 message）。
 *
 * @module dsh-pmboard/client/board-entry
 */

/** 入口失败的三种原因（互斥）。 */
export type BoardEntryFailure = 'nav-unavailable' | 'req-missing' | 'ledger-unreachable'

/** 失败原因 → 人话（纯函数）。 */
export function boardEntryFailureMessage(reason: BoardEntryFailure, reqId: string, detail?: string): string {
  switch (reason) {
    case 'nav-unavailable':
      return '页面导航服务不可用（layout 未注入），请刷新页面后重试'
    case 'req-missing':
      return `需求 ${reqId.length > 0 ? reqId : '(空)'} 不在台账（可能已归档或被删除），未跳转`
    case 'ledger-unreachable':
      return `无法确认需求是否可达（台账接口失败：${detail !== undefined && detail.length > 0 ? detail : '未知原因'}），未跳转`
  }
}

export interface BoardEntryDeps {
  /** 该 REQ 是否在台账（注入 api.fetchState 的投影，便于单测）。 */
  isKnown(reqId: string): Promise<boolean>
  /** 登记一次性定位意图（注入 board-focus 的 requestBoardFocus）。 */
  requestFocus(reqId: string): void
  /** 页面导航服务；undefined = 未注入（由调用方从 getPageLayout() 取）。 */
  layout: { selectPanel(id: string | null): void } | undefined
}

export type BoardEntryVerdict =
  | { ok: true }
  | { ok: false; reason: BoardEntryFailure; message: string }

/** REQ id 的最小形状（REQ- 前缀）；不在此形状内的空串/乱码一律判 req-missing 且不打接口。 */
const REQ_ID_SHAPE = /^REQ-/

/**
 * 校验 + 登记（**不切页**：切页由调用方在 ok=true 后执行）。
 */
export async function activateBoardEntry(reqId: string, deps: BoardEntryDeps): Promise<BoardEntryVerdict> {
  // ① layout 可用性（最先排除「注定跳不动」的情况，无网络成本）
  if (deps.layout === undefined) {
    return { ok: false, reason: 'nav-unavailable', message: boardEntryFailureMessage('nav-unavailable', reqId) }
  }
  // ② reqId 形状（联网前拦下空 id / 非 REQ- 形状）
  const id = typeof reqId === 'string' ? reqId.trim() : ''
  if (!REQ_ID_SHAPE.test(id)) {
    return { ok: false, reason: 'req-missing', message: boardEntryFailureMessage('req-missing', id) }
  }
  // ③ 台账可达性（唯一 IO 步）
  let known: boolean
  try {
    known = await deps.isKnown(id)
  } catch (e) {
    const detail = e instanceof Error ? e.message : String(e)
    return { ok: false, reason: 'ledger-unreachable', message: boardEntryFailureMessage('ledger-unreachable', id, detail) }
  }
  if (known !== true) {
    return { ok: false, reason: 'req-missing', message: boardEntryFailureMessage('req-missing', id) }
  }
  // ④ 登记意图（仅在「确定能到达」时写）
  deps.requestFocus(id)
  return { ok: true }
}
