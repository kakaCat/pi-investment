/**
 * L2 用例测试内存端口（REQ-47939a t6）。
 *
 * 用例只依赖 application/ports.ts 的 6 个端口；本文件给出一套**纯内存**实现，
 * 让用例测试不落盘、不碰 fs（卡片验收：用例测试全部用内存端口实现，无临时目录落盘）。
 */
import type {
  AskAnswer,
  AskQuestion,
  DocEntry,
  DocRepository,
  LedgerChange,
  LedgerView,
  MutableLedger,
  MutateResult,
  ReqboardRepository,
  SessionProbe,
  UseCaseDeps,
  UserQuestionPort,
} from '../../src/application/ports.js'
import { REQBOARD_SCHEMA_VERSION, emptyBuckets, type ReqboardLedger, type RequirementRecord, type TaskRecord, type TokenSnapshot } from '../../src/shared/protocol.js'

export class InMemoryRepo implements ReqboardRepository {
  ledger: ReqboardLedger
  constructor(seed?: Partial<ReqboardLedger>) {
    this.ledger = {
      schemaVersion: REQBOARD_SCHEMA_VERSION,
      revision: seed?.revision ?? 0,
      requirements: (seed?.requirements ?? []) as RequirementRecord[],
      tasks: (seed?.tasks ?? []) as TaskRecord[],
      triages: (seed?.triages ?? []) as ReqboardLedger['triages'],
    }
  }
  async read<T>(fn: (view: LedgerView) => T): Promise<T> {
    return fn(structuredClone(this.ledger))
  }
  snapshot(): LedgerView {
    return structuredClone(this.ledger)
  }
  async mutate(_reason: string, fn: (ledger: MutableLedger) => LedgerChange | undefined): Promise<MutateResult> {
    const draft = structuredClone(this.ledger)
    const changed = fn(draft)
    if (changed === undefined) {
      // 与 JsonLedgerRepository 同口径：changed 永远是数组（undefined 键补空数组），
      // 用例侧沿用搬迁前"changed.requirements.length"的写法不做防御。
      return { changed: { requirements: [], tasks: [] }, revision: this.ledger.revision }
    }
    draft.revision += 1
    this.ledger = draft
    return { changed: { ...changed }, revision: draft.revision }
  }
  async replaceAll(_reason: string, next: MutableLedger): Promise<void> {
    this.ledger = structuredClone(next as ReqboardLedger)
  }
}

export class FakeDocs implements DocRepository {
  files = new Map<string, { content: string; mtimeMs: number }>()
  private now: () => number
  constructor(now: () => number = () => 0) { this.now = now }
  put(relPath: string, content = 'x', mtimeMs?: number): void {
    this.files.set(relPath, { content, mtimeMs: mtimeMs ?? this.now() })
  }
  exists(relPath: string): boolean { return this.files.has(relPath) }
  async read(relPath: string): Promise<string> { return this.files.get(relPath)?.content ?? '' }
  async write(relPath: string, content: string): Promise<void> { this.files.set(relPath, { content, mtimeMs: this.now() }) }
  list(relDir: string): readonly DocEntry[] {
    const prefix = relDir.length > 0 ? relDir.replace(/\/+$/, '') + '/' : ''
    const seen = new Set<string>()
    const out: DocEntry[] = []
    for (const [p, v] of this.files) {
      if (!p.startsWith(prefix)) continue
      const rest = p.slice(prefix.length)
      const name = rest.split('/')[0]!
      if (seen.has(name)) continue
      seen.add(name)
      const isFile = !rest.includes('/')
      out.push({ name, isFile, mtimeMs: v.mtimeMs, size: v.content.length })
    }
    return out
  }
  resolve(relPath: string): string { return relPath }
  workspaceRoot(): string { return '.' }
  stat(relPath: string): { mtimeMs: number; size: number } | undefined {
    const f = this.files.get(relPath)
    return f === undefined ? undefined : { mtimeMs: f.mtimeMs, size: f.content.length }
  }
}

export class FixedClock {
  t: number
  constructor(t = 1_000_000) { this.t = t }
  now(): number { return this.t }
}

export class SeqIds {
  private n = 0
  private next(prefix: string): string {
    this.n += 1
    return prefix + this.n.toString(16).padStart(6, '0')
  }
  requirement(): string { return this.next('REQ-') }
  task(): string { return this.next('t-') }
  execution(): string { return this.next('e-') }
  comment(): string { return this.next('c-') }
}

export class FakeSession implements SessionProbe {
  window = 'session-w-001'
  activity = 5
  recentMatch: { ok: boolean; matchedText?: string; reason?: string } | undefined = undefined
  windowKey(exec: unknown): string {
    const id = (exec as { agent?: { id?: unknown } } | undefined)?.agent?.id
    return typeof id === 'string' ? id : this.window
  }
  requireLiveDriver(_exec: unknown): void { /* 放行 */ }
  requireDirectHuman(_exec: unknown): void { /* 放行 */ }
  toolActivitySince(_windowKey: string, _since: number): number { return this.activity }
  /** 默认不可得（测试按需覆盖）；用例可注入具体快照。 */
  tokenSnapshot: TokenSnapshot = { at: 0, totals: emptyBuckets(), source: 'unavailable' }
  tokenTotals(_windowKey: string): TokenSnapshot { return this.tokenSnapshot }
  matchesRecentUserMessage(): { ok: boolean; matchedText?: string; reason?: string } | undefined {
    return this.recentMatch
  }
}

export class FakeQuestions implements UserQuestionPort {
  availableFlag = true
  answers: AskAnswer[] = []
  asked: AskQuestion[] = []
  available(): boolean { return this.availableFlag }
  async ask(questions: readonly AskQuestion[]): Promise<readonly AskAnswer[]> {
    this.asked = [...questions]
    return this.answers
  }
}

export interface Harness {
  repo: InMemoryRepo
  docs: FakeDocs
  clock: FixedClock
  ids: SeqIds
  session: FakeSession
  questions: FakeQuestions
  deps: UseCaseDeps
}

export function makeHarness(seed?: Partial<ReqboardLedger>): Harness {
  const clock = new FixedClock()
  const docs = new FakeDocs(() => clock.t)
  const repo = new InMemoryRepo(seed)
  const session = new FakeSession()
  const questions = new FakeQuestions()
  const ids = new SeqIds()
  const deps: UseCaseDeps = { repo, docs, clock, ids, session, questions, doneThrottleMs: 0 }
  return { repo, docs, clock, ids, session, questions, deps }
}

/** 最小需求记录（字段对齐 protocol.RequirementRecord）。 */
export function req(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: 'REQ-000001',
    title: '需求',
    description: 'd',
    category: 'feature',
    status: 'draft',
    blocked: false,
    sourceSessionId: 'session-w-001',
    comments: [],
    version: 1,
    createdAt: 1,
    updatedAt: 1,
    createdBy: { kind: 'human' },
    updatedBy: { kind: 'human' },
    statusHistory: [],
    ...over,
  }
}

/** 最小任务记录。 */
export function task(over: Partial<TaskRecord> = {}): TaskRecord {
  return {
    id: 't-000001',
    requirementId: 'REQ-000001',
    title: '任务',
    description: 'd',
    phase: 'implement',
    side: 'backend',
    dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: '跑测试看到绿',
    implementation: '改 x.ts',
    context: '',
    status: 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: 1,
    updatedAt: 1,
    createdBy: { kind: 'agent', sessionId: 'session-w-001' },
    updatedBy: { kind: 'agent', sessionId: 'session-w-001' },
    statusHistory: [],
    ...over,
  }
}
