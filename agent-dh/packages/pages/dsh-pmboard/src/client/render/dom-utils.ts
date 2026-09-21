/**
 * 项目看板视图公共渲染工具（REQ-47939a t11 从 view.ts 机械拆分）。
 * 标签表 / 时间与时长格式化 / markdown 渲染 / 会话窗口 chip / 评论行 / 空态错误。
 * 被 views/* 复用；不含看板业务逻辑。
 *
 * @module dsh-pmboard/client/render/dom-utils
 */
import { esc } from '../html.js'
import type { CommentRecord, RequirementRecord, RequirementStatus, TaskRecord, TaskStatus } from '../types.ts'

/* ------------------------------------------------------------------ utils */

// REQ-6f39b5：流程节点名称对齐唯一事实源 docs/architecture/workflow-stages.md
// 与 stage-panel.ts STAGE_LABELS 保持一致（需求分析/设计/实施）
export const STATUS_LABELS: Record<RequirementStatus, string> = {
  draft: '立项', brainstorming: '需求分析', design: '设计', decomposing: '拆分',
  implementing: '实施', accepting: '验收', done: '完成', archived: '归档', canceled: '取消',
}

// 任务状态标签（2026-09-21 用户裁定）：长式 + in_review=待复核（与需求级「验收」区分）；
// 与 stage-panel.ts TASK_STATUS_LABELS 保持一致。
export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  todo: '待开始', in_progress: '开发中', integrating: '联调中', testing: '测试中',
  in_review: '待复核', done: '已完成', canceled: '已取消',
}

export const PHASE_LABELS: Record<string, string> = {
  doc: '文档', ui: 'UI', analysis: '分析', implement: '实施',
  test: '测试', review: '评审', merge: '合并',
}

export const CATEGORY_LABELS: Record<string, string> = {
  feature: '功能', bug: '缺陷', doc: '文档', refactor: '重构', spike: '调研', chore: '杂项',
}

/**
 * 泳道列（REQ-6f39b5 对齐 workflow-stages.md）：6 个泳道，从立项走到验收：
 * 立项 → 需求分析 → 设计 → 拆分 → 实施 → 验收。
 * done（待归档）需求归入验收泳道显示；archived/canceled 走底部归档区。
 */
export const LANE_STATUSES: readonly RequirementStatus[] = [
  'draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting',
]

/**
 * 会话 id → 窗口码（人类可读短标识）：`session-<uuid>` → `w-<uuid 前 8 位>`。
 * 与 host shared/protocol.ts 的 windowCodeFromSessionId 同规则（client 半不 import
 * host 模块，避免打包把 host 代码带进浏览器包）。
 */
export function windowCodeFromSessionId(sessionId: string): string {
  const raw = sessionId.startsWith('session-') ? sessionId.slice('session-'.length) : sessionId
  const head = raw.split('-')[0] ?? raw
  return `w-${head.slice(0, 8)}`
}

export const fmtTime = (ts: number): string => {
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 任务进度 n/m */
export function progress(done: number, total: number): string {
  return total === 0 ? '0/0' : `${done}/${total}`
}

/**
 * 立项来源窗口 chip —— 「项目看板 ↔ 窗口关联」在看板上的可见锚点。
 * sourceSessionId 是 host 落库时写入的窗口会话 id；点击可跳转到该会话。
 * 人工建卡（GUI/看板按钮）无 sourceSessionId → 不渲染（避免空 chip）。
 */
/**
 * 已归档会话 id 集合的默认值（工作区服务不可用时使用）。
 * 归档会话「日志保留、侧栏不可见」——跳过去也打不开，所以窗口按钮**置灰**但仍可点：
 * 点击给出「已归档，无法跳转」的明确原因，而不是静默无反应。
 */
export const NO_ARCHIVED: ReadonlySet<string> = new Set<string>()

/** 会话是否已归档（集合缺省 → 视为未归档）。 */
export function isArchived(sid: string, archived: ReadonlySet<string>): boolean {
  return archived.has(sid)
}

/**
 * 窗口/会话跳转按钮的统一渲染（REQ-31e11f #5）。
 *
 * 可跳转 → button[data-action=jump-session]；
 * 已归档 → **仍是可点按钮**（灰色 + data-archived="true"）。
 * 旧实现把已归档渲染成无 data-action 的灰 span → 点了完全没反应，
 * 正是「列表的窗口点击不跳转」的真因；现在点击由 board-mount 直接给出
 * 明确原因（该会话已归档、侧栏不可见），不做静默。
 */
export function sessionChipHtml(opts: {
  sid: string
  label: string
  /** 类名（dsh-pm-window 用于来源窗口；dsh-pm-session 用于执行会话） */
  cls: string
  /** title 前缀，如「立项来源窗口」 */
  kind: string
  archived: boolean
}): string {
  const { sid, label, cls, kind, archived } = opts
  const classes = archived ? `${cls} is-archived` : cls
  const title = archived
    ? `${kind}已归档（${esc(sid)}）：日志保留、侧栏不可见，点击查看说明`
    : `${kind}（点击跳转到该会话）：${esc(sid)}`
  return `<button type="button" class="${classes}" data-action="jump-session" data-sid="${esc(sid)}" `
    + (archived ? 'data-archived="true" ' : '')
    + `title="${title}">${archived ? label + ' · 已归档' : label}</button>`
}

export function renderWindowChip(req: RequirementRecord, archived: ReadonlySet<string> = NO_ARCHIVED): string {
  const sid = req.sourceSessionId
  if (!sid) return ''
  return sessionChipHtml({
    sid,
    label: `窗口 ${windowCodeFromSessionId(sid)}`,
    cls: 'dsh-pm-window',
    kind: '立项来源窗口',
    archived: isArchived(sid, archived),
  })
}

export function renderSessionChip(tasks: TaskRecord[], archived: ReadonlySet<string> = NO_ARCHIVED): string {
  for (let i = tasks.length - 1; i >= 0; i--) {
    const execs = tasks[i].executions
    for (let j = execs.length - 1; j >= 0; j--) {
      const sid = execs[j].sessionId
      if (sid) {
        return sessionChipHtml({
          sid,
          label: `会话 ${sid.slice(0, 12)}…`,
          cls: 'dsh-pm-session',
          kind: '执行会话',
          archived: isArchived(sid, archived),
        })
      }
    }
  }
  return ''
}

/* ------------------------------------------------------------------ 需求详情 */

/** 轻量 Markdown 渲染（零依赖，安全：先转义 HTML 再应用标记）。
 * 支持：# 标题、**粗体**、*斜体*、`行内代码`、[链接](url)、- 无序列表、1. 有序列表、```代码块``` */
/**
 * 链接协议白名单（REQ-f0579a FR-5）：只放行 http/https/mailto 与无协议的相对路径/锚点；
 * javascript:/data:/vbscript: 等可执行协议不渲染为链接（低危 XSS 面：href 里的 URL 虽经
 * esc 转义，但 javascript: 协议点击即执行，转义防不住协议本身）。
 */
function isSafeLinkUrl(url: string): boolean {
  const u = url.trim().toLowerCase()
  if (u.startsWith('http://') || u.startsWith('https://') || u.startsWith('mailto:')) return true
  return !u.includes(':')
}

export function renderMarkdown(text: string): string {
  if (!text) return ''
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const out: string[] = []
  let codeBuf: string[] = []
  let inCode = false
  let listItems: string[] = []
  let listOrdered = false

  const flushList = (): void => {
    if (listItems.length === 0) return
    const tag = listOrdered ? 'ol' : 'ul'
    out.push('<' + tag + '>' + listItems.map(i => '<li>' + i + '</li>').join('') + '</' + tag + '>')
    listItems = []
  }

  // 行内标记（输入已转义，安全）
  const inline = (s: string): string => s
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, label, url) =>
      isSafeLinkUrl(url) ? '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + label + '</a>' : label)

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (line.trim().startsWith('```')) {
      flushList()
      if (inCode) {
        out.push('<pre><code>' + codeBuf.join('\n') + '</code></pre>')
        codeBuf = []
        inCode = false
      } else {
        inCode = true
      }
      continue
    }
    if (inCode) { codeBuf.push(esc(line)); continue }
    if (line.trim() === '') { flushList(); continue }
    const h = line.match(/^(#{1,6})\s+(.+)$/)
    if (h) {
      flushList()
      const lv = h[1].length
      out.push('<h' + lv + '>' + inline(esc(h[2])) + '</h' + lv + '>')
      continue
    }
    const ul = line.match(/^\s*[-*+]\s+(.+)$/)
    if (ul) {
      if (listItems.length > 0 && listOrdered) flushList()
      listOrdered = false
      listItems.push(inline(esc(ul[1])))
      continue
    }
    const ol = line.match(/^\s*\d+[.)]\s+(.+)$/)
    if (ol) {
      if (listItems.length > 0 && !listOrdered) flushList()
      listOrdered = true
      listItems.push(inline(esc(ol[1])))
      continue
    }
    flushList()
    out.push('<p>' + inline(esc(line)) + '</p>')
  }
  flushList()
  if (inCode && codeBuf.length > 0) out.push('<pre><code>' + codeBuf.join('\n') + '</code></pre>')
  return out.join('\n')
}

/**
 * 评论作者 → 展示口径（REQ-31e11f #9：人机协同双方可区分）。
 * data-actor 供样式/测试选择；文本给人看（人 / 窗口 w-xxxx / 系统），
 * 不再直接吐 'human'/'agent' 这种内部枚举值。
 */
export function commentActorLabel(c: CommentRecord): { actor: 'human' | 'agent' | 'system'; text: string } {
  const by = c.createdBy
  const kind = by?.kind ?? 'human'
  if (kind === 'human') return { actor: 'human', text: '人' }
  if (kind === 'system') return { actor: 'system', text: '系统' }
  const sid = by?.sessionId
  return {
    actor: 'agent',
    text: sid !== undefined && sid.length > 0 ? '窗口 ' + windowCodeFromSessionId(sid) : '窗口',
  }
}

/**
 * 评论列表：人工评论（GUI 评论框 POST /comment，actor=human）与窗口 agent 评论
 * 一视同仁地渲染，用 data-actor 区分来源。空库给明确空态而不是白板。
 */
export function renderComments(comments: CommentRecord[]): string {
  if (comments.length === 0) return '<div class="dsh-pm-empty">暂无评论</div>'
  return `<div class="dsh-pm-comments">` + comments.map(c => {
    const who = commentActorLabel(c)
    return `
    <div class="dsh-pm-comment" data-actor="${who.actor}">
      <span class="dsh-pm-comment-meta"><span class="dsh-pm-comment-who" data-actor="${who.actor}">${esc(who.text)}</span> · ${fmtTime(c.createdAt)}</span>
      <div class="dsh-pm-comment-body">${esc(c.body)}</div>
    </div>`
  }).join('') + `</div>`
}

/* ------------------------------------------------------------------ 空态/错误 */

export function buildEmpty(): string {
  return `<div class="dsh-pm-board"><div class="dsh-pm-empty">暂无数据 — 点击「+ 需求」创建第一个需求</div></div>`
}

export function buildError(message: string): string {
  return `<div class="dsh-pm-board"><div class="dsh-pm-error">加载失败：${esc(message)}</div></div>`
}
/* ------------------------------------------------------------------ 时间线 */

/** 时长人类可读（时间线停留 / 任务耗时用）。 */
export function fmtDur(ms: number): string {
  const total = Math.max(0, ms)
  const min = Math.floor(total / 60000)
  if (min < 60) return min + ' 分'
  const hours = Math.floor(min / 60)
  if (hours < 24) return hours + ' 小时 ' + (min % 60) + ' 分'
  const days = Math.floor(hours / 24)
  return days + ' 天 ' + (hours % 24) + ' 小时'
}

/** 终态（不再累计停留时长）。 */
export function isTerminal(status: string): boolean {
  return status === 'done' || status === 'archived' || status === 'canceled'
}

export function short(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) + '…' : text
}
