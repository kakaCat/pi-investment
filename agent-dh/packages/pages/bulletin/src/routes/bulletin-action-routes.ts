// 路由：POST /dashboard/api/bulletin/action —— 公告板 GUI 认领/转交动作（Task #2）。
// 语义与 board_update 工具对齐（lifecycle/board-tools.ts）：
//   - 认领/转交 = 对 Agent OS memory PATCH metadata（board_status=claimed + moderation_log 追加），
//     assignee 恒为身份 id（本实例 cfg.agentId='investor'，board_update 完成权限即靠它放行）；
//   - 动作后把"自包含任务消息"经 ctx.agents 投递给目标会话（followup 注入，agent 自主闭环：
//     处理完调 board_update(complete/blocked) 关闭帖子）。投递目标来自 client 左侧会话列表
//     （sessions 服务），不建后端窗口清单端点（USER #3 校正）。
// 终态（done/dropped/archived）拒绝；claimed 状态的转交 = 人工覆盖（moderation action transfer）。
// 信封：200 {success:true,data} / 200 {success:false,error}（用户可预期错误）/ 500 兜底。

import type { IncomingMessage, ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'

export interface ActionTarget {
  /** 目标 agent（root 会话），含 followup 投递能力 */
  agent: unknown
  sessionId: string
  /** 展示用窗口标签（session-<uuid> → w-<前8>，余者原样） */
  window: string
}

export interface BulletinActionDeps {
  agentOsBaseURL: string
  requestTimeoutMs: number
  /** 本实例身份 id（board 工具 cfg.agentId），assignee 写入值 */
  agentId: string
  /** 解析目标会话 → 在线 agent；resolve(null) 回退主 root。查无 → null */
  resolveAgent: (sessionId?: string) => ActionTarget | null
}

const ACTIVE_STATUSES = new Set(['open', 'claimed', 'paused', 'blocked'])

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  })
  res.end(text)
}

function readBody(req: IncomingMessage): Promise<any> {
  return new Promise((resolve, reject) => {
    let raw = ''
    req.on('data', (c) => { raw += c; if (raw.length > 64 * 1024) { reject(new Error('body too large')); req.destroy() } })
    req.on('end', () => {
      if (!raw.trim()) return resolve({})
      try { resolve(JSON.parse(raw)) } catch (e) { reject(new Error('请求体不是合法 JSON')) }
    })
    req.on('error', reject)
  })
}

async function fetchMem(baseURL: string, timeoutMs: number, path: string, init?: RequestInit): Promise<any> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(baseURL + path, { ...(init ?? {}), signal: controller.signal })
    const text = await res.text()
    let parsed: any = null
    try { parsed = text ? JSON.parse(text) : null } catch { /* non-json */ }
    if (!res.ok) {
      const msg = parsed?.message ?? parsed?.error ?? ('HTTP ' + res.status)
      throw new Error(msg)
    }
    return parsed ?? {}
  } finally {
    clearTimeout(timer)
  }
}

function buildTaskMessage(deps: { postId: string; title: string; content: string; kind: string | null; created_at: string | null; actorLabel: string; postStatusBefore: string }): any {
  const lines = [
    '【公告板任务】有一张公告板帖子已认领给你，请处理并闭环：',
    '',
    '标题：' + deps.title,
    '类型：' + (deps.kind || '未分类') + '（原状态：' + deps.postStatusBefore + '）',
    '上报时间：' + (deps.created_at || '—'),
    '',
    '正文：',
    deps.content,
    '',
    '来源：公告板 GUI 认领（' + deps.actorLabel + '）。',
    '要求：请以认领人身份解决该帖子代表的问题（调查/分析/回答均可，自定）。',
    '闭环方式：用 board_update 工具处理 —— 完成后 action=complete、note=处理结论；',
    '无法完成则 action=blocked、note=卡因。',
    '重要结论建议写入 memory（namespace=decision）。',
    '帖子 ID：' + deps.postId,
  ]
  return {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text: lines.join('
') }],
    source: { kind: 'plugin', plugin: 'dashboard-bulletin' },
  }
}

async function deliverMessage(target: ActionTarget | null, message: unknown): Promise<{ delivered: boolean; error?: string; target?: { sessionId: string; window: string } }> {
  if (!target) return { delivered: false, error: '目标窗口不在线（未解析到 agent），认领已写入，请稍后在目标窗口重试' }
  const agent = target.agent as any
  if (typeof agent?.followup !== 'function') {
    return { delivered: false, error: '目标 agent 无 followup 投递能力，认领已写入', target: { sessionId: target.sessionId, window: target.window } }
  }
  try {
    await agent.followup(message)
    return { delivered: true, target: { sessionId: target.sessionId, window: target.window } }
  } catch (e) {
    return { delivered: false, error: '投递失败：' + (e instanceof Error ? e.message : String(e)), target: { sessionId: target.sessionId, window: target.window } }
  }
}

export function createBulletinActionHandler(deps: BulletinActionDeps) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const body = await readBody(req)
      const { post_id, action, to_session, from_session } = body as any

      if (!post_id || typeof post_id !== 'string') {
        return json(res, 200, { success: false, error: '缺少 post_id' })
      }
      if (action !== 'solve' && action !== 'delegate') {
        return json(res, 200, { success: false, error: 'action 仅支持 solve（我来解决）/ delegate（转交）' })
      }
      if (action === 'delegate' && (!to_session || typeof to_session !== 'string')) {
        return json(res, 200, { success: false, error: '转交缺少目标会话 to_session' })
      }

      const { agentOsBaseURL, requestTimeoutMs, agentId, resolveAgent } = deps

      // 1) 读帖（含 closed）
      const got = await fetchMem(agentOsBaseURL, requestTimeoutMs, '/api/v1/memory/' + encodeURIComponent(post_id) + '?include_closed=true')
      const mem = got?.memory ?? got
      const md = mem?.metadata ?? {}
      if (!mem?.id) {
        return json(res, 200, { success: false, error: '帖子不存在：' + post_id })
      }

      const status = typeof md.board_status === 'string' && md.board_status !== '' ? md.board_status : 'open'
      if (!ACTIVE_STATUSES.has(status)) {
        return json(res, 200, { success: false, error: '帖子已终态（' + status + '），无法认领/转交' })
      }

      // 2) 目标会话：solve → 当前窗口（客户端 from_session）或主 root；delegate → to_session
      const target = action === 'delegate'
        ? resolveAgent(to_session, true)
        : resolveAgent(from_session || undefined, false)
      if (!target) {
        return json(res, 200, { success: false, error: '未解析到任何在线目标窗口，动作未执行' })
      }

      // 3) 认领语义（镜像 board-tools 元数据模型）
      const now = new Date().toISOString()
      const curRev = Number(md.revision) || 0
      const isSelfNudge = action === 'solve' && status === 'claimed' && md.assignee === agentId
      const prevLog: any[] = Array.isArray(md.moderation_log) ? md.moderation_log : []
      const claimCount = isSelfNudge ? (Number(md.claim_count) || 0) : (Number(md.claim_count) || 0) + 1

      const actorLabel = from_session
        ? (from_session.startsWith('session-') ? 'w-' + String(from_session).slice(8, 16) : from_session)
        : target.window
      const logAction = action === 'delegate' && status === 'claimed' ? 'transfer'
        : action === 'delegate' ? 'claim'
        : isSelfNudge ? 'nudge' : 'claim'
      const logNote = action === 'delegate'
        ? 'GUI 转交 → ' + target.window + '（' + target.sessionId + '）'
        : isSelfNudge
          ? 'GUI 再次认领（催办），投递 ' + target.window
          : 'GUI 我来解决，投递 ' + target.window + '（' + target.sessionId + '）'

      const metadataPatch: Record<string, any> = {
        board_status: 'claimed',
        assignee: agentId,
        claim_count: claimCount,
        claimed_at: now,
        revision: curRev + 1,
        moderation_log: [
          ...prevLog,
          { timestamp: now, action: logAction, actor: actorLabel, note: logNote },
        ],
      }

      const patchBody: Record<string, any> = { metadata_patch: metadataPatch }
      if (curRev > 0) patchBody.expected_revision = curRev

      await fetchMem(agentOsBaseURL, requestTimeoutMs, '/api/v1/memory/' + encodeURIComponent(post_id), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patchBody),
      })

      // 4) 认领成功 → followup 注入自包含任务消息，agent 自主闭环
      const message = buildTaskMessage({
        postId: post_id,
        title: String(mem.title ?? ''),
        content: String(mem.content ?? ''),
        kind: typeof md.kind === 'string' ? md.kind : null,
        created_at: mem.created_at ?? null,
        actorLabel,
        postStatusBefore: status,
      })
      const delivery = await deliverMessage(target, message)

      return json(res, 200, {
        success: true,
        data: {
          post_id,
          status: 'claimed',
          assignee: agentId,
          revision: curRev + 1,
          claim_count: claimCount,
          action: logAction,
          target: { sessionId: target.sessionId, window: target.window },
          delivery,
          note: delivery.delivered
            ? '已认领并投递 ' + target.window + '，目标窗口将自主处理并闭环'
            : '已认领；' + (delivery.error || '投递未完成，请稍后重试'),
        },
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      json(res, 500, { success: false, error: msg })
    }
  }
}
