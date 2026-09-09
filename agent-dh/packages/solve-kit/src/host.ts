// @pi-investment/solve-kit · host 半：「我来解决」投递路由工厂（只投递，不建帖）。
// 从 dashboard-execution routes/execution-solve-route.ts 抽象（2026-09-08, w-752decf5）：
// 面板文案（panel/panelFull/plugin）参数化，供 execution（执行看板）/holdings（持仓看板）共用。
// 语义：kind ∈ task/error 的失败快照 → 组装自包含排查消息 → ctx.agents.followup 投递目标窗口会话，
// 由该窗口自主排查并在会话内给结论。不写 memory、不建公告板帖子，结论沉淀由接收方自主决定。
// 信封：200 {success:true,data:{kind,title,target,delivered,note}} / 200 {success:false,error} / 500 兜底。

import type { IncomingMessage, ServerResponse } from 'node:http'
import { randomUUID } from 'node:crypto'

export interface ActionTarget {
  /** 目标 agent（root 会话），含 followup 投递能力 */
  agent: unknown
  sessionId: string
  /** 展示用窗口标签（session-<uuid> → w-<前8>，余者原样） */
  window: string
}

export interface SolveKitHostDeps {
  /** 解析目标会话 → 在线 agent；无 to_session 时回退 from_session（默认当前窗口），
   *  再回退主 root；查无 → null。to_session 传 true=精确命中（投递指定窗口禁止回退） */
  resolveAgent: (sessionId?: string, exactOnly?: boolean) => ActionTarget | null
}

export interface SolveKitHostOptions {
  /** 面板短名（消息标题前缀），如 '执行看板' / '持仓看板' */
  panel: string
  /** 面板全名（消息来源行），如 '双线执行确认看板' / '账户持仓看板' */
  panelFull: string
  /** source.plugin 值（消息留痕归属），如 'dashboard-execution' / 'dashboard-holdings' */
  plugin: string
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

const NL = '\n'

function buildSolveMessage(b: { kind: 'task' | 'error'; title: string; lines: string[]; actorWindow: string; opts: SolveKitHostOptions }): any {
  const lines = [
    b.kind === 'task'
      ? '【' + b.opts.panel + ' · 失败任务排查】以下调度任务失败，请排查处置并在本会话回复结论：'
      : '【' + b.opts.panel + ' · 错误事件处置】以下错误事件需要你实际解决（定位根因并落地处置，不是只给结论）：',
    '',
    ...b.lines,
    '',
    '来源：' + b.opts.panelFull + '「我来解决」投递（' + b.actorWindow + '）。',
  ]
  if (b.kind === 'task') {
    lines.push(
      '要求：以任务属主视角调查根因并处置——可查 Agent OS 日志、重启相关服务、修正任务或代码等，自定方案。',
      '闭环方式：处置完成或给出结论后在本会话回复即可（本投递不建帖、不写 memory，由你决定是否沉淀经验/审计）。'
    )
  } else {
    lines.push(
      '处置目标：让该错误消除或确认无害——必须落地动作，不是只写一段排查结论。流程：',
      '调查路径：',
      '  1) 该错误由 Agent OS 采集（错误事件表 error_events，事件 ID 见上），先查对应端真实日志上下文（见上 logger/log 字段位置）；',
      '  2) 溯源责任代码：quantsys-v2 → pi-investment/quantsys-v2，agent-os → pi-investment/agent-os，agent-dh → pi-investment/agent-dh；按错误串/logger 定位源码行；',
      '  3) 判定根因类型：代码 bug / 环境问题 / 外部依赖 / 误报（自愈）；必要时本机复现（python -c / curl）实证，禁止臆造语言或 API 特性；',
      '落地动作（三选一，必须做一件）：',
      '  a) 能修则修——修代码/配置或重启服务，验证错误消除（日志干净/复现不再触发），给验证证据；',
      '  b) 外部依赖/环境所致——给证据（前后日志/复现输出）与建议动作，交人工决定；',
      '  c) 确属误报/一次性——给证据（未再现的日志区间或判定依据）。',
      '回写闭环：处置完成后立即把该事件落终态（勿等用户再点按钮）：',
      "  已解决 → 调用: curl -s -X POST http://127.0.0.1:13080/dashboard/api/board/error-action -H 'Content-Type: application/json' -d '{\"id\":\"<上文事件ID>\",\"action\":\"resolve\",\"note\":\"根因+动作+证据（处置窗口署名）\"}'",
      '  已修/已解决 → action=resolve；误报/无需处理 → action=ignore。接口不可达时，在本会话回复完整结论并说明，事件留给人工闭环。'
    )
  }
  return {
    id: randomUUID(),
    role: 'user',
    content: [{ type: 'text', text: lines.join(NL) }],
    source: { kind: 'plugin', plugin: b.opts.plugin },
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
export function windowCode(id: string): string {
  return id.startsWith('session-') ? 'w-' + id.slice(8, 16) : id
}

/** 「我来解决」投递路由工厂：deps.resolveAgent 由宿主页面提供（agents 服务注入解析）。 */
export function createSolveHandler(deps: SolveKitHostDeps, opts: SolveKitHostOptions) {
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
          '任务：' + name + (src ? '（来源：' + src + '）' : ''),
          '计划：' + (t.scheduleExpr ? String(t.scheduleExpr) : '—') + (t.nextRunAt ? '；下次运行：' + fmt(t.nextRunAt) : ''),
          '上次运行：' + lastRunText(t.lastRun) + '；今日：' + (Number(t.todayTriggered) || 0) + ' 触发 / ' + (Number(t.todaySuccess) || 0) + ' 成功',
          '数据时点：' + fetchedAt + '（看板快照）',
          '失败原因：' + (fail ? fail.slice(0, 600) : '—（看板未见失败原因，请查 Agent OS 日志）')
        ]
        if (agentCall) lines.push('Agent 调用：' + agentCall.slice(0, 300))
      } else {
        const e = err as Record<string, any>
        const src = String(e.source ?? '?')
        const msg = String(e.msg ?? '').trim()
        const det = e.detail == null ? '' : (typeof e.detail === 'string' ? String(e.detail).trim() : JSON.stringify(e.detail))
        const meta: Record<string, any> = (e.metadata && typeof e.metadata === 'object') ? e.metadata : {}
        const line1 = String(e.line ?? e.file ?? '').replace(/\n/g, ' ').slice(0, 300)
        const occ = Number(e.occurrenceCount ?? 1)
        const metaParts = [
          meta.logger ? 'logger=' + String(meta.logger) : '',
          meta.log_path ? 'log=' + String(meta.log_path) : '',
          meta.thread ? 'thread=' + String(meta.thread) : '',
          meta.channel ? 'channel=' + String(meta.channel) : '',
        ].filter(Boolean)
        // msg/detail 常直接是结构化 JSON（如 v2 failed_to_shutdown_pool）：提炼 error/event 做事件行，原文进上下文
        const pick = (raw: string): { err: string; ev: string } => {
          if (!raw.startsWith('{')) return { err: '', ev: '' }
          try {
            const o: any = JSON.parse(raw)
            if (o && typeof o === 'object') return { err: typeof o.error === 'string' ? o.error : '', ev: typeof o.event === 'string' ? o.event : '' }
          } catch { /* 非 JSON */ }
          return { err: '', ev: '' }
        }
        const mPick = pick(msg)
        const dPick = pick(det)
        const errTxt = mPick.err || dPick.err
        const evTxt = mPick.ev || dPick.ev
        const evtLabel = errTxt ? errTxt + (evTxt ? '（event=' + evTxt + '）' : '') : (evTxt ? 'event=' + evTxt : '')
        const isMsgJson = msg.startsWith('{') && (mPick.err || mPick.ev)
        // 结构化原文优先 detail（det 有 error/event 提炼），否则 msg 原文（msg 自身是 JSON 时）
        const fullRaw = det ? (dPick.err || dPick.ev ? det : '') : (isMsgJson ? msg : '')
        title = '错误事件：' + (evtLabel || msg || line1 || src).slice(0, 60)
        lines = [
          '事件：' + (evtLabel || (msg && !isMsgJson ? msg : '') || '—'),
        ]
        if (line1 && !isMsgJson && line1 !== (evtLabel || msg)) lines.push('详情：' + line1)
        if (fullRaw) lines.push('原始日志：' + fullRaw.slice(0, 1800))
        lines.push('来源：' + src + (metaParts.length ? '（' + metaParts.join('；') + '）' : ''))
        lines.push('事件 ID：' + String(e.id ?? '—') + '；状态：' + String(e.status ?? '?') + (e.assignee ? '；认领：' + String(e.assignee) : ''))
        const tf: string[] = []
        if (e.firstSeenAt) tf.push('首现 ' + fmt(e.firstSeenAt))
        if (e.lastSeenAt) tf.push('最近 ' + fmt(e.lastSeenAt))
        if (e.timestamp) tf.push('数据时点 ' + fmt(e.timestamp))
        lines.push('频次：' + occ + ' 次' + (tf.length ? '；' + tf.join('；') : '') + '（' + fetchedAt + ' 看板快照）')
        if (e.level) lines.push('级别：' + String(e.level) + (e.fingerprint ? '；指纹：' + String(e.fingerprint) : ''))
      }

      const message = buildSolveMessage({ kind, title, lines, actorWindow, opts })
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
