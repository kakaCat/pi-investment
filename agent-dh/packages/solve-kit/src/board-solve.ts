// @pi-investment/solve-kit · host 半：公告板档「我来解决」——认领 + 投递任务消息（公共能力）。
// 2026-09-14（w-61022a21，REQ-1bb221）：公告板 GUI 的认领/转交原先自写一套 fetch，指向 Agent OS
// **memory** 端点（RFC 009 前语义）；2026-09-08 RFC 014 把公告板迁到独立存储（board_posts 表 +
// /api/v1/board/posts）后该路径对帖子 id 一律 404 → 按钮稳定 500。现统一到本文件：
//   1) 状态读写走**统一公告板 API**（BoardPort；生产实现 = @pi-investment/agent-os-client 的
//      BoardClient，与 board_post/board_read/board_update 工具同源，状态机/权限/乐观锁由服务端强制）；
//   2) 投递复用 ./target.js 的 deliverMessage（与执行看板/持仓看板同一套「我来解决」语义）；
//   3) 信封与执行档一致：200 {success:true,data} / 200 {success:false,error}（用户可预期错误）/ 500 兜底。
//
// 语义与限制（诚实标注）：
//   - solve（我来解决）= 认领 → 投递目标窗口（默认当前窗口，可回退主 root）；
//   - delegate（转交）= 指定窗口精确投递 + 同一路径认领；服务端无 transfer 动作，实际执行窗口
//     只能记入 PATCH note（assignee 恒为本实例身份），板面不展示改派；
//   - 已由他人认领（claimed 且 assignee≠actor）：服务端状态机不允许改派 → 返回用户可预期错误；
//   - 已是本人认领：跳过 PATCH（claim 在 claimed 状态非法），仅重新投递（催办）；
//   - 终态（done/dropped/archived）：拒绝，不投递。

import type { IncomingMessage, ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'
import { json, readBody } from './http.js'
import { windowCode, deliverMessage, type SolveKitHostDeps } from './target.js'

/** 公告板帖子快照（统一 board API 返回体的结构化子集，字段口径同 BoardPost） */
export interface BoardPostSnapshot {
  id: string
  title?: string
  content?: string
  display_title?: string
  kind?: string
  status?: string
  author?: string | null
  assignee?: string | null
  revision?: number
  claim_count?: number
  claimed_at?: string | null
  created_at?: string
}

/** 统一公告板 API 的最小契约。生产实现 = @pi-investment/agent-os-client 的 BoardClient（推荐）。
 *  此处只声明结构化子集，solve-kit 保持零依赖，且不与 BoardClient 的具体实现耦合。 */
export interface BoardPort {
  getPost: (id: string) => Promise<BoardPostSnapshot>
  updatePost: (id: string, params: {
    action: string
    note?: string
    expected_revision?: number
    actor: string
  }) => Promise<{ new_status?: string; revision?: number; message?: string; post?: BoardPostSnapshot }>
}

export interface BoardSolveDeps extends SolveKitHostDeps {
  /** 统一公告板 API 客户端（必须走 /api/v1/board/posts，禁止再退回 memory 端点） */
  board: BoardPort
  /** 本实例身份 id（board actor / assignee 写入值，= board 工具 cfg.agentId） */
  actor: string
  /** 面板短名（消息标题前缀），如 '公告板' */
  panel: string
  /** 面板全名（消息来源行），如 '投资顾问公告板看板' */
  panelFull: string
  /** source.plugin 值（消息留痕归属），如 'dashboard-bulletin' */
  plugin: string
}

/** 服务端状态机终态（不再允许任何流转） */
const TERMINAL = new Set(['done', 'dropped', 'archived'])
/** 允许 claim 的状态（服务端 BoardStateMachine：open→claim, paused→claim, blocked→claim） */
const CLAIMABLE = new Set(['open', 'paused', 'blocked'])

/** 从 axios / fetch 错误里提取服务端可读信息（409/403/400 的理由在 body.error/message） */
function serverMessage(error: unknown): string {
  const e = error as any
  const data = e?.response?.data
  if (data && typeof data === 'object') return String(data.error || data.message || JSON.stringify(data))
  if (typeof e?.response?.data === 'string') return e.response.data
  return e instanceof Error ? e.message : String(error)
}

function clip(s: unknown, max: number): string {
  const t = String(s ?? '').replace(/\r\n/g, '\n').trim()
  return t.length > max ? t.slice(0, max) + '…（已截断）' : t
}

/** 组装自包含的处置消息（接收窗口无需回看原帖即可开工，闭环方式写在消息里） */
export function buildBoardSolveMessage(p: {
  post: BoardPostSnapshot
  actorWindow: string
  targetWindow: string
  action: 'solve' | 'delegate'
  panel: string
  panelFull: string
  plugin: string
}): any {
  const title = clip(p.post.title ?? p.post.display_title ?? '(无标题)', 120)
  const who = p.post.author ? String(p.post.author) : '—'
  const lines = [
    '【' + p.panel + '】帖子已由「我来解决」'
      + (p.action === 'delegate' ? '转交给你' : '派给你') + '，请在本会话处置并闭环：',
    '',
    '帖子 ID：' + p.post.id,
    '标题：' + title,
    '类型：' + String(p.post.kind ?? '—') + '；原状态：' + String(p.post.status ?? '—') + '；作者：' + who,
    '',
    '正文：',
    clip(p.post.content ?? '（无正文）', 2000),
    '',
    '来源：' + p.panelFull + '「我来解决」投递（' + p.actorWindow + ' → ' + p.targetWindow + '）。',
    '要求：以任务属主视角调查根因并**实际处置**（查日志 / 改代码 / 重启服务等，自定方案），不是只给结论。',
    '闭环：处置完成后调用 board_update(post_id="' + p.post.id + '", action="complete"|"blocked", note="…") 关闭帖子，并在本会话回复结论。',
    '（本投递不写 memory，是否沉淀经验/审计由你决定；若判定不该由你处理，用 board_update(action="pause", note="…") 退回并说明。）',
  ]
  // 信封与执行档 buildSolveMessage 一致（agent.followup 消费的形状）
  return {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text: lines.join('\n') }],
    source: { kind: 'plugin', plugin: p.plugin },
  }
}

/** 「我来解决」公告板档路由工厂。deps.board 由宿主页面注入（唯一 board 访问入口）。 */
export function createBoardSolveHandler(deps: BoardSolveDeps) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      let body: any
      try {
        body = await readBody(req)
      } catch (e) {
        return json(res, 200, { success: false, error: e instanceof Error ? e.message : String(e) })
      }

      const postId = String(body?.post_id ?? '').trim()
      if (!postId) return json(res, 200, { success: false, error: '缺少 post_id（公告板帖子 ID）' })
      const rawAction = body?.action == null || body.action === '' ? 'solve' : String(body.action)
      if (rawAction !== 'solve' && rawAction !== 'delegate') {
        return json(res, 200, { success: false, error: 'action 仅支持 solve（我来解决）/ delegate（转交），收到：' + rawAction })
      }
      const action: 'solve' | 'delegate' = rawAction
      const fromSession = typeof body?.from_session === 'string' && body.from_session ? body.from_session : undefined
      const toSession = typeof body?.to_session === 'string' && body.to_session ? body.to_session : undefined

      // 1) 读帖（统一 board API）——查不到属用户可预期错误，不是 500
      let post: BoardPostSnapshot
      try {
        post = await deps.board.getPost(postId)
      } catch (e) {
        const raw = serverMessage(e)
        const msg = /404|not found|不存在/i.test(raw) ? '帖子不存在或已删除（' + postId + '）' : '读取公告板失败：' + raw
        return json(res, 200, { success: false, error: msg })
      }
      if (!post || typeof post !== 'object') {
        return json(res, 200, { success: false, error: '帖子不存在或不可读：' + postId })
      }

      const status = String(post.status ?? '')
      const assignee = post.assignee ? String(post.assignee) : null
      if (TERMINAL.has(status)) {
        return json(res, 200, { success: false, error: '该帖已终结（status=' + status + '），无需处理' })
      }

      // 2) 目标窗口：显式 to_session 精确命中（转交禁止回退）；否则 from_session（默认当前窗口）可回退主 root
      const target = toSession
        ? deps.resolveAgent(toSession, true)
        : deps.resolveAgent(fromSession, false)
      if (!target) {
        const hint = toSession
          ? '目标窗口 ' + windowCode(toSession) + ' 不在线（会话 agent 未加载）'
          : '当前窗口与主窗口均不在线'
        return json(res, 200, { success: false, error: hint + '，未执行认领/投递。请选择在线窗口后重试' })
      }
      const actorWindow = fromSession ? windowCode(fromSession) : target.window

      // 3) 认领（走统一 board API；状态机/权限/乐观锁由服务端强制）
      let newStatus = status
      let revision = typeof post.revision === 'number' ? post.revision : undefined
      let claimedNow = false
      let claimNote = ''

      if (status === 'claimed' && assignee && assignee !== deps.actor) {
        return json(res, 200, {
          success: false,
          error: '该帖已由 ' + assignee + ' 认领；服务端状态机不允许改派，'
            + '请等其完成（complete）或暂停（pause）后再处理，或让其在 note 中标注实际执行窗口',
        })
      }

      if (CLAIMABLE.has(status)) {
        const note = (action === 'delegate' ? '看板转交' : '看板认领')
          + '（' + actorWindow + ' → ' + target.window + '）'
        try {
          const r = await deps.board.updatePost(postId, { action: 'claim', note, expected_revision: revision, actor: deps.actor })
          newStatus = String(r?.new_status ?? 'claimed')
          revision = typeof r?.revision === 'number' ? r.revision : revision
          claimedNow = true
          claimNote = '已认领'
        } catch (e) {
          const msg = serverMessage(e)
          const friendly = /revision conflict/i.test(msg)
            ? '帖子已被他人更新（乐观锁冲突），请刷新看板后重试'
            : msg
          return json(res, 200, { success: false, error: '认领失败：' + friendly })
        }
      } else if (status === 'claimed') {
        // 已是本人认领：claim 在 claimed 状态非法 → 跳过写操作，仅重新投递（催办/改派给新窗口）
        claimNote = '已在本人名下，跳过认领'
      } else {
        return json(res, 200, { success: false, error: '当前状态 ' + status + ' 不允许认领' })
      }

      // 4) 投递自包含处置消息（唯一投递原语，与执行/持仓看板同一套）
      const message = buildBoardSolveMessage({
        post, actorWindow, targetWindow: target.window, action,
        panel: deps.panel, panelFull: deps.panelFull, plugin: deps.plugin,
      })
      const delivery = await deliverMessage(target, message)
      const actionLabel = action === 'delegate' ? '转交' : '认领'

      return json(res, 200, {
        success: true,
        data: {
          post_id: postId,
          action,
          status: newStatus,
          claimed: claimedNow,
          assignee: deps.actor,
          revision,
          target: { sessionId: target.sessionId, window: target.window },
          delivery,
          note: delivery.delivered
            ? '已' + actionLabel + '并投递 ' + target.window + '（' + claimNote + '），目标窗口将自主处理并闭环'
            : '已' + actionLabel + '（' + claimNote + '）；' + (delivery.error || '投递未完成，请稍后重试'),
        },
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      json(res, 500, { success: false, error: msg })
    }
  }
}
