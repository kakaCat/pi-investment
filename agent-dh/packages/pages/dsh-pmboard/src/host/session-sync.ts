/**
 * 会话同步服务：监听 session/event，自动捕获会话并「自动立项」。
 * 三层分类：显式标记（直接绑定）→ LLM 精准（语义+分类）→ 启发式兜底。
 *
 * 自动立项语义（窗口↔需求 n:n）：
 * - bind 判定对全库 open 需求/任务做（跨窗口），窗口 B 可续做窗口 A 立的需求；
 * - LLM 判 create_req（该窗口此刻无对应需求）且置信度达标 → 自动落一条
 *   status:'draft' 的 REQ（进「立项」泳道），记 sourceSessionId + 追加进该窗口
 *   triage.resultRequirementIds；
 * - 人在回路：GUI 待归类卡显示 LLM 建议（标题/分类可编辑），确认/改绑/拒绝后放行。
 *
 * @module dsh-pmboard/host/session-sync
 */
import type { ReqboardStore } from './store.js'
import {
  cleanUserMessageText,
  extractExplicitId,
  classifySessionHeuristic,
  classifySessionLlm,
  titleFromCleanedText,
  type LlmClassifyOutput,
  type LlmTextCaller,
} from './classifier.js'
import {
  newCommentId,
  newRequirementId,
  newTriageId,
  type ActorRef,
  type RequirementRecord,
  type TriageRecord,
} from '../shared/protocol.js'

export interface SessionSyncDeps {
  store: ReqboardStore
  now: () => number
  /** 真实 LLM 文本调用器（由装配层注入；缺省则走规则模拟+启发式） */
  callLlm?: LlmTextCaller
  ids?: {
    triage?: () => string
    requirement?: () => string
    comment?: () => string
  }
}

/** 自动立项置信度门槛（低于只更新建议，不自动建卡）。 */
export const AUTO_CREATE_MIN_CONFIDENCE = 60

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

/** 标题两两包含/高度重叠 → 视为同一话题（自动立项去重护栏）。 */
function titlesOverlap(a: string, b: string): boolean {
  const x = a.trim()
  const y = b.trim()
  if (x.length === 0 || y.length === 0) return false
  if (x.length <= 6 || y.length <= 6) return x === y
  return x.includes(y) || y.includes(x)
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
      const raw = extractUserMessageText(event.data)
      const text = cleanUserMessageText(raw)
      // 整段都是系统注入块（checkpoint/runtime context）→ 不建卡不立项
      if (text.length === 0) {
        if (raw.trim().length > 0) {
          // 保住"该窗口确实活跃"：已有 pending triage 则只留一条提示评论，不立项
          await this.noteNoiseMessage(sessionId, now)
        }
        return
      }
      await this.processMessage(sessionId, text, now)
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
        resultRequirementIds: [],
        comments: [],
      }
      ledger.triages.push(tri)
      return { triages: [tri] }
    })
  }

  /** 处理用户消息：显式标记 → LLM（自动立项）→ 启发式兜底。 */
  private async processMessage(sessionId: string, text: string, now: number): Promise<void> {
    // 第 0 层：显式标记检测（#REQ-xxx / #t-xxx）
    const explicit = extractExplicitId(text)
    if (explicit) {
      await this.deps.store.mutate('triage-updated', (ledger) => {
        const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
        if (!tri) return undefined
        if (!tri.firstMessageText) tri.firstMessageText = text.slice(0, 2000)
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

    // 第 1 层：LLM 精准分类（异步，不阻塞；自动立项在其中完成）
    void this.runLlmClassification(sessionId, text, now)
  }

  /** 系统噪声消息：只在已有 triage 上留一条计数评论（不进分类，不立项）。 */
  private async noteNoiseMessage(sessionId: string, now: number): Promise<void> {
    await this.deps.store.mutate('triage-updated', (ledger) => {
      const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      if (!tri) return undefined
      const last = tri.comments[tri.comments.length - 1]
      const alreadyNoise = last?.body === '[系统消息] 收到系统注入块，跳过立项'
      if (alreadyNoise) return undefined
      tri.comments.push({
        id: this.deps.ids?.comment?.() ?? newCommentId(),
        body: '[系统消息] 收到系统注入块，跳过立项',
        createdAt: now,
      })
      return { triages: [tri] }
    })
  }

  /** LLM 分类 + 自动立项（异步，后台运行）。 */
  private async runLlmClassification(sessionId: string, text: string, now: number): Promise<void> {
    let result: LlmClassifyOutput
    let source: 'llm' | 'heuristic' = 'llm'
    try {
      const ledger = await this.deps.store.read(l => l)
      const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      const windowRequirementIds = tri?.resultRequirementIds ?? []
      result = await classifySessionLlm(
        {
          firstMessage: text,
          sessionId,
          windowRequirementIds,
          requirements: ledger.requirements
            .filter(r => r.status !== 'archived' && r.status !== 'canceled')
            .map(r => ({ id: r.id, title: r.title, description: r.description, status: r.status })),
          tasks: ledger.tasks
            .filter(t => t.status !== 'done' && t.status !== 'canceled')
            .map(t => ({ id: t.id, title: t.title, context: t.context, phase: t.phase, status: t.status })),
        },
        this.deps.callLlm ? { callLlm: this.deps.callLlm } : undefined,
      )
    } catch (err) {
      // LLM 失败 → 启发式兜底
      console.warn('[reqboard] LLM classification failed, falling back to heuristic:', err)
      source = 'heuristic'
      const ledger = await this.deps.store.read(l => l)
      const heuristic = classifySessionHeuristic(text, ledger.requirements, ledger.tasks)
      result = {
        action: heuristic.action,
        targetId: heuristic.targetId,
        confidence: heuristic.action === 'create_req' ? Math.max(heuristic.score, 40) : heuristic.score,
        reason: heuristic.action === 'create_req' ? '与现有需求/任务语义关联度低，建议新建' : `启发式匹配（分数 ${heuristic.score}）`,
        category: 'feature',
        suggestedTitle: titleFromCleanedText(text),
      }
    }

    await this.applyClassification(sessionId, text, result, source, now)
  }

  /** 落地分类结论：更新 triage 建议字段 + （create_req 且达标时）自动立项草稿 REQ。 */
  private async applyClassification(
    sessionId: string,
    text: string,
    result: LlmClassifyOutput,
    source: 'llm' | 'heuristic',
    now: number,
  ): Promise<void> {
    const actor: ActorRef = { kind: 'agent', sessionId }

    await this.deps.store.mutate('triage-updated', (ledger) => {
      const tri = ledger.triages.find(t => t.sessionId === sessionId && t.status === 'pending')
      if (!tri) return undefined
      if (!Array.isArray(tri.resultRequirementIds)) tri.resultRequirementIds = []
      if (!tri.firstMessageText) tri.firstMessageText = text.slice(0, 2000)
      tri.suggestedAction = result.action
      tri.suggestedTargetId = result.targetId
      tri.suggestedTitle = result.action === 'create_req' ? result.suggestedTitle : undefined
      tri.suggestedCategory = result.action === 'create_req' ? result.category : undefined
      tri.score = result.confidence
      tri.comments.push({
        id: this.deps.ids?.comment?.() ?? newCommentId(),
        body: `[${source === 'llm' ? 'LLM 分类' : '启发式兜底'}] 建议：${result.action}${result.targetId ? ' → ' + result.targetId : ''}（置信度 ${result.confidence}）\n理由：${result.reason}${result.category ? '\n分类：' + result.category : ''}${result.suggestedTitle ? '\n建议标题：' + result.suggestedTitle : ''}`,
        createdAt: now,
      })

      const createdReqs: RequirementRecord[] = []
      const shouldCreate = result.action === 'create_req'
        && result.confidence >= AUTO_CREATE_MIN_CONFIDENCE
        && result.suggestedTitle && result.suggestedTitle.trim().length > 0

      if (shouldCreate) {
        // 去重护栏：与已立项草稿标题同话题 → 改建议绑定，不重复建
        const dup = tri.resultRequirementIds
          .map(id => ledger.requirements.find(r => r.id === id))
          .find(r => r && r.status !== 'canceled' && r.status !== 'archived' && titlesOverlap(r.title, result.suggestedTitle!))
        if (dup) {
          tri.suggestedAction = 'bind_req'
          tri.suggestedTargetId = dup.id
          tri.score = Math.max(tri.score, 90)
          tri.comments.push({
            id: this.deps.ids?.comment?.() ?? newCommentId(),
            body: `[自动立项去重] 与已立项 ${dup.id}「${dup.title}」同话题，建议绑定而非重复新建`,
            createdAt: now,
          })
        } else {
          const reqId = this.deps.ids?.requirement?.() ?? newRequirementId()
          const title = result.suggestedTitle!.trim().slice(0, 120)
          const req: RequirementRecord = {
            id: reqId,
            title,
            description: `（会话自动立项草稿，待人工完善）\n\n来源消息：\n${text.slice(0, 2000)}`,
            category: result.category,
            status: 'draft',
            blocked: false,
            sourceSessionId: sessionId,
            comments: [
              {
                id: this.deps.ids?.comment?.() ?? newCommentId(),
                body: `[自动立项] 来自会话 ${sessionId}，LLM 建议（分类 ${result.category}，置信度 ${result.confidence}）。待人工确认/编辑。`,
                createdAt: now,
                createdBy: actor,
              },
            ],
            version: 1,
            createdAt: now,
            updatedAt: now,
            createdBy: actor,
            updatedBy: actor,
          }
          ledger.requirements.push(req)
          tri.resultRequirementId = reqId
          tri.resultRequirementIds.push(reqId)
          tri.comments.push({
            id: this.deps.ids?.comment?.() ?? newCommentId(),
            body: `[自动立项] 已建草稿 ${reqId}「${title}」（draft，待人工确认）`,
            createdAt: now,
          })
          createdReqs.push(req)
        }
      }
      return { requirements: createdReqs, tasks: [], triages: [tri] }
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
