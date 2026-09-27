/**
 * 用例层测试的 **v9 世界**夹具（REQ-260927202051-f6df task-16）。
 *
 * 为什么需要它：`tests/application/harness.ts` 的 `InMemoryRepo` 建在**台账还带 `tasks`** 的旧世界上
 * （它仍给 ledger 塞 `tasks` 键、`mutate` 仍返回 `tasks` 通道）。那个文件不在本卡写域内，故这里给出
 * v9 口径的等价物，供台账域用例测试（`tests/ledger-v6-token.test.ts`）使用：
 *
 * - `V9Repo`：内存 `ReqboardRepository`，**v9 台账结构**（只有 requirements / triages），
 *   与 `adapters/JsonLedgerRepository` 的返回形状一致（changed 恒为两键、revision 语义相同）。
 * - `makeV9Harness`：**真实** `QueueTaskStore` + **真实** `JsonQueueRepository`（临时目录），
 *   并把它注入 `UseCaseDeps.taskStore`。这里**不造 mock 端口**——`QueueTaskStore` 是生产实现，
 *   文件 I/O 用的是 `QueueRepository` 的生产实现，只是把工作区根指向临时目录。
 *
 * 与 `tests/application/harness.ts` 的关系：叶端口假实现（FakeDocs / FixedClock / SeqIds /
 * FakeSession / FakeQuestions）直接复用那边的类（它们与 v9 无关）；只替换"台账仓储"这一层。
 *
 * ⚠️ 临时目录必须由调用方 `dispose()`（测试用 afterEach），否则 /var/folders 会堆积。
 *
 * @module dsh-pmboard/tests/queue/v9-harness
 */
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type {
  LedgerChange,
  LedgerView,
  MutableLedger,
  MutateResult,
  ReqboardRepository,
  UseCaseDeps,
} from '../../src/application/ports.js'
import { JsonQueueRepository } from '../../src/repositories/QueueRepository.js'
import { QueueTaskStore } from '../../src/repositories/QueueTaskStore.js'
import {
  emptyLedger,
  type ReqboardLedger,
  type RequirementRecord,
  type TaskRecord,
} from '../../src/shared/protocol.js'
import { FakeDocs, FakeQuestions, FakeSession, FixedClock, SeqIds } from '../application/harness.js'

/** v9 口径的内存台账仓储（结构上没有 `tasks` 键）。 */
export class V9Repo implements ReqboardRepository {
  ledger: ReqboardLedger

  constructor(seed: { revision?: number; requirements?: readonly RequirementRecord[]; triages?: ReqboardLedger['triages'] } = {}) {
    this.ledger = {
      ...emptyLedger(),
      revision: seed.revision ?? 0,
      requirements: [...(seed.requirements ?? [])],
      triages: [...(seed.triages ?? [])],
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
      // 与 JsonLedgerRepository 同口径：无变更时不 bump revision，changed 恒为两键空数组。
      return { changed: { requirements: [], triages: [] }, revision: this.ledger.revision }
    }
    draft.revision += 1
    this.ledger = draft
    return { changed: { ...changed }, revision: draft.revision }
  }

  async replaceAll(_reason: string, next: MutableLedger): Promise<void> {
    this.ledger = structuredClone(next)
  }
}

export interface V9HarnessSeed {
  revision?: number
  requirements?: readonly RequirementRecord[]
  /** 任务卡：**直接落队列**（v9 不再有台账 tasks 通道）。 */
  tasks?: readonly TaskRecord[]
}

export interface V9Harness {
  /** 临时工作区根（队列文件的落点 = `<root>/docs/requirements/<REQ>/queue.json`）。 */
  root: string
  repo: V9Repo
  queueRepo: JsonQueueRepository
  taskStore: QueueTaskStore
  docs: FakeDocs
  clock: FixedClock
  ids: SeqIds
  session: FakeSession
  questions: FakeQuestions
  deps: UseCaseDeps
  /** 队列层告警（隔离/校验失败等），供断言"确实告警了"。 */
  warnings: string[]
  dispose(): void
}

/**
 * 构造 v9 世界夹具：内存台账 + 真实队列（临时目录）+ 真实 TaskStore 注入 `deps.taskStore`。
 *
 * 是 async 的原因：种子任务要经 `taskStore.createMany` 真实落盘（幂等、重算派生视图、校验全都真跑）。
 */
export async function makeV9Harness(seed: V9HarnessSeed = {}): Promise<V9Harness> {
  const root = mkdtempSync(join(tmpdir(), 'pmboard-v9-'))
  const clock = new FixedClock()
  const docs = new FakeDocs(() => clock.t)
  const repo = new V9Repo({ revision: seed.revision, requirements: seed.requirements })
  const session = new FakeSession()
  const questions = new FakeQuestions()
  const ids = new SeqIds()
  const warnings: string[] = []
  const queueRepo = new JsonQueueRepository({ workspaceRoot: root, onWarn: (m) => warnings.push(m) })
  const taskStore = new QueueTaskStore({ repo: queueRepo, now: () => clock.t, onWarn: (m) => warnings.push(m) })
  const deps: UseCaseDeps = { repo, docs, clock, ids, session, questions, doneThrottleMs: 0, taskStore }

  if (seed.tasks !== undefined && seed.tasks.length > 0) {
    const byRequirement = new Map<string, TaskRecord[]>()
    for (const t of seed.tasks) {
      const arr = byRequirement.get(t.requirementId)
      if (arr === undefined) byRequirement.set(t.requirementId, [t])
      else arr.push(t)
    }
    for (const [requirementId, tasks] of byRequirement) await taskStore.createMany(requirementId, tasks)
  }

  return {
    root,
    repo,
    queueRepo,
    taskStore,
    docs,
    clock,
    ids,
    session,
    questions,
    deps,
    warnings,
    dispose: () => rmSync(root, { recursive: true, force: true }),
  }
}
