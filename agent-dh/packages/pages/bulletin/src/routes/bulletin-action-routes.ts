// 公告板「我来解决 / 转交」路由：**适配层**（2026-09-14, w-61022a21, REQ-1bb221）。
//
// 历史问题：本文件原自写一套 fetch，直接读写 Agent OS 的 **memory** 端点
// （GET /api/v1/memory/{id}、PATCH /api/v1/memory/{id}，RFC 009 之前的公告板语义）。
// 2026-09-08 RFC 014 把公告板迁到独立存储（board_posts 表 + /api/v1/board/posts REST）后，
// 帖子 id 在 memory 里一律不存在 → 该路径稳定 500（实测 2026-09-14：{"success":false,
// "error":"memory not found: 026cd6a3-…"}）；同页的列表视图早已改用统一 board API，所以页面看着正常。
//
// 现在本文件只做装配，不再实现任何业务逻辑：
//   · 状态读写 → **统一公告板 API**（@pi-investment/agent-os-client 的 BoardClient，
//     与 board_post/board_read/board_update 工具同源；状态机/权限/乐观锁由服务端强制）；
//   · 认领 + 投递 → **公共能力库** @pi-investment/solve-kit 的 createBoardSolveHandler
//     （与执行看板/持仓看板同一套「我来解决」语义与响应信封）。
// 请求/响应契约不变：{post_id, action:'solve'|'delegate', to_session?, from_session?}
//   → 200 {success:true,data:{delivery:{delivered},note,…}}（客户端只读这两个字段）。

import { BoardClient } from '@pi-investment/agent-os-client'
import { createBoardSolveHandler, type BoardPort } from '@pi-investment/solve-kit'

export interface ActionTarget {
  /** 目标 agent（root 会话），含 followup 投递能力 */
  agent: unknown
  sessionId: string
  /** 展示用窗口标签（session-<uuid> → w-<前8>） */
  window: string
}

export interface BulletinActionDeps {
  /** Agent OS 基址（统一公告板 API 的服务端），如 http://localhost:8080 */
  agentOsBaseURL: string
  /** 请求超时（毫秒） */
  requestTimeoutMs: number
  /** 本实例身份 id（board actor / assignee 写入值，与 board 工具同源） */
  agentId: string
  /** 解析目标会话 → 在线 agent（宿主 index.ts 注入；to_session 传 true=精确命中） */
  resolveAgent: (sessionId?: string, exactOnly?: boolean) => ActionTarget | null
  /** 覆盖公告板客户端（测试 / 联调注入假实现）；缺省按 agentOsBaseURL 构造 BoardClient */
  board?: BoardPort
  /** 面板文案覆盖（默认公告板） */
  panel?: string
  panelFull?: string
  plugin?: string
}

/**
 * 装配公告板「我来解决」处理器：唯一 board 客户端 + 公共 solve 处理器。
 * 逻辑实现全部在 @pi-investment/solve-kit（见其 src/board-solve.ts），本函数不做分支。
 */
export function createBulletinActionHandler(deps: BulletinActionDeps) {
  // BoardClient 结构上满足 solve-kit 的 BoardPort（getPost / updatePost 同签名），无需转换层
  const board: BoardPort = deps.board
    ?? (new BoardClient({
      baseURL: deps.agentOsBaseURL,
      timeout: deps.requestTimeoutMs,
      agentId: deps.agentId,
    }) as unknown as BoardPort)

  return createBoardSolveHandler({
    board,
    actor: deps.agentId,
    resolveAgent: deps.resolveAgent,
    panel: deps.panel ?? '公告板',
    panelFull: deps.panelFull ?? '投资顾问公告板看板',
    plugin: deps.plugin ?? 'dashboard-bulletin',
  })
}
