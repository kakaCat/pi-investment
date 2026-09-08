/**
 * Reqboard 台账：DSH 主目录单 JSON 文件，串行写队列 + 原子写（temp+fsync+rename）
 * + 损坏隔离 + 深冻快照 + 订阅发布。模式沿用 dsh-taskboard host/store.ts（已验证）。
 *
 * @module dashboard-requirement/host/store
 */
import { mkdir, open, readFile, rename } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import {
  REQBOARD_SCHEMA_VERSION,
  emptyLedger,
  type ReqboardLedger,
  type RequirementRecord,
  type TaskRecord,
} from '../shared/protocol.js'

/** 一次已提交的台账变更，交给订阅者（SSE 用）。 */
export interface LedgerChange {
  revision: number
  kind:
    | 'requirement-created' | 'requirement-updated' | 'requirement-moved'
    | 'task-created' | 'task-updated' | 'task-moved'
    | 'triage-created' | 'triage-updated'
    | 'comment-added' | 'execution-recorded' | 'ledger-replaced'
  requirements: readonly RequirementRecord[]
  tasks: readonly TaskRecord[]
  triages: readonly import('../shared/protocol.js').TriageRecord[]
}

export interface ReqboardStoreOptions {
  /** 台账文件绝对路径。 */
  file: string
}

/** 台账结构最低可信度校验（S11 哲学：不信任整份记录，坏条目丢弃并告警）。 */
function isPlausibleLedger(raw: unknown): raw is ReqboardLedger {
  if (typeof raw !== 'object' || raw === null) return false
  const o = raw as Record<string, unknown>
  return typeof o.revision === 'number' && Array.isArray(o.requirements) && Array.isArray(o.tasks) && Array.isArray(o.triages ?? [])
}

function isPlausibleRequirement(raw: unknown): boolean {
  if (typeof raw !== 'object' || raw === null) return false
  const o = raw as Record<string, unknown>
  return typeof o.id === 'string' && /^REQ-[0-9a-f]{6}$/.test(o.id)
    && typeof o.title === 'string' && typeof o.status === 'string'
    && typeof o.version === 'number'
}

function isPlausibleTask(raw: unknown): boolean {
  if (typeof raw !== 'object' || raw === null) return false
  const o = raw as Record<string, unknown>
  return typeof o.id === 'string' && /^t-[0-9a-f]{6}$/.test(o.id)
    && typeof o.requirementId === 'string' && typeof o.title === 'string'
    && typeof o.status === 'string' && Array.isArray(o.dependsOn)
    && typeof o.version === 'number'
}

export class ReqboardStore {
  private readonly file: string
  private ledger: ReqboardLedger = emptyLedger()
  private readonly subscribers = new Set<(change: LedgerChange) => void>()
  private queue: Promise<unknown> = Promise.resolve()
  private loaded = false

  constructor(options: ReqboardStoreOptions) {
    this.file = options.file
  }

  /** 加载（仅一次）：缺文件从空开始；损坏文件隔离不抛错。 */
  async load(): Promise<void> {
    if (this.loaded) return
    try {
      const raw = await readFile(this.file, 'utf8')
      const parsed = JSON.parse(raw) as unknown
      if (isPlausibleLedger(parsed)) {
        const requirements = (parsed.requirements as unknown[]).filter((entry) => {
          const ok = isPlausibleRequirement(entry)
          if (!ok) console.warn('[reqboard] dropping implausible requirement on load:', (entry as { id?: unknown })?.id)
          return ok
        }) as RequirementRecord[]
        const tasks = (parsed.tasks as unknown[]).filter((entry) => {
          const ok = isPlausibleTask(entry)
          if (!ok) console.warn('[reqboard] dropping implausible task on load:', (entry as { id?: unknown })?.id)
          return ok
        }) as TaskRecord[]
        const triages = Array.isArray(parsed.triages) ? (parsed.triages as unknown[]).filter((entry) => {
          const ok = typeof entry === 'object' && entry !== null && typeof (entry as { id?: unknown }).id === 'string'
          if (!ok) console.warn('[reqboard] dropping implausible triage on load:', (entry as { id?: unknown })?.id)
          return ok
        }) as import('../shared/protocol.js').TriageRecord[] : []
        this.ledger = { schemaVersion: REQBOARD_SCHEMA_VERSION, revision: parsed.revision, requirements, tasks, triages }
      }
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code
      if (code !== 'ENOENT') {
        // 损坏隔离：改名挪走重新起空台账，绝不拖垮宿主进程
        try { await rename(this.file, `${this.file}.corrupt-${Date.now()}`) } catch { /* best effort */ }
      }
    }
    this.loaded = true
  }

  /** 当前快照（深冻克隆；改它会抛错而不是悄悄绕过持久化路径）。 */
  snapshot(): ReqboardLedger {
    return deepFreeze(structuredClone(this.ledger))
  }

  getRequirement(id: string): RequirementRecord | undefined {
    const r = this.ledger.requirements.find(x => x.id === id)
    return r === undefined ? undefined : deepFreeze(structuredClone(r))
  }

  getTask(id: string): TaskRecord | undefined {
    const t = this.ledger.tasks.find(x => x.id === id)
    return t === undefined ? undefined : deepFreeze(structuredClone(t))
  }

  /** 订阅已提交变更；返回退订函数。 */
  subscribe(fn: (change: LedgerChange) => void): () => void {
    this.subscribers.add(fn)
    return () => this.subscribers.delete(fn)
  }

  /** 整册导入/替换前的备份。 */
  async backup(): Promise<string> {
    await this.load()
    const target = `${this.file}.backup-${Date.now()}`
    await persistAtomic(target, JSON.stringify(this.ledger, null, 2))
    return target
  }

  /**
   * 串行队列内执行一次变更：变更器拿到结构化克隆，原地改后返回触动的记录；
   * 返回 undefined = 中止不写。落库后 bump revision、原子持久化、通知订阅者。
   */
  async mutate(
    kind: LedgerChange['kind'],
    mutator: (ledger: ReqboardLedger) => { requirements?: RequirementRecord[]; tasks?: TaskRecord[]; triages?: import('../shared/protocol.js').TriageRecord[] } | undefined,
  ): Promise<{ ledger: ReqboardLedger; changed: { requirements: readonly RequirementRecord[]; tasks: readonly TaskRecord[]; triages: readonly import('../shared/protocol.js').TriageRecord[] } }> {
    const run = async () => {
      await this.load()
      const draft: ReqboardLedger = structuredClone(this.ledger)
      const changed = mutator(draft)
      if (changed === undefined) {
        return { ledger: deepFreeze(structuredClone(this.ledger)), changed: { requirements: [] as const, tasks: [] as const, triages: [] as const } }
      }
      draft.revision += 1
      await persistAtomic(this.file, JSON.stringify(draft))
      this.ledger = draft
      const change: LedgerChange = {
        revision: draft.revision,
        kind,
        requirements: changed.requirements ?? [],
        tasks: changed.tasks ?? [],
        triages: changed.triages ?? [],
      }
      for (const fn of this.subscribers) {
        try { fn(change) } catch { /* 订阅者错误不阻断写 */ }
      }
      return {
        ledger: deepFreeze(structuredClone(draft)),
        changed: {
          requirements: (changed.requirements ?? []).map(r => deepFreeze(structuredClone(r))),
          tasks: (changed.tasks ?? []).map(t => deepFreeze(structuredClone(t))),
          triages: (changed.triages ?? []).map(t => deepFreeze(structuredClone(t))),
        },
      }
    }
    const result = (this.queue = this.queue.then(run, run)) as ReturnType<typeof run>
    return result
  }

  /** 串行队列内读（R3：读到的是全部已入队变更之后的精确状态；只读）。 */
  async read<T>(fn: (ledger: ReqboardLedger) => T): Promise<T> {
    const run = async (): Promise<T> => {
      await this.load()
      return fn(deepFreeze(structuredClone(this.ledger)))
    }
    const result = (this.queue = this.queue.then(run, run)) as Promise<T>
    return result
  }
}

/** 递归深冻（防御性：发出去的快照不可改）。 */
function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === 'object') {
    if (!Object.isFrozen(value)) Object.freeze(value)
    for (const key of Object.keys(value as Record<string, unknown>)) {
      deepFreeze((value as Record<string, unknown>)[key])
    }
  }
  return value
}

/** 原子写：写临时文件 → fsync → rename（S10：缺 fsync 断电可留零长文件）。 */
async function persistAtomic(file: string, contents: string): Promise<void> {
  await mkdir(dirname(file), { recursive: true })
  const temp = join(dirname(file), `.${Math.random().toString(36).slice(2)}.tmp`)
  const fh = await open(temp, 'w')
  try {
    await fh.writeFile(contents, 'utf8')
    await fh.sync()
  } finally {
    await fh.close()
  }
  await rename(temp, file)
}
