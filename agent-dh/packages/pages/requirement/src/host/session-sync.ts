/**
 * 会话同步服务：监听 session/event，自动捕获新会话进「待归类」区。
 * 人机回路：一律进 pending，经人确认后才生效。
 *
 * @module dashboard-requirement/host/session-sync
 */
import type { ReqboardStore } from './store.js'
import { classifySession } from './classifier.js'
import {
  newCommentId,
  newRequirementId,
  newTriageId,
  normalizeTitle,
  type ActorRef,
  type RequirementRecord,
  type TriageRecord,
} from '../shared/protocol.js'

export interface SessionSyncDeps {
  store: ReqboardStore
  now: () => number
  /** 可注入 id 生成器（测试用） */
  ids?: {
    triage?: () => string
    requirement?: () => string
    comment?: () => string
  }
}

/** 从 user message payload 提取文本（同 dsh-taskboard session-sync）。 */
export function extractUserMessageText(msg: unknown): string {
  if (typeof msg !== 'object' || msg === null) return ''
  const content = (msg as { content?: unknown }).content
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    return content
      .map(part => {
        if (typeof part === 'string') return part
        if (typeof part === 'object' && part !== null && 'text' in part && typeof (part as { text: unknown }).text === 'string') {
          return (part as { text: string }).text
        }
        return ''
      })
      .filter(Boolean)
      .join('\n')
  }
  return ''
}

/** 从文本提取单行标题。 */
export function titleFromText(text: string): string {
  const first = text.trim().replace(/^#+\s*/, '').split('\n')[0]?.trim() ?? ''
  return first.slice(0, 50).trim()
}

/** 检测是否 subagent/内部执行会话（永不建卡）。 */
export function isIgnoredSession(sessionId: string, sessionMeta?: unknown): boolean {
  if (sessionId.startsWith('session-reqboard-') || sessionId.startsWith('subagent-') || sessionId.startsWith('child-')) return true
  if (typeof sessionMeta === 'object' && sessionMeta !== null) {
    const s = sessionMeta as { header?: { origin?: string; parentSession?: string; delegationDepth?: number }; meta?: { origin?: string; parentSession?: string; delegationDepth?: number } }
    if (s.header?.origin === 'subagent' || s.meta?.origin === 'subagent') return true
    if (s.header?.parentSession !== undefined || s.meta?.parentSession !== undefined) return true
    if (typeof s.header?.delegationDepth === 'number' && s.header.delegationDepth > 0) return true
    if (typeof s.meta?.delegationDepth === 'number' && s.meta.delegationDepth > 0) return true
  }
  return false
}

export class SessionSyncService {
  private readonly unsubscribe: () => void
  private readonly ignored = new Set<string>()

  constructor(private readonly deps: SessionSyncDeps, eventCtx: { on: (event: string, handler: (...args: any[]) => void) => () => void }) {
    this.unsubscribe = eventCtx.on('session/event', (session, event) => {
      void this.handleEvent(String(session.id ?? ''), event as { type: string; data?: unknown }, session as never)
    })
  }

  dispose(): void {
    this.unsubscribe()
  }

  private async handleEvent(
    sessionId: string,
    event: { type: string; data?: unknown },
    sessionMeta?: { header?: { cwd?: string }; meta?: Record<string, unknown> },
  ): Promise<void> {
    if (this.ignored.has(sessionId)) return
    if (isIgnoredSession(sessionId, sessionMeta)) {
      this.ignored.add(sessionId)
      return
    }

    const now = this.deps.now()

    if (event.type === 'turn/start') {
      await this.ensureTriage(sessionId, now)
      return
    }

    if (event.type === 'user/message') {
      const text = extractUserMessageText(event.data)
      if (text.trim().length > 0) {
        await this.updateTriageText(sessionId, text, now)
      }
      return
    }

    if (event.type === 'session/title') {
      const title = typeof event.data === 'object' && event.data !== null && 'title' in event.data
        ? String((event.data as { title: unknown }).title)
        : typeof event.data === 'string' ? event.data : ''
      if (title.trim()) await this.updateTriageTitle(sessionId, title, now)
    }
  }

  private async ensureTriage(sessionId: string, now: number): Promise<void> {
    await this.deps.store.mutate('requirement-created', (ledger) => {
      const existing = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      if (existing) return undefined
      const tri: TriageRecord = {
        id: this.deps.ids?.triage?.() ?? newTriageId(),
        sessionId,
        firstMessageText: '',
        suggestedAction: 'create_req',
        score: 0,
        status: 'pending',
        createdAt: now,
        comments: [],
      }
      ledger.triages.push(tri)
      return { triages: [tri] }
    })
  }

  private async updateTriageText(sessionId: string, text: string, now: number): Promise<void> {
    await this.deps.store.mutate('requirement-updated', (ledger) => {
      const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      if (!tri) return undefined
      tri.firstMessageText = text.slice(0, 2000)
      // 运行分类器
      const suggestion = classifySession(text, ledger.requirements, ledger.tasks)
      tri.suggestedAction = suggestion.action
      tri.suggestedTargetId = suggestion.targetId
      tri.score = suggestion.score
      tri.comments.push({
        id: this.deps.ids?.comment?.() ?? newCommentId(),
        body: `[自动判定] 建议：${suggestion.action}${suggestion.targetId ? ' → ' + suggestion.targetId : ''}（分数 ${suggestion.score}）`,
        createdAt: now,
      })
      return { triages: [tri] }
    })
  }

  private async updateTriageTitle(sessionId: string, title: string, now: number): Promise<void> {
    await this.deps.store.mutate('requirement-updated', (ledger) => {
      const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      if (!tri) return undefined
      // 若 firstMessageText 仍为空（标题先于消息到达），用标题补
      if (tri.firstMessageText.length === 0) {
        tri.firstMessageText = title.slice(0, 2000)
      }
      tri.comments.push({
        id: this.deps.ids?.comment?.() ?? newCommentId(),
        body: `[会话标题] ${title}`,
        createdAt: now,
      })
      return { triages: [tri] }
    })
  }
}
