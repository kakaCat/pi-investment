/**
 * 队列任务存储（REQ-260927202051-f6df · S-5 / I-1 / FR-1, FR-2, FR-3）。
 *
 * `TaskStore` 端口的唯一实现：**所有读方唯一的任务入口**（见 `application/ports.ts`）。
 * 本类只做四件事，别的一律不做：
 *
 * 1. **缓存**：按需求懒加载 + 内存缓存。启动时**不**预读全部需求（TC-11.6）——
 *    首访某需求才读它的 queue.json。
 * 2. **写路径强制重读**：`mutate` / `createMany` 落笔前**必须重读文件**再合并，
 *    **不信任缓存**（UC-4 E2）。理由：多窗口并发写同一需求时，缓存里的任务集可能已被
 *    别的窗口改过；信任缓存 = 用旧快照覆盖别人刚写的内容，属静默丢数据。
 * 3. **派生视图唯一来源**：每次写入前用 `topology.computeLayers/computeEdges/computeReady`
 *    整份重算 layer/edges/layers/ready。**不在这里另写一份 ready 判断**（否则 V-5 的
 *    正反例都用新增的那份实现去校验，检查不出来）。
 * 4. **出口剥离 `layer`**（Lead 裁决 D3）：`layer` 是队列文件的派生字段，不属于 `TaskRecord`。
 *    所有返回"任务"的方法都返回去掉 `layer` 的副本，需要 DAG 视图就用 `readQueue`。
 *
 * 不做什么：不做文件原子写（那是 `QueueRepository`）、不做校验规则实现（那是 `validateQueue`）、
 * 不做需求记录读写（那是 `ReqboardRepository`）。
 *
 * @module dsh-pmboard/repositories/QueueTaskStore
 */
import type { TaskChange, TaskStore } from '../application/ports.js'
import { QUEUE_VERSION, type QueueFile, type QueueTask } from '../domain/queue/QueueTypes.js'
import type { TaskRecord } from '../shared/protocol.js'
import { normalizeQueueFile } from '../domain/queue/normalizeQueue.js'
import { QUEUE_ERROR, type QueueRepository } from './QueueRepository.js'

/** 队列写入时对应台账 schema 版本（v9：台账已无 tasks）。 */
export const QUEUE_SCHEMA_VERSION = 9

export interface QueueTaskStoreOptions {
  /** 队列文件仓储（I-2）。 */
  repo: QueueRepository
  /** 时钟（毫秒），默认 `Date.now`。注入后测试可复现。 */
  now?: () => number
  /** 告警通道（默认 `console.warn`）。 */
  onWarn?: (message: string) => void
}

/** 任务内容指纹（用于判断"这次到底改没改"，避免无变更时白写一次）。 */
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value !== null && typeof value === 'object') {
    const o = value as Record<string, unknown>
    return `{${Object.keys(o)
      .sort()
      .map((k) => `${JSON.stringify(k)}:${canonical(o[k])}`)
      .join(',')}}`
  }
  const json = JSON.stringify(value)
  return json === undefined ? 'undefined' : json
}

/**
 * 任务结构相等（**键序无关**的规范化比较）。
 *
 * 为什么不用裸 `JSON.stringify`：两边键的插入顺序不同就判"不等"，会让我们在
 * "其实没改"时白写一次盘——写盘会 bump 文件 mtime，而 t11 的幂等判据恰恰是
 * "重复调用后文件 mtime 不变"。键序无关的比较才是幂等的正确判据。
 */
function sameTask(a: QueueTask, b: QueueTask): boolean {
  return canonical(a) === canonical(b)
}

/**
 * 出口转换：深拷贝 + 删掉 `layer`（D3）。
 *
 * 为什么深拷贝而不是 `{...task, layer: undefined}`：返回的副本若与缓存共享嵌套数组
 * （executions / statusHistory / revisions），调用方一次 `push` 就会**悄悄改到缓存**，
 * 而后缓存与磁盘不一致——这是最难查的一类漂移。
 */
function toRecord(task: QueueTask): TaskRecord {
  const copy = structuredClone(task) as unknown as Record<string, unknown>
  delete copy.layer
  return copy as unknown as TaskRecord
}

export class QueueTaskStore implements TaskStore {
  private readonly repo: QueueRepository
  private readonly now: () => number
  private readonly onWarn: (message: string) => void
  /** 按需求的队列文件缓存（懒加载；写后整份替换）。 */
  private readonly cache = new Map<string, QueueFile>()
  /** taskId → requirementId 索引（`get` 用）；队列被加载/写入时填充。 */
  private readonly index = new Map<string, string>()
  /** 进程内按需求单调计数（见 ports.TaskChange 的说明：不进文件、不可跨重启比较）。 */
  private readonly revisions = new Map<string, number>()
  private readonly subscribers = new Set<(change: TaskChange) => void>()
  /** 写串行队列（进程内；跨进程靠 rename 原子性 + 写前重读）。 */
  private writeQueue: Promise<unknown> = Promise.resolve()
  /** 是否已做过一次全量扫盘建索引（避免未知 id 反复扫盘）。 */
  private indexComplete = false

  constructor(options: QueueTaskStoreOptions) {
    this.repo = options.repo
    this.now = options.now ?? (() => Date.now())
    this.onWarn = options.onWarn ?? ((message) => console.warn(message))
  }

  // ── 读 ────────────────────────────────────────────────────────────────

  /** 取队列文件（缓存优先）；无文件/损坏/校验失败 → undefined。 */
  async readQueue(requirementId: string): Promise<QueueFile | undefined> {
    const cached = this.cache.get(requirementId)
    if (cached !== undefined) return structuredClone(cached)
    return this.loadInto(requirementId)
  }

  async listByRequirement(requirementId: string): Promise<readonly TaskRecord[]> {
    const file = await this.readQueue(requirementId)
    if (file === undefined) return []
    return file.tasks.map(toRecord)
  }

  /**
   * 全部需求的任务（D2）。顺序契约：`requirementId` 字典序升序分组 + 组内队列文件顺序。
   *
   * 实现口径与注释保持一致：先 `listRequirementIds()`（已排序），依次 `listByRequirement`。
   * 需要"稳定"的消费方（看板回归的逐字节比对）依赖这个顺序，**改排序键等于改契约**。
   */
  async listAll(): Promise<readonly TaskRecord[]> {
    const ids = await this.repo.listRequirementIds()
    const out: TaskRecord[] = []
    for (const id of ids) {
      const tasks = await this.listByRequirement(id)
      for (const t of tasks) out.push(t)
    }
    return out
  }

  async get(taskId: string): Promise<TaskRecord | undefined> {
    const known = this.index.get(taskId)
    if (known !== undefined) {
      const file = await this.readQueue(known)
      const hit = file?.tasks.find((t) => t.id === taskId)
      if (hit !== undefined) return toRecord(hit)
      this.index.delete(taskId) // 索引陈旧（任务已被删）→ 退回全量扫描
    }
    // 索引未命中：扫一遍全部需求目录，建齐索引后重试。
    // 只在**未命中**时才扫盘（不是启动扫全量，TC-11.6 仍成立）；扫完后续命中走缓存。
    await this.buildIndexFromDisk()
    const found = this.index.get(taskId)
    if (found === undefined) return undefined
    const file = await this.readQueue(found)
    const hit = file?.tasks.find((t) => t.id === taskId)
    return hit === undefined ? undefined : toRecord(hit)
  }

  // ── 写 ────────────────────────────────────────────────────────────────

  async createMany(requirementId: string, tasks: readonly TaskRecord[]): Promise<readonly TaskRecord[]> {
    if (tasks.length === 0) return []
    // 防串档：入参任务的 requirementId 必须与目标一致（写错需求 = 任务落到别人档案里）
    for (const t of tasks) {
      if (t.requirementId !== requirementId) {
        throw Object.assign(
          new Error(`任务 ${t.id} 的 requirementId(${t.requirementId}) 与目标需求(${requirementId}) 不一致，拒绝写入`),
          { code: QUEUE_ERROR.VALIDATION_FAILED },
        )
      }
    }

    return this.serialize(async () => {
      const existing = await this.repo.load(requirementId)
      const base: QueueFile = existing ?? {
        version: QUEUE_VERSION,
        requirement_id: requirementId,
        schemaVersion: QUEUE_SCHEMA_VERSION,
        generated_at: new Date(this.now()).toISOString(),
        tasks: [],
        edges: [],
        layers: [],
        ready: [],
      }
      const known = new Set(base.tasks.map((t) => t.id))
      // 幂等：已存在的 id 跳过（**不覆盖**——重复调用拆分不得改写已执行中的卡）
      const fresh: QueueTask[] = tasks.filter((t) => !known.has(t.id)).map((t) => ({ ...structuredClone(t), layer: 0 }))
      if (fresh.length === 0) return [] // 全已存在：不写盘（文件 mtime 不变，t11 幂等判据）

      const next = this.recompute({ ...structuredClone(base), tasks: [...base.tasks.map((t) => structuredClone(t)), ...fresh] })
      next.updated_at = new Date(this.now()).toISOString()
      await this.repo.save(requirementId, next)
      this.commit(requirementId, next)
      // 返回值取 **归一化后的落盘态**（`next`），不取入参 `fresh`：recompute 会把 dependsOn
      // 归约为直接前置，若返回入参副本，调用方（拆分落库的 decomposition.md / 任务卡 / 评论）
      // 会拿到与磁盘不一致的依赖——同一个事实两处口径分叉。
      const freshIds = new Set(fresh.map((t) => t.id))
      const normalizedFresh = next.tasks.filter((t) => freshIds.has(t.id)).map(toRecord)
      this.notify({ requirementId, kind: 'task-created', tasks: normalizedFresh, revision: this.revisions.get(requirementId) ?? 0 })
      return normalizedFresh
    })
  }

  async mutate(
    requirementId: string,
    fn: (tasks: QueueTask[], ctx: { recompute: () => void; now: () => number }) => QueueTask[] | undefined,
  ): Promise<readonly TaskRecord[]> {
    return this.serialize(async () => {
      // 写路径强制重读：不信任缓存（并发窗口可能刚改过同一需求）
      const loaded = await this.repo.load(requirementId)
      if (loaded === undefined) {
        throw Object.assign(
          new Error(`需求 ${requirementId} 没有队列文件，拒绝隐式建档（写操作需先经 createMany）`),
          { code: QUEUE_ERROR.NOT_FOUND },
        )
      }

      let working: QueueTask[] = loaded.tasks.map((t) => structuredClone(t))
      const current: { file: QueueFile } = { file: { ...structuredClone(loaded), tasks: working } }
      const recompute = (): void => {
        current.file = this.recompute({ ...current.file, tasks: working })
      }
      recompute() // 先让草稿处于自洽态，回调看到的派生视图就是当前文件的重算结果

      const returned = fn(working, { recompute, now: this.now })
      if (returned === undefined) return [] // 无变更：不写盘、不广播
      working = returned
      const next = this.recompute({ ...current.file, tasks: working })
      next.updated_at = new Date(this.now()).toISOString()

      const before = new Map(loaded.tasks.map((t) => [t.id, t]))
      const after = new Map(next.tasks.map((t) => [t.id, t]))
      const changed = next.tasks.filter((t) => {
        const prev = before.get(t.id)
        return prev === undefined || !sameTask(prev, t)
      })
      // ⚠️ 删除必须**先于**"无变更"判定（2026-09-27 实测缺陷修复）：
      // 被删掉的任务不出现在 `next.tasks` 里，原来只用 `changed.length === 0` 判"没改"，
      // 于是 `mutate(reqId, () => [])` 这类**纯删除**会提前返回、**静默不写盘**，
      // 且 `kind: 'task-removed'` 变成永远走不到的死分支。
      // 判据改为"**集合与内容都没变**才提前返回"：新增/改动（changed）或删除（removed）任一非空都算变更。
      const removed = [...before.keys()].filter((id) => !after.has(id))
      if (changed.length === 0 && removed.length === 0) return [] // 真没改：不白写（mtime 不变）

      await this.repo.save(requirementId, next)
      this.commit(requirementId, next)

      const created = changed.filter((t) => !before.has(t.id))
      const kind: TaskChange['kind'] =
        created.length > 0 ? 'task-created' : removed.length > 0 ? 'task-removed' : changed.some((t) => before.get(t.id)?.status !== t.status) ? 'task-moved' : 'task-updated'
      // 返回值 = 本次真正改动的任务：新增/内容变化者（`next` 侧）+ **被删除者**（`before` 末态）。
      // 删除没有"after 态"，返回被删卡的末态是唯一能如实表达"这几位变了"的形状；
      // 同时保证 `TaskChange.tasks` 在删除场景也**非空**（订阅者据此失效缓存/刷新看板）。
      const records = [...changed, ...removed.map((id) => before.get(id)!)] .map(toRecord)
      this.notify({ requirementId, kind, tasks: records, revision: this.revisions.get(requirementId) ?? 0 })
      return records
    })
  }

  subscribe(fn: (change: TaskChange) => void): () => void {
    this.subscribers.add(fn)
    return () => this.subscribers.delete(fn)
  }

  // ── 内部 ──────────────────────────────────────────────────────────────

  /**
   * 重算派生视图 —— **唯一实现来源 = `domain/queue/normalizeQueue.normalizeQueueFile`**。
   *
   * 2026-09-29（REQ-260929010300-dbf9 · 用户裁定 B「数据侧」）起，本方法除了原先的
   * layer/edges/layers/ready 重算，还多了一步**传递归约**：把 `tasks[].dependsOn`
   * 从「全部前置（传递闭包）」归一为「直接前置」。理由：闭包是拆分时的写法习惯
   * （线上实测 33/55 份队列带冗余前置），但它是**存储冗余**——每个消费者（画布 / 依赖列 /
   * 任务表）都要各自再折一次。前移到写入这一处后，磁盘上的依赖即直接前置。
   *
   * 归约保持可达性 ⇒ layer/ready 结果不变（语义等价，只去冗余）。见 normalizeQueue 文件头。
   * 返回**新对象**，不改入参。
   */
  private recompute(file: QueueFile): QueueFile {
    return normalizeQueueFile(file)
  }

  /** 写成功后：换缓存 + 刷索引 + bump 进程内 revision。 */
  private commit(requirementId: string, file: QueueFile): void {
    this.cacheFile(requirementId, file)
    this.revisions.set(requirementId, (this.revisions.get(requirementId) ?? 0) + 1)
  }

  /**
   * 装载缓存与索引（**不** bump revision）。
   *
   * 读路径（loadInto）也走这里：缓存填充不是"一次变更"，不该让 revision 计数器跳动——
   * 否则 SSE 消费方看到的版本号会掺进纯粹的读行为。
   */
  private cacheFile(requirementId: string, file: QueueFile): void {
    this.cache.set(requirementId, structuredClone(file))
    for (const [taskId, reqId] of this.index) if (reqId === requirementId) this.index.delete(taskId)
    for (const t of file.tasks) this.index.set(t.id, requirementId)
  }

  private notify(change: TaskChange): void {
    for (const fn of this.subscribers) {
      try {
        fn(change)
      } catch (error) {
        this.onWarn(`[queue] 订阅者回调抛错（已忽略，不阻断写）：${(error as Error).message}`)
      }
    }
  }

  /** 加载某需求并填充缓存/索引；不存在 → undefined（不缓存负结果，下次访问会重试读盘）。 */
  private async loadInto(requirementId: string): Promise<QueueFile | undefined> {
    const file = await this.repo.load(requirementId)
    if (file === undefined) return undefined
    this.cacheFile(requirementId, file)
    return structuredClone(file)
  }

  /**
   * 扫盘建索引（只在 `get` 未命中时调用一次，`indexComplete` 保证只扫一次）。
   *
   * 代价：读一遍全部需求目录里的 queue.json。之所以不放在构造函数：TC-11.6 明令
   * "启动不预读全部 queue.json"，而 `get` 未命中本身就是"要全局找一张卡"的信号。
   * 首次扫完后 `indexComplete=true`：未知 id 的重复查询不再反复扫盘（写路径会自行
   * 维护索引，不需要重新全扫）。
   */
  private async buildIndexFromDisk(): Promise<void> {
    if (this.indexComplete) return
    const ids = await this.repo.listRequirementIds()
    for (const id of ids) {
      if (this.cache.has(id)) continue
      await this.loadInto(id)
    }
    this.indexComplete = true
  }

  /**
   * 写串行化（进程内，**全局**一条队列）。
   *
   * 为什么不用"按需求分锁"：A 需求与 B 需求的写本来互不影响，全局串行只是少一点并发度，
   * 却省掉了锁表本身的状态管理（键什么时候能释放、锁表会不会泄漏）。队列写入是低频事件
   * （拆分 / 状态推进），收益不值那点复杂度。跨进程并发由"写前重读 + rename 原子"兜底。
   */
  private serialize<T>(run: () => Promise<T>): Promise<T> {
    const next = this.writeQueue.then(run, run)
    this.writeQueue = next.then(
      () => undefined,
      () => undefined,
    )
    return next
  }
}
