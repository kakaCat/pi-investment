/**
 * 会话同步服务：监听 session/event，自动捕获新会话进「待归类」区。
 * 三层分类：显式标记（直接绑定）→ LLM 精准（语义+分类）→ 启发式兜底。
 *
 * @module dsh-pmboard/host/session-sync
 */
import type { ReqboardStore } from './store.js'
import { extractExplicitId, classifySessionHeuristic, classifySessionLlm } from './classifier.js'
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
  ids?: {
    triage?: () => string
    requirement?: () => string
    comment?: () => string
  }
}

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

export function titleFromText(text: string): string {
  const first = text.trim().replace(/^#+\s*/, '').split('\n')[0]?.trim() ?? ''
  return first.slice(0, 50).trim()
}

export function isIgnoredSession(sessionId: string, sessionMeta?: unknown): boolean {
  if (sessionId.startsWith('session-reqboard-') || sessionId.startsWith('subagent-') || sessionId.startsWith('child-')) return true
  if (typeof sessionMeta === 'object' && sessionMeta !== null) {
    const s = sessionMeta as { header?: { origin?: string; parentSession?: string; delegationDepth?: number }; meta?: { origin?: string; parentSession?: string; delegationDepth?: number } }
    if (s.header?.origin === 'subagent' || s.meta?.origin === 'subagent') return true
    if (s.header?.parentSession !== undefined || s.meta?.parentSession !== undefined) return true
    if (typeof s.header?.delegationDepth === 'number' && s.header.delegationDepth > 0) return true
    if (typeof s.meta?.delegationDepth === 'number' && s.meta?.delegationDepth > 0) return true
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
        await this.processMessage(sessionId, text, now)
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
    await this.deps.store.mutate('triage-created', (ledger) => {
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

  /** 处理用户消息：显式标记 → LLM → 启发式兜底。 */
  private async processMessage(sessionId: string, text: string, now: number): Promise<void> {
    // 第 0 层：显式标记检测（#REQ-xxx / #t-xxx）
    const explicit = extractExplicitId(text)
    if (explicit) {
      await this.deps.store.mutate('triage-updated', (ledger) => {
        const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
        if (!tri) return undefined
        tri.firstMessageText = text.slice(0, 2000)
        tri.suggestedAction = explicit.kind === 'req' ? 'bind_req' : 'bind_task'
        tri.suggestedTargetId = explicit.id
        tri.score = 100
        tri.comments.push({
          id: this.deps.ids?.comment?.() ?? newCommentId(),
          body: `[显式标记] 消息包含 ${explicit.kind === 'req' ? '需求' : '任务'}标记 #${explicit.id}，直接建议绑定`,
          createdAt: now,
        })
        return { triages: [tri] }
      })
      return
    }

    // 第 1 层：LLM 精准分类（异步，不阻塞）
    void this.runLlmClassification(sessionId, text, now)
  }

  /** LLM 分类 + 需求分类（异步，后台运行）。 */
  private async runLlmClassification(sessionId: string, text: string, now: number): Promise<void> {
    try {
      const ledger = await this.deps.store.read(l => l)
      const llmResult = await classifySessionLlm({
        firstMessage: text,
        requirements: ledger.requirements
          .filter(r => r.status !== 'archived' && r.status !== 'canceled')
          .map(r => ({ id: r.id, title: r.title, description: r.description, status: r.status })),
        tasks: ledger.tasks
          .filter(t => t.status !== 'done' && t.status !== 'canceled')
          .map(t => ({ id: t.id, title: t.title, context: t.context, phase: t.phase, status: t.status })),
      })

      await this.deps.store.mutate('triage-updated', (draft) => {
        const tri = draft.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
        if (!tri) return undefined
        tri.firstMessageText = text.slice(0, 2000)
        tri.suggestedAction = llmResult.action
        tri.suggestedTargetId = llmResult.targetId
        tri.score = llmResult.confidence
        tri.comments.push({
          id: this.deps.ids?.comment?.() ?? newCommentId(),
          body: `[LLM 分类] 建议：${llmResult.action}${llmResult.targetId ? ' → ' + llmResult.targetId : ''}（置信度 ${llmResult.confidence}）\n理由：${llmResult.reason}${llmResult.category ? '\n分类：' + llmResult.category : ''}${llmResult.suggestedTitle ? '\n建议标题：' + llmResult.suggestedTitle : ''}`,
          createdAt: now,
        })
        return { triages: [tri] }
      })
    } catch (err) {
      // LLM 失败 → 启发式兜底
      console.warn('[reqboard] LLM classification failed, falling back to heuristic:', err)
      await this.runHeuristicFallback(sessionId, text, now)
    }
  }

  /** 启发式兜底（LLM 失败时）。 */
  private async runHeuristicFallback(sessionId: string, text: string, now: number): Promise<void> {
    const ledger = await this.deps.store.read(l => l)
    const heuristic = classifySessionHeuristic(text, ledger.requirements, ledger.tasks)

    await this.deps.store.mutate('triage-updated', (draft) => {
      const tri = draft.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      if (!tri) return undefined
      tri.firstMessageText = text.slice(0, 2000)
      tri.suggestedAction = heuristic.action
      tri.suggestedTargetId = heuristic.targetId
      tri.score = heuristic.score
      tri.comments.push({
        id: this.deps.ids?.comment?.() ?? newCommentId(),
        body: `[启发式兜底] 建议：${heuristic.action}${heuristic.targetId ? ' → ' + heuristic.targetId : ''}（分数 ${heuristic.score}）`,
        createdAt: now,
      })
      return { triages: [tri] }
    })
  }

  private async updateTriageTitle(sessionId: string, title: string, now: number): Promise<void> {
    await this.deps.store.mutate('triage-updated', (ledger) => {
      const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      if (!tri) return undefined
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
