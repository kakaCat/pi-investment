// 路由：POST /dashboard/api/board/solve —— 执行看板「我来解决」（只投递，不建帖）。
// 语义（2026-09-06 用户确认范围）：失败调度任务行 / 错误事件条的「我来解决」→
//   把"自包含排查消息"经 ctx.agents.followup 投递给目标窗口会话，由该窗口自主排查处置并在
//   会话内给出结论。与 bulletin 的 solve 差异：bulletin 认领会 PATCH Agent OS memory（建帖闭环），
//   本路由**只投递不建帖**——不写 memory、不 PATCH metadata、不建公告板帖子，
//   投递即完成，结论留在目标窗口会话（重要结论由接收方自主决定是否沉淀 memory）。
// 路由所有权：execution 独占 /dashboard/api/board*；bulletin 独占 /dashboard/api/bulletin/*。
// 信封：200 {success:true,data:{kind,title,target,delivered,note}} /
//       200 {success:false,error}（用户可预期错误）/ 500 兜底。

import type { IncomingMessage, ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'

export interface ActionTarget {
  /** 目标 agent（root 会话），含 followup 投递能力 */
  agent: unknown
  sessionId: string
  /** 展示用窗口标签（session-<uuid> → w-<前8>，余者原样） */
  window: string
}

export interface ExecutionSolveDeps {
  /** 解析目标会话 → 在线 agent；无 to_session 时回退 from_session（默认当前窗口），
   *  再回退主 root；查无 → null。to_session 传 true=精确命中（投递指定窗口禁止回退） */
  resolveAgent: (sessionId?: string, exactOnly?: boolean) => ActionTarget | null
}

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
      try { resolve(JSON.parse(raw)) } catch { reject(new Error('请求体不是合法 JSON')) }
    })
    req.on('error', reject)
  })
}

/** 快照时间 → 展示文本（GMT+8） */
function fmt(ts: unknown): string {
  if (!ts) return '—'
  const d = new Date(String(ts))
  if (isNaN(d.getTime())) return String(ts)
  const p = (n: number): string => String(n).padStart(2, '0')
  return (d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes())
}

/** 最近运行状态中文 */
function lastRunText(r: unknown): string {
  if (typeof r === 'string') return r
  const o = (r ?? {}) as Record<string, unknown>
  const st = String(o.status ?? '')
  const at = fmt(o.triggeredAt ?? o.finishedAt ?? null)
  if (!st && at === '—') return '—'
  const zh = st === 'success' ? '成功' : st === 'failed' ? '失败' : st === 'skipped' ? '已跳过' : (st || '未知')
  return at + '（' + zh + '）' + (o.err ? '；' + String(o.err).slice(0, 200) : '')
}

interface BuildCtx {
  kind: 'task' | 'error'
  title: string
  lines: string[]
  actorWindow: string
}

function buildSolveMessage(b: BuildCtx): any {
  const lines = [
    b.kind === 'task' ? '【执行看板 · 失败任务排查】以下调度任务失败，请排查处置并在本会话回复结论：'
      : '【执行看板 · 错误事件排查】以下错误事件需要定位处置，请排查并在本会话回复结论：'
    '',
    ...b.lines,
    '',
    '来源：双线执行确认看板「我来解决」投递（' + b.actorWindow + '）。',
    '要求：以任务/事件属主视角调查根因并处置——可查 Agent OS 日志、重启相关服务、修正任务或代码等，自定方案。',
    '闭环方式：处置完成或给出结论后在本会话回复即可（本投递不建帖、不写 memory，由你决定是否沉淀经验/审计）。',
  ]
  return {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text: lines.join(NL) }],
    source: { kind: 'plugin', plugin: 'dashboard-execution' },
  }
}

async function deliverMessage(target: ActionTarget | null, message: unknown): Promise<{ delivered: boolean; error?: string; target?: { sessionId: string; window: string } }> {
  if (!target) return { delivered: false, error: '目标窗口不在线（未解析到 agent）' }
  const agent = target.agent as any
  if (typeof agent?.followup !== 'function') {
    return { delivered: false, error: '目标 agent 无 followup 投递能力', target: { sessionId: target.sessionId, window: target.window } }
  }
  try {
    await agent.followup(message)
    return { delivered: true, target: { sessionId: target.sessionId, window: target.window } }
  } catch (e) {
    return { delivered: false, error: '投递失败：' + (e instanceof Error ? e.message : String(e)), target: { sessionId: target.sessionId, window: target.window } }
  }
}

/** 会话 id → 窗口标签（与 lifecycle/bulletin 同口径：session- 前缀取中段 8 位） */
function windowCode(id: string): string {
  return id.startsWith('session-') ? 'w-' + id.slice(8, 16) : id
}

export function createExecutionSolveHandler(deps: ExecutionSolveDeps) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const body: any = await readBody(req)
      const { kind, task, err, from_session, to_session } = body as any

      if (kind !== 'task' && kind !== 'error') {
        return json(res, 200, { success: false, error: 'kind 仅支持 task（失败任务）/ error（错误事件）' })
      }
      if (kind === 'task' && (!task || typeof task !== 'object')) {
        return json(res, 200, { success: false, error: 'kind=task 缺少任务快照 task' })
      }
      if (kind === 'error' && (!err || typeof err !== 'object')) {
        return json(res, 200, { success: false, error: 'kind=error 缺少错误快照 err' })
      }

      // 目标会话：显式 to_session（精确）→ 否则 from_session（默认当前窗口，可回退主 root）
      const target = to_session && typeof to_session === 'string'
        ? deps.resolveAgent(to_session, true)
        : deps.resolveAgent(from_session && typeof from_session === 'string' ? from_session : undefined, false)
      if (!target) {
        return json(res, 200, { success: false, error: '未解析到任何在线目标窗口，投递未执行' })
      }

      const actorWindow = from_session && typeof from_session === 'string' ? windowCode(from_session) : target.window
      const fetchedAt = fmt((task as any)?.fetchedAt ?? (err as any)?.fetchedAt ?? null)

      let title: string
      let lines: string[]
      if (kind === 'task') {
        const t = task as Record<string, any>
        const name = String(t.name ?? t.title ?? '?')
        const src = String(t.src ?? '')
        const agentCall = t.agentCall ? (typeof t.agentCall === 'string' ? String(t.agentCall) : JSON.stringify(t.agentCall)) : ''
        title = '失败任务：' + name
        const fail = String(t.error ?? '') || (t.lastRun && typeof t.lastRun === 'object' ? String((t.lastRun as any).err ?? '') : '')
        lines = [
          '任务：' + name + (src ? '（来源：' + src + '）' : '')
          '计划：' + (t.scheduleExpr ? String(t.scheduleExpr) : '—') + (t.nextRunAt ? '；下次运行：' + fmt(t.nextRunAt) : '')
          '上次运行：' + lastRunText(t.lastRun) + '；今日：' + (Number(t.todayTriggered) || 0) + ' 触发 / ' + (Number(t.todaySuccess) || 0) + ' 成功',
          '数据时点：' + fetchedAt + '（看板快照）'
          '失败原因：' + (fail ? fail.slice(0, 600) : '—（看板未见失败原因，请查 Agent OS 日志）')
        ]
        if (agentCall) lines.push('Agent 调用：' + agentCall.slice(0, 300))
      } else {
        const e = err as Record<string, any>
        const src = String(e.source ?? '?')
        const first = String(e.line ?? e.file ?? '').replace(/\n/g, ' ').slice(0, 300)
        title = '错误事件：' + src + (first ? ' ' + first.slice(0, 40) : '')
        lines = [
          '来源：' + src
          '时间：' + fmt(e.timestamp) + '（数据时点：' + fetchedAt + '，看板快照）'
          '详情：' + (first || '—')
        ]
      }

      const message = buildSolveMessage({ kind, title, lines, actorWindow })
      const delivery = await deliverMessage(target, message)

      return json(res, 200, {
        success: true,
        data: {
          kind,
          title,
          target: { sessionId: target.sessionId, window: target.window },
          delivered: delivery.delivered,
          note: delivery.delivered
            ? '已投递窗口 ' + target.window + '，处理结论将回复在该窗口会话'
            : (delivery.error || '投递未完成，请稍后重试')
        },
      })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      json(res, 500, { success: false, error: msg })
    }
  }
}