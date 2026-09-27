/**
 * L2 用例测试内存端口（REQ-47939a t6）——**v9 世界**（REQ-260927202051-f6df task-17）。
 *
 * ## v9 口径（与 t9 之前最大的差别）
 *
 * 1. **台账没有 `tasks` 键**：任务唯一存储 = 各需求 `docs/requirements/<REQ>/queue.json`
 *    （写方 = `QueueTaskStore`）。`InMemoryRepo` 因此只持 `requirements` / `triages`，
 *    `mutate` 的 change 通道**恒为两键**（与 `JsonLedgerRepository` 同口径）。
 * 2. **任务存取走真实 `QueueTaskStore`**（生产实现），底座是 `InMemoryQueueRepository`
 *    （内存 Map，**不落盘、不碰 fs**，保住 harness 原有的"用例测试不落盘"性质）。
 *
 * ## 为什么不再自带一份"内存 TaskStore"
 *
 * 曾经这里有一份手写 `InMemoryTaskStore`：它把 `mutate` / `createMany` / 派生视图
 * **又实现了一遍**。这类"第二实现"是静默分歧的温床——夹具里绿、线上却崩（或反之），
 * 而两边都不会报错。现在 `deps.taskStore` 就是**真的 `QueueTaskStore`**，
 * 校验、派生视图重算、`QUEUE_NOT_FOUND`、幂等跳过全部走生产代码；
 * 只有**文件 I/O 这一层**换成内存实现（`InMemoryQueueRepository` 实现 `QueueRepository`
 * 端口，`load`/`save` 复用真实 `validateQueueFile`）——与 `FakeDocs` 的做法同构。
 *
 * ## 为什么**不**做同步镜像 getter（Lead 裁定 D 系列）
 *
 * 曾考虑在 `InMemoryRepo` 上挂一个同步 `tasks` getter 以"零改动兼容"老调用方：
 * 收益是 19 个文件不用改，代价是把**已删除的 v8 语义永久留在夹具里**
 * （且 `ReqboardLedger` 已无 `tasks` 键，tsc 照样红）。这笔债比改 19 个文件贵，故不做。
 * 取而代之：`seedTasks` / `setTasks` / `addTasks` / `tasksOf` / `queueOf` 五个便捷方法。
 *
 * ## `makeHarness` 保持**同步**、签名向后兼容
 *
 * 31 个调用方的 `const h = makeHarness({...})` 一行都不用改：`seed.tasks` 现在**同步写入队列**
 * （构造合法 `QueueFile` 后直接落内存仓储；新 store 首访才读盘，因此不需要 await）。
 * 代价（**已写进这里的契约**）：`seedTasks` 必须在该需求**首次被读取之前**调用；
 * 若要在读过之后改任务，用 `await setTasks()` / `await addTasks()`（走真实写路径，缓存一致）。
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
import { QUEUE_VERSION, type QueueFile, type QueueTask } from '../../src/domain/queue/QueueTypes.js'
import { computeEdges, computeLayers, computeReady } from '../../src/domain/queue/topology.js'
import { validateQueueFile } from '../../src/domain/queue/validateQueue.js'
import { QUEUE_ERROR, type QueueRepository, queueRelativePath } from '../../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'
import {
  REQBOARD_SCHEMA_VERSION,
  emptyBuckets,
  type ReqboardLedger,
  type RequirementRecord,
  type TaskRecord,
  type TokenSnapshot,
} from '../../src/shared/protocol.js'

/** 队列文件的 schemaVersion（v9：台账已无 tasks）。 */
const QUEUE_SCHEMA_VERSION = 9

/** 队列文件落点（内存版；仅用于 `pathOf` 与错误信息，不产生真实文件）。 */
const IN_MEMORY_ROOT = '/in-memory-workspace'

/**
 * 由任务集构造**合法**队列文件：派生视图（edges/layers/ready）唯一来源 = `domain/queue/topology`，
 * 每个任务的 `layer` 按拓扑结果回填。**不在这里另写一份分层/就绪判断。**
 */
export function buildQueueFile(requirementId: string, tasks: readonly TaskRecord[], generatedAt = 0): QueueFile {
  const draft: QueueTask[] = tasks.map((t) => ({ ...structuredClone(t), layer: 0 }))
  const layers = computeLayers(draft)
  const layerOf = new Map<string, number>()
  for (const layer of layers) {
    for (const id of layer.tasks) if (!layerOf.has(id)) layerOf.set(id, layer.layer)
  }
  const withLayer: QueueTask[] = draft.map((t) => ({ ...t, layer: layerOf.get(t.id) ?? t.layer }))
  return {
    version: QUEUE_VERSION,
    requirement_id: requirementId,
    schemaVersion: QUEUE_SCHEMA_VERSION,
    generated_at: new Date(generatedAt).toISOString(),
    tasks: withLayer,
    edges: computeEdges(withLayer),
    layers: computeLayers(withLayer),
    ready: computeReady(withLayer),
  }
}

/**
 * 内存队列文件仓储（`QueueRepository` 端口的测试实现；不落盘、不碰 fs）。
 *
 * 与 `JsonQueueRepository` 的语义对齐点（差一处就会让用例测试与线上行为脱节）：
 * - `load`：不存在 → `undefined`；JSON 解析失败 → 告警 + 隔离（内存版没有 rename，隔离 = 移除）；V-1~V-6 不过 → 告警 + `undefined`；
 * - `save`：`requirement_id` 必须与写入目标一致；校验不过 → 抛 `QUEUE_VALIDATION_FAILED` 且**不写入**；
 * - `listRequirementIds` 返回**已排序**（`listAll` 的稳定顺序依赖它）。
 */
export class InMemoryQueueRepository implements QueueRepository {
  private readonly files = new Map<string, string>()
  private readonly writeSeq = new Map<string, number>()
  private readonly root: string
  /** 队列层告警（隔离 / 校验失败），供断言"确实告警了"。 */
  readonly warnings: string[] = []

  constructor(root = IN_MEMORY_ROOT) {
    this.root = root
  }

  pathOf(requirementId: string): string {
    return `${this.root}/docs/requirements/${requirementId}/queue.json`
  }

  relativePathOf(requirementId: string): string {
    return queueRelativePath(requirementId)
  }

  workspaceRoot(): string {
    return this.root
  }

  async listRequirementIds(): Promise<readonly string[]> {
    return [...this.files.keys()].sort()
  }

  async load(requirementId: string): Promise<QueueFile | undefined> {
    const raw = this.files.get(requirementId)
    if (raw === undefined) return undefined
    let parsed: unknown
    try {
      parsed = JSON.parse(raw)
    } catch (error) {
      this.warnings.push(`[queue] 内存队列 JSON 解析失败，已隔离（移除）：${requirementId}（${(error as Error).message}）`)
      this.files.delete(requirementId)
      return undefined
    }
    const result = validateQueueFile(parsed as QueueFile)
    if (!result.passed) {
      this.warnings.push(
        `[queue] 内存队列未通过校验（按不可用处理）：${requirementId} —— ${result.issues
          .slice(0, 3)
          .map((i) => `${i.rule}@${i.path ?? '-'} ${i.message}`)
          .join(' | ')}`,
      )
      return undefined
    }
    return parsed as QueueFile
  }

  async save(requirementId: string, file: QueueFile): Promise<void> {
    if (file?.requirement_id !== requirementId) {
      throw Object.assign(
        new Error(`队列文件 requirement_id(${String(file?.requirement_id)}) 与写入目标需求(${requirementId}) 不一致，拒绝落盘`),
        { code: QUEUE_ERROR.VALIDATION_FAILED },
      )
    }
    const result = validateQueueFile(file)
    if (!result.passed) {
      throw Object.assign(
        new Error(`队列校验未通过（${result.issues.length} 条）：${result.issues.slice(0, 3).map((i) => `${i.rule}@${i.path ?? '-'}`).join(' | ')}`),
        { code: QUEUE_ERROR.VALIDATION_FAILED, issues: result.issues },
      )
    }
    this.files.set(requirementId, JSON.stringify(file, null, 2))
    this.bumpWriteSeq(requirementId)
  }

  /**
   * 测试专用：**同步**播种（原样写入，不做校验）。
   *
   * 存在的理由：`makeHarness` 必须保持同步（31 个调用方不改），而真实 `save` 与
   * `QueueTaskStore.createMany` 都是 async。校验由调用方（`seedGrouped`）先行完成。
   */
  seedSync(requirementId: string, file: QueueFile): void {
    this.files.set(requirementId, JSON.stringify(file, null, 2))
    this.bumpWriteSeq(requirementId)
  }

  private bumpWriteSeq(requirementId: string): void {
    this.writeSeq.set(requirementId, (this.writeSeq.get(requirementId) ?? 0) + 1)
  }

  /**
   * 测试专用：该需求的原始 JSON（诊断 / 断言"到底写没写"）。
   *
   * ⚠️ 口径（Lead 裁定，夹具必须保持可区分性）：
   * **「无队列」= 文件不存在**（`rawOf` → undefined）｜**「空队列」= 文件存在且 `tasks: []`**
   * （`rawOf` → JSON 文本）。两者在仓储层可区分（`load()` → undefined vs 对象），
   * 夹具不得用同一种表示把它们抹平——否则"写操作不隐式建档"这条验收就没法断言。
   */
  rawOf(requirementId: string): string | undefined {
    return this.files.get(requirementId)
  }

  /**
   * 该需求的**队列写入序号**（每次 `save` / `seedSync` 各 +1；从未写过 → 0）。
   *
   * 存在的理由（Lead 裁定 B-2）：台账 `revision` 在任务移出后退化成**恒真**判据
   * （terminal noop 本来就不写台账），拿它断言"重复调用幂等"会永远通过。
   * 队列写入序号是"这份队列文件被改写过几次"的直接计数：
   * **幂等重放不写盘 → 序号不变**，是真判据。
   */
  writeSeqOf(requirementId: string): number {
    return this.writeSeq.get(requirementId) ?? 0
  }
}

/** 台账种子（**只有台账自己的字段**；夹具的 `tasks` 播种在 `HarnessSeed` 里，二者刻意分开）。 */
export interface LedgerSeed {
  revision?: number
  requirements?: readonly RequirementRecord[]
  triages?: ReqboardLedger['triages']
}

/** v9 口径的内存台账仓储（结构上**没有** `tasks` 键）。 */
export class InMemoryRepo implements ReqboardRepository {
  ledger: ReqboardLedger
  constructor(seed?: LedgerSeed) {
    this.ledger = {
      schemaVersion: REQBOARD_SCHEMA_VERSION,
      revision: seed?.revision ?? 0,
      requirements: [...(seed?.requirements ?? [])],
      // REQ-260927202051-f6df t6/t9：台账 v9 起**没有 tasks**（任务唯一存储 = queue.json）。
      triages: (seed?.triages ?? []) as ReqboardLedger['triages'],
    }
  }
  async read<T>(fn: (view: LedgerView) => T): Promise<T> {
    return fn(structuredClone(this.ledger) as LedgerView)
  }
  snapshot(): LedgerView {
    return structuredClone(this.ledger) as LedgerView
  }
  async mutate(_reason: string, fn: (ledger: MutableLedger) => LedgerChange | undefined): Promise<MutateResult> {
    const draft = structuredClone(this.ledger)
    const changed = fn(draft)
    if (changed === undefined) {
      return { changed: { requirements: [], triages: [] }, revision: this.ledger.revision }
    }
    draft.revision += 1
    this.ledger = draft
    // 与 JsonLedgerRepository 同口径：两键恒为数组（`undefined` 补空数组），
    // 用例侧沿用搬迁前"changed.requirements.length"的写法不做防御。
    return {
      changed: {
        requirements: changed.requirements ?? [],
        triages: changed.triages ?? [],
      },
      revision: draft.revision,
    }
  }
  async replaceAll(_reason: string, next: MutableLedger): Promise<void> {
    this.ledger = structuredClone(next) as ReqboardLedger
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

/**
 * `makeHarness` 的播种入参——**夹具自己的类型**，刻意**不**复用 `Partial<ReqboardLedger>`。
 *
 * 理由（Lead 裁决）：台账去 `tasks` 是**存储层**的事，不该顺带取消夹具的播种能力；
 * 复用台账类型会让 `tasks` 这个键在类型上直接报错（excess property），
 * 于是 11 处 `makeHarness({ requirements, tasks: [...] })` 全得改写——既白干又容易漏。
 * 这里显式声明 `tasks`：**签名对调用方保持兼容**，语义上它现在落**队列**而非台账。
 */
export interface HarnessSeed extends LedgerSeed {
  /**
   * 任务卡：**直接落队列**（v9 台账没有任务通道）。
   * 按 `task.requirementId` 分组，各写一份对应需求的 queue.json（跨需求播种因此天然正确）。
   */
  tasks?: readonly TaskRecord[]
}

export interface Harness {
  repo: InMemoryRepo
  /** 内存队列仓储（任务落点；`seedSync` / `rawOf` 是测试专用同步口）。 */
  queueRepo: InMemoryQueueRepository
  /** **真实** `QueueTaskStore`（生产实现，底座 = `queueRepo`）。`deps.taskStore` 就是它。 */
  taskStore: QueueTaskStore
  docs: FakeDocs
  clock: FixedClock
  ids: SeqIds
  session: FakeSession
  questions: FakeQuestions
  deps: UseCaseDeps
  /** 当前内存台账（= `repo.ledger`；任务不在其中——v9 台账无 tasks）。 */
  readonly ledger: ReqboardLedger
  /**
   * 同步播种任务（**须在该需求首次被读取之前**调用）。
   * 按 `task.requirementId` 分组；不合法（V-1~V-6）**立刻抛错**，不留半份脏夹具。
   */
  seedTasks(requirementId: string, tasks: readonly TaskRecord[]): readonly TaskRecord[]
  /** 异步整份替换某需求的任务（走真实写路径：`createMany` 建档 / `mutate` 覆盖；缓存一致）。 */
  setTasks(requirementId: string, tasks: readonly TaskRecord[]): Promise<readonly TaskRecord[]>
  /** 异步追加任务（幂等：已存在 id 跳过）。 */
  addTasks(requirementId: string, tasks: readonly TaskRecord[]): Promise<readonly TaskRecord[]>
  /** 读取某需求的任务（已剥 `layer`）。 */
  tasksOf(requirementId: string): Promise<readonly TaskRecord[]>
  /** 读取某需求的队列文件全量（DAG 视图，**含** layer）。 */
  queueOf(requirementId: string): Promise<QueueFile | undefined>
  /**
   * 改一张卡的字段（**最常用**：把散落在测试里的一堆「从台账取任务数组再就地改字段」收成一行）。
   *
   * **async**（走真实 `QueueTaskStore.mutate`：重算派生视图 → 校验 → 写盘）。
   * `fn` 收到**草稿副本**（含 `layer`），可以原地改后返回 `void`，也可以返回新对象。
   * 任务不存在 → 抛 `TASK_NOT_FOUND`（不静默）；改完不合法（V-1~V-6）→ 抛 `QUEUE_VALIDATION_FAILED` 且不落盘。
   */
  mutateTask(taskId: string, fn: (task: QueueTask) => QueueTask | void): Promise<readonly TaskRecord[]>
  /** `mutateTask` 的补丁式糖：`await h.setTaskFields('t-s', { status: 'done' })`（async，同口径）。 */
  setTaskFields(taskId: string, patch: Partial<TaskRecord>): Promise<readonly TaskRecord[]>
  /**
   * 队列**写入序号**（幂等重放判据，替代恒真的台账 revision）：
   * 每次真正写盘 +1；幂等 noop 不写盘 → 数值不变。从没写过 → 0。
   */
  queueRevisionOf(requirementId: string): number
  /**
   * 队列**文件是否存在**（失败路径用这个，**不要**用 `readQueue() === undefined`：
   * 后者把"文件不存在"与"文件存在但校验不过"混为一谈）。
   */
  queueExists(requirementId: string): boolean
}

/**
 * 同步播种：按任务自述的 `requirementId` 分组 → 构造合法 `QueueFile` → 校验 → 写内存仓储。
 *
 * 为什么要**校验并抛错**：不合法夹具如果静默写进去，`QueueTaskStore.load` 会按"校验不过 = 不可用"
 * 返回 undefined，症状是"任务凭空消失"——排查成本极高。在播种点响亮失败，
 * 报错里直接给 `V-x@path`，一眼知道夹具哪里不合法。
 */
function seedGrouped(queueRepo: InMemoryQueueRepository, requirementId: string, tasks: readonly TaskRecord[]): readonly TaskRecord[] {
  // 空任务集 = 显式建一份**空队列**（文件存在、tasks 为 []）。
  // 这与「无队列」（文件根本不存在）是两件事——Lead 裁定的口径约定，夹具必须能表达后者为"不调用本方法"。
  if (tasks.length === 0) {
    if (requirementId.length === 0) throw new Error('夹具 seedTasks：空任务集时必须给出 requirementId（否则不知道给谁建空队列）')
    queueRepo.seedSync(requirementId, buildQueueFile(requirementId, []))
    return tasks
  }
  const groups = new Map<string, TaskRecord[]>()
  for (const t of tasks) {
    const owner = typeof t.requirementId === 'string' && t.requirementId.length > 0 ? t.requirementId : requirementId
    const arr = groups.get(owner)
    if (arr === undefined) groups.set(owner, [t])
    else arr.push(t)
  }
  for (const [owner, list] of groups) {
    const file = buildQueueFile(owner, list)
    const result = validateQueueFile(file)
    if (!result.passed) {
      throw Object.assign(
        new Error(
          `夹具任务播种失败：需求 ${owner} 的任务集不是合法 v9 队列 —— ${result.issues
            .slice(0, 4)
            .map((i) => `${i.rule}@${i.path ?? '-'} ${i.message}`)
            .join(' | ')}`,
        ),
        { code: QUEUE_ERROR.VALIDATION_FAILED, issues: result.issues },
      )
    }
    queueRepo.seedSync(owner, file)
  }
  return tasks
}

export function makeHarness(seed?: HarnessSeed): Harness {
  const clock = new FixedClock()
  const docs = new FakeDocs(() => clock.t)
  const repo = new InMemoryRepo(seed)
  const session = new FakeSession()
  const questions = new FakeQuestions()
  const ids = new SeqIds()
  const queueRepo = new InMemoryQueueRepository()
  const taskStore = new QueueTaskStore({ repo: queueRepo, now: () => clock.t, onWarn: (m) => queueRepo.warnings.push(m) })
  const deps: UseCaseDeps = { repo, docs, clock, ids, session, questions, taskStore, doneThrottleMs: 0 }

  const harness: Harness = {
    repo,
    queueRepo,
    taskStore,
    docs,
    clock,
    ids,
    session,
    questions,
    deps,
    get ledger(): ReqboardLedger { return repo.ledger },
    seedTasks(requirementId, tasks) { return seedGrouped(queueRepo, requirementId, tasks) },
    async setTasks(requirementId, tasks) {
      if (queueRepo.rawOf(requirementId) === undefined) return taskStore.createMany(requirementId, tasks)
      return taskStore.mutate(requirementId, () => tasks.map((t) => ({ ...structuredClone(t), layer: 0 })))
    },
    addTasks(requirementId, tasks) { return taskStore.createMany(requirementId, tasks) },
    tasksOf(requirementId) { return taskStore.listByRequirement(requirementId) },
    queueOf(requirementId) { return taskStore.readQueue(requirementId) },
    async mutateTask(taskId, fn) {
      const target = await taskStore.get(taskId)
      if (target === undefined) {
        throw Object.assign(new Error(`夹具 mutateTask：任务 ${taskId} 不在任何队列里`), { code: 'TASK_NOT_FOUND' })
      }
      return taskStore.mutate(target.requirementId, (tasks) =>
        tasks.map((t) => {
          if (t.id !== taskId) return t
          const draft = structuredClone(t)
          const out = fn(draft)
          return out === undefined ? draft : out
        }),
      )
    },
    setTaskFields(taskId, patch) {
      return harness.mutateTask(taskId, (t) => { Object.assign(t, patch) })
    },
    queueRevisionOf(requirementId) { return queueRepo.writeSeqOf(requirementId) },
    queueExists(requirementId) { return queueRepo.rawOf(requirementId) !== undefined },
  }

  if (seed?.tasks !== undefined && seed.tasks.length > 0) seedGrouped(queueRepo, seed.requirements?.[0]?.id ?? '', seed.tasks)
  return harness
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
