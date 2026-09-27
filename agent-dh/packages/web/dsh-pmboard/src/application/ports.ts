/**
 * application 端口（REQ-47939a t1）——用例依赖的抽象，签名对应 design/domain-model.md §5。
 *
 * 为什么要有端口层：现在 20 处 \`store.mutate\` 直接写在工具壳里，测一条领域规则要搭真
 * store；端口化之后用例测试可以用内存实现（t6 起），I/O 只在 adapters 落地（t5）。
 *
 * 依赖方向（design/architecture.md §2）：application 只依赖 domain 与 shared 的**类型**。
 * 本文件故意只 import type（编译期擦除），不在运行时把 shared 拉进用例。
 *
 * 本任务（t1）只立接口，不提供实现——实现由 t5 落地。
 */

import type {
  ArtifactKind,
  PendingConfirmation,
  PendingConfirmationOutcome,
  ReqboardLedger,
  RequirementRecord,
  TaskRecord,
  TriageRecord,
  TokenSnapshot,
} from '../shared/protocol.js'
import type { ConfirmContext, GateId } from '../domain/gate/GateSpec.js'
import type { QueueFile, QueueTask } from '../domain/queue/QueueTypes.js'
import type { ChainRunSummary } from './gate/GatePostChain.js'

/**
 * 只读台账视图（用例读路径的输入）。
 *
 * REQ-260927202051-f6df t6：`tasks` 已**移除**（台账 v9 不再持有任务卡）。
 * 需要任务请用 `TaskStore`（`taskStore.listByRequirement` / `get` / `listAll`）。
 * 这里**故意不留** `tasks` 字段：留着它会让读方编译通过却永远读到空数组——
 * "看板静默空白"正是本需求要根治的最坏结果，宁可让类型检查当场报错。
 */
export interface LedgerView {
  readonly schemaVersion: number
  readonly revision: number
  readonly requirements: readonly RequirementRecord[]
  readonly triages: readonly TriageRecord[]
}

/** 可写台账（仅在 mutate 回调内可见；写操作必须经 ReqboardRepository.mutate 单点）。 */
export type MutableLedger = ReqboardLedger

/**
 * 一次 mutate 的变更集：只有这两个键。
 *
 * t6：`tasks` 通道**移除**——任务变更不再经台账通知，改由 `TaskStore.subscribe` 广播。
 */
export interface LedgerChange {
  requirements?: readonly RequirementRecord[]
  triages?: readonly TriageRecord[]
}

/** 一次 mutate 的结果。 */
export interface MutateResult {
  changed: LedgerChange
  revision: number
}

/**
 * 台账仓储端口——**写操作的唯一入口**。
 * 实现者（t5 JsonLedgerRepository）负责原子写、损坏隔离与并发串行化。
 */
export interface ReqboardRepository {
  /** 只读查询（不持有引用，回调内不得改）。 */
  read<T>(fn: (view: LedgerView) => T): Promise<T>
  /** 同步快照（渲染前取视图用）。 */
  snapshot(): LedgerView
  /** 单点写：reason 必填（审计与调试）；返回 undefined 表示无变化（不 bump revision）。 */
  mutate(reason: string, fn: (ledger: MutableLedger) => LedgerChange | undefined): Promise<MutateResult>
  /** 迁移专用：整体重写台账（备份 + 原子替换由实现者负责）。 */
  replaceAll(reason: string, next: MutableLedger): Promise<void>
}

// ---------------------------------------------------------------------------
// 任务存储端口（REQ-260927202051-f6df · I-1 / FR-1, FR-2, FR-3）：代码级"队列"
// ---------------------------------------------------------------------------

/**
 * 一次任务变更的通知（供 SSE / 缓存失效）。
 *
 * `revision` 是**进程内**的按需求单调计数（队列文件本身没有 revision 字段：
 * `QueueFile` 的 schema 里没有它，我们不擅自加字段）。因此它只可用于"这次和上次比有没有变"，
 * **不得**当作跨进程/跨重启的可比版本号，也不得用于 CAS——那需要给 QueueFile 加字段（契约变更）。
 */
export interface TaskChange {
  requirementId: string
  kind: 'task-created' | 'task-updated' | 'task-moved' | 'task-removed'
  tasks: readonly TaskRecord[]
  revision: number
}

/** mutate 回调拿到的上下文。 */
export interface QueueMutateContext {
  /**
   * 重算派生视图（edges / layers / ready）并写回草稿。
   *
   * 这是给回调的**可选**便利方法：`TaskStore.mutate` 在回调返回后会**再算一遍**
   * （派生字段绝不允许陈旧），所以回调里调不调都不影响最终落盘内容。
   */
  recompute: () => void
  /** 当前时间（毫秒）；时间由外部注入，保证测试可复现。 */
  now: () => number
}

/**
 * TaskStore 端口（I-1）——**所有读方唯一的任务入口**，不得绕过它直接读 queue.json。
 *
 * 三条出口契约（读方按此写代码）：
 * 1. **出口即剥离 `layer`**：`layer` 是队列文件的派生字段（DAG 层级），不属于 `TaskRecord`。
 *    凡从本端口取"任务"的方法（get / listByRequirement / listAll / mutate / createMany）
 *    返回的对象**不含 `layer` 键**；需要 DAG 视图（含 layer）用 `readQueue`。
 *    这样"层字段泄漏进 /state 响应"从根上不可能发生——收敛在端口一处。
 * 2. **不抛"不存在"**：`listByRequirement` 无队列返回 `[]`、`get` 无此任务返回 `undefined`、
 *    `readQueue` 无队列返回 `undefined`。只有**写**操作在无队列时抛 `QUEUE_NOT_FOUND`。
 * 3. 返回值是**脱离缓存的副本**（改它不会污染 store）。
 */
export interface TaskStore {
  /** 取单个任务（不存在返回 undefined）。 */
  get(taskId: string): Promise<TaskRecord | undefined>
  /** 取某需求的全部任务（无队列文件 → 空数组，不是错误）；顺序 = 队列文件内顺序。 */
  listByRequirement(requirementId: string): Promise<readonly TaskRecord[]>
  /**
   * 取**全部**需求的任务（看板首屏 `/state` 用；避免路由层遍历 82 个需求各读一次文件）。
   *
   * **顺序契约（稳定，D2）**：先按 `requirementId` **字典序升序**分组，组内保持队列文件内的
   * 任务顺序。即 `listAll()` = 对 `listRequirementIds().sort()` 依次拼接 `listByRequirement()`。
   * 之所以强调"稳定"：调用方（看板/回归断言）会比对两次输出的**逐字节相等**，
   * 顺序只要依赖文件系统 readdir 的返回次序就会偶发不等。
   */
  listAll(): Promise<readonly TaskRecord[]>
  /** 取某需求的队列文件全量（**含** DAG 派生视图 layer/edges/layers/ready）；无文件 → undefined。 */
  readQueue(requirementId: string): Promise<QueueFile | undefined>
  /**
   * 在需求维度上变更任务（原子写；返回**改动过的**任务）。
   *
   * `fn` 返回 `undefined` = 无变更（不写盘、不 bump revision、不广播）。
   * 目标需求无 queue.json → 抛 `QUEUE_NOT_FOUND`（写操作不隐式建空档）。
   * 校验失败 → 抛 `QUEUE_VALIDATION_FAILED`，文件保持上次有效内容。
   */
  mutate(
    requirementId: string,
    fn: (tasks: QueueTask[], ctx: QueueMutateContext) => QueueTask[] | undefined,
  ): Promise<readonly TaskRecord[]>
  /**
   * 批量写入（拆分落库用；**幂等**：已存在的 id 跳过不覆盖）。返回**实际新增**的任务。
   *
   * 与 `mutate` 的关键差异：目标需求没有队列文件时**允许新建**（拆分本来就是队列的诞生时刻）。
   * 全部 id 都已存在时不写盘（文件 mtime 不变）——这是"重复调用幂等"的可观测判据。
   */
  createMany(requirementId: string, tasks: readonly TaskRecord[]): Promise<readonly TaskRecord[]>
  /** 订阅任务变更（供 SSE / 缓存失效）；返回退订函数。 */
  subscribe(fn: (change: TaskChange) => void): () => void
}

/** 目录项（文件系统扫描的最小投影）。 */
export interface DocEntry {
  readonly name: string
  readonly isFile: boolean
  readonly mtimeMs: number
  readonly size: number
}
export interface DocRepository {
  /** 相对工作区路径是否存在（evidence 存在性、构建新鲜度都靠它）。 */
  exists(relPath: string): boolean
  read(relPath: string): Promise<string>
  write(relPath: string, content: string): Promise<void>
  /** 列出目录（不存在则返回空数组，不抛）。 */
  list(relDir: string): readonly DocEntry[]
  /**
   * 单文件元数据（存在性 + mtime/size）；不存在/不可读 → undefined。
   * done 凭证门的"文件证据"与"页面插件构建新鲜度"需要 mtime（REQ-47939a t6 补，
   * 口径同搬迁前的 statSync(join(process.cwd(), f)).mtimeMs）。
   */
  stat(relPath: string): { mtimeMs: number; size: number } | undefined
  /** 相对路径 → 绝对路径（候选路径探测用）。 */
  resolve(relPath: string): string
  /** 工作区根（产物清单渲染需要相对路径）。 */
  workspaceRoot(): string
}

/** 时钟端口：domain 禁止 Date.now()，时间一律由外部注入，保证用例可复现。 */
export interface Clock {
  now(): number
}

/** ID 工厂端口：domain 禁止 Math.random()，ID 生成同样注入。 */
export interface IdFactory {
  requirement(): string
  task(): string
  execution(): string
  comment(): string
}

/** 会话探测端口：窗口身份、调用方权限、工具痕迹、近期用户消息（t5 适配 capture-hook）。 */
export interface SessionProbe {
  windowKey(exec: unknown): string
  /** 非活窗口/非本进程驱动 → 抛 caller_not_live。 */
  requireLiveDriver(exec: unknown): void
  /** subagent/非直接人机通道 → 抛 delegated_caller / not_direct_human。 */
  requireDirectHuman(exec: unknown): void
  /** 某窗口"自 since 以来最后一次真实工具动作"的时间戳；无则 0（done 凭证门用）。 */
  toolActivitySince(windowKey: string, since: number): number
  /**
   * 某窗口执行会话的**累计** token 快照（写时快照的唯一读取口，REQ-a33899 t2）。
   * 服务/会话不可得时返回 source='unavailable' 的空桶快照——**不抛错、不阻断主流程**；
   * 调用方据此按「无快照」展示，禁止用旧值/记忆值冒充（R-013）。
   */
  tokenTotals(windowKey: string): TokenSnapshot
  /**
   * evidence 原文是否命中该窗口近期的真实用户消息（文字确认核验用）。
   * 返回 undefined = 核验通道未注入（搬迁前 deps.recentUserMsgs === undefined 的语义，
   * 此时放行并标注"核验未启用"）；返回 {ok:false, reason} = 确实未命中（拒绝并带原因）。
   */
  matchesRecentUserMessage(
    windowKey: string,
    evidence: string,
    withinMs: number,
  ): { ok: boolean; matchedText?: string; reason?: string } | undefined
}

/**
 * 弹框端口（reqboard_ask_confirm / accept_sheet / 立项弹框 的 UI 通道）。
 *
 * REQ-e3b6a0 t7：原先的 `autoContinue` 桩（作答后回调）**已删除**，改为 `gate` 声明——
 * 由装饰器 `adapters/GateAwareQuestions.ts` 统一织入"确认后置链"，故新增弹框入口零成本获得能力。
 */
export interface UserQuestionPort {
  available(): boolean
  ask(
    questions: readonly AskQuestion[],
    opts: {
      agent?: unknown
      signal?: unknown
      /**
       * 闸门声明（可选）：这次弹框属于哪道人工闸门。**带它 = 自动获得确认后置链**
       * （压缩/注入/唤醒/留痕）；不带 = 通用征询，不进链。
       */
      gate?: GateId
    },
  ): Promise<readonly AskAnswer[]>
}

/** 单个弹框问题（题干与选项都要短——长文本会把选项挤出可视区）。 */
export interface AskQuestion {
  id: string
  header?: string
  question: string
  options?: readonly { label: string; description?: string }[]
}

/** 弹框答复（selected 为选项 label；custom 为自定义输入）。 */
export interface AskAnswer {
  id?: string
  selected?: string[]
  custom?: string
}

/**
 * 受信内部**人工门弹框**端口（REQ-260927100007-b8ba FR-14 / design I-10）。与工具层的
 * `questions.ask` 分开：工具层要过 `requireLiveDriver`（`agent.status === 'running'`），
 * 而 Dive 跑在 idle。**仅 Dive 调用**、只发起弹框——肯定项仍由 `actor=human` 走
 * `transitionRequirement`（人工门强度不变）。通道不可用 → `{answered:false}` + 降级投递；
 * 实现须**永不抛**。幂等/防刷屏由调用方按 (需求, 门, 产物指纹) 保证。
 */
export interface GatePromptPort {
  prompt(input: {
    windowKey: string
    requirementId: string
    /** 人工门 id（G1..G4）。 */
    gate: string
    /** 确认产物（artifact）/ 推进确认（plan）。 */
    kind: 'artifact' | 'plan'
    /** kind='artifact' 时必填：要确认的产物 kind。 */
    artifactKind?: string
    question: string
  }): Promise<{ answered: boolean; affirmative: boolean }>
}

/** 用例的依赖集合（组合根构造后注入；用例不得自行 new 实现）。 */
/** 投递结果：三态都要可判（在线 / 离线 / 抛错），且**永不抛**。 */
export interface DeliveryResult {
  readonly delivered: boolean
  readonly reason?: string
}

/**
 * 会话投递端口（已废弃 deliver 方法）：现仅作为 DiveRoundDeliveryPort 的父接口。
 * 实际使用的是子接口 DiveRoundDeliveryPort（Dive 专用投递）。
 */
export interface AgentDeliveryPort {
  // deliver() 已删除，所有需求都在Dive模式下运行
}

/**
 * Dive 回合投递端口（REQ-260926215013-1568 T-3）：在 `AgentDeliveryPort` 之上增「回合消息」能力。
 *
 * 刻意独立成**子类型**而不是直接扩 `AgentDeliveryPort`：既有实现与测试大量只提供 `deliver`，
 * 直接扩父接口会同时打红它们（T-1 的验收是"tsc 错误数不高于基线"）。唯一实现 =
 * `adapters/AgentDeliverer.ts`（T-3 落地）；回合驱动只依赖本端口。
 */
export interface DiveRoundDeliveryPort extends AgentDeliveryPort {
  /**
   * 构造（**不投递**）一条 Dive 回合消息：带 `source:{kind:'dive',requirementId,revision,round}`。
   * 返回消息与身份——驱动需要在 `followup` 之前登记预留（messageId 是 user/message 认领锚点）。
   */
  createRoundMessage(input: {
    requirementId: string
    revision: number
    round: number
    text: string
  }): { message: unknown; messageId: string }
  /** 投递一条已构造消息（保留既有 source）；永不抛，失败以 delivered=false + reason 返回。 */
  deliverMessage(windowKey: string, message: unknown): DeliveryResult
}

/**
 * 闸门后置链端口（REQ-e3b6a0 t3 / FR-2）：Phase A `enqueue` 登记、Phase B `runPending` 执行。
 * 实现 = `application/gate/GatePostChain.ts`（组合根装配）；本端口让用例与适配器只见契约。
 */
export interface GatePostChainPort {
  /** 登记一次闸门作答（幂等键 windowKey+gate+decidedAt）；永不抛。 */
  enqueue(ctx: ConfirmContext): void
  /** 跑某窗口的待处理闸门（幂等 / 可降级 / 永不抛）。 */
  runPending(windowKey: string, session?: unknown): Promise<ChainRunSummary>
}

// ---------------------------------------------------------------------------
// 叶子执行端口（REQ-4842fe t4 / FR-4）：一张子卡 = 一次独立 workflow run
// ---------------------------------------------------------------------------

/** 一次 workflow run 的结果投影（stopReason 非 completed → ok:false，永不抛给调用方）。 */
export interface WorkflowRunOutcome {
  ok: boolean
  /** realm 物化后的 lossless JSON（仅 ok=true 时可信）。 */
  value?: unknown
  /** 失败原因：stopReason(error/cancelled) / engine_unavailable / start_failed。 */
  reason?: string
}

/** 起一次 run 的入参（parent 类型不外泄——端口只透传，adapter 内桥接引擎类型）。 */
export interface WorkflowStartInput {
  script: string
  meta: { name: string; description: string; phases?: string[] }
  args?: Record<string, unknown>
  /** 子代理归属（引擎要求 live Agent）；调用方传入 exec.agent。 */
  parent?: unknown
  signal?: AbortSignal
}

/**
 * WorkflowRunner 端口（唯一实现 = adapters/WorkflowEngineRunner.ts）。
 *
 * 为什么要有这个端口：application/domain 层禁止 import 运行时 `@deepseek-ai/*`
 * （layer-boundary 门禁），而子卡执行必须触达 `ctx.workflowEngine`——端口把
 * "起一次 run" 收敛成一个方法，引擎类型只在 adapter 内出现。
 */
export interface WorkflowRunner {
  start(input: WorkflowStartInput): Promise<WorkflowRunOutcome>
}

// ---------------------------------------------------------------------------
// 团队执行端口（FR-11 路线 A / REQ-260926140539-457b + REQ-260927144541-0481）：
// 子卡实施段改走 DSH 原生 Agent Teams（ctx.agentTeams = TeamService）
// ---------------------------------------------------------------------------

/** 共享任务视图（TeamTaskView 投影；application 层不得 import @deepseek-ai/*）。 */
export interface TeamTaskViewLike {
  id: string
  revision: number
  subject: string
  description: string
  status: 'pending' | 'in_progress' | 'completed' | 'deleted'
  blockedBy: readonly string[]
  writeScopes: readonly string[]
  ownerName?: string
  ready: boolean
  writeScopeWarnings: readonly string[]
}

/** 团队成员视图（TeamMemberView 投影）。 */
export interface TeamMemberViewLike {
  id: string
  name: string
  role: 'lead' | 'teammate'
  status: 'running' | 'idle' | 'inactive' | 'provisioning' | 'failed'
  description?: string
  diagnostics: readonly string[]
}

/** 起一个持久 Worker（teammate）的入参。 */
export interface SpawnWorkerInput {
  name: string
  description: string
  /** 明文提示词；adapter 负责转成引擎要的 ContentBlock[]。 */
  prompt: string
  context?: 'fresh' | 'fork'
  signal?: AbortSignal
}

/** 建一张共享任务的入参（原生 DAG = blockedBy；写范围 = writeScopes）。 */
export interface TeamTaskCreateInput {
  subject: string
  description: string
  blockedBy?: readonly string[]
  writeScopes?: readonly string[]
}

/** CAS 转移入参（FR-11 的 expected_revision 防冲突）。 */
export interface TeamTaskUpdateInput {
  taskId: string
  expectedRevision: number
  action: 'claim' | 'release' | 'edit' | 'set_dependencies' | 'complete' | 'reopen' | 'reassign' | 'delete'
  owner?: string
}

/**
 * AgentTeamsPort（FR-11 路线 A）——唯一实现 = adapters/AgentTeamsAdapter.ts，桥接 `ctx.agentTeams`。
 *
 * 为什么要有这个端口：application/domain 层禁止 import 运行时 `@deepseek-ai/*`（layer-boundary
 * 门禁），而团队执行必须触达 TeamService——端口把"起 Worker / 建任务 / CAS / 等变更"收敛成方法，
 * 服务类型只在 adapter 内出现。`caller` = live Agent 句柄（透传，adapter 内桥接），
 * 与 WorkflowStartInput.parent 同款处理。
 */
export interface AgentTeamsPort {
  /** 服务是否可用（未装配 → false；调用方走兼容路径，不静默成功）。 */
  available(): boolean
  spawnWorker(caller: unknown, input: SpawnWorkerInput): Promise<TeamMemberViewLike>
  listMembers(caller: unknown): readonly TeamMemberViewLike[]
  createTask(caller: unknown, input: TeamTaskCreateInput): Promise<TeamTaskViewLike>
  listTasks(caller: unknown): readonly TeamTaskViewLike[]
  getTask(caller: unknown, taskId: string): TeamTaskViewLike
  updateTask(caller: unknown, input: TeamTaskUpdateInput): Promise<TeamTaskViewLike>
  /** 等下一个团队域变更（事件驱动，零轮询）。timedOut=true 表示窗口内无变更。 */
  waitForChange(caller: unknown, timeoutMs: number, signal?: AbortSignal): Promise<{ timedOut: boolean }>
  /** 中断一个 teammate 的当前回合（保留其待处理收件箱）。 */
  interrupt(caller: unknown, targetName: string): { previousStatus: string }
  /**
   * 给一个**已存在**的 teammate 投递消息（inactive 的会被唤醒——teammate 是 durable/continuable 的）。
   * 为什么必须有它：TeamService 的 teammate 名字**唯一且不可复用**（实测：同名重起被拒
   * `teammate name "…" was already used in this Team`），所以"成员已存在但 inactive"时只能唤醒，不能重起。
   */
  sendMessage(caller: unknown, input: { target: string; content: string }): Promise<{ messageId: string; status: string }>
}

/**
 * 实施链失败处置端口（REQ-4842fe FR-13）：**唯一人工交互面 = 会话内弹框**（三选一）；
 * 不另做告警通道、**不发飞书**、不接通知面（2026-09-21 用户裁定，见 requirement §8 #17）；
 * 宿主日志仅作排障留痕。
 * 唯一纪律：**永不抛**（告警失败不得反过来阻断暂停与留痕）。
 */
export interface FailureAlertPort {
  alert(input: { requirementId: string; title: string; content: string }): void
}

/**
 * 立项拒绝留痕（REQ-260922012924-2e29 FR-5）：「用户在立项弹框选择不立项」的事实。
 * 用途：capture 调用超时/中断导致答复丢失后，重试仍能看见"用户刚拒绝过"，不再重弹。
 */
export interface CaptureRejection {
  windowKey: string
  at: number
  title?: string
}

/** 拒绝留痕端口：record 同步受理异步落盘（失败只告警不抛）；readAll 缺文件 → []，损坏由调用方降级。 */
export interface CaptureRejectionPort {
  record(entry: CaptureRejection): void
  readAll(): Promise<readonly CaptureRejection[]>
}

/**
 * 挂起确认端口（T-4，REQ-260924213231-b1c4 / FR-3 / I-3/I-4）。
 *
 * 唯一实现 = `adapters/PendingConfirmRegistry.ts`（内存 ticket → 状态；窗口绑定 + 过期判定）。
 * 为什么要有端口：ask_confirm / confirm_receipt 用例只依赖契约，内存注册表与过期规则留在 adapter；
 * `UseCaseDeps.pendingConfirms === undefined`（缺省）= 未装配非阻塞能力 → 弹框保持旧的阻塞语义。
 *
 * 各方法都**不抛**：未知 ticket / 窗口不符 / 已过期一律返回 undefined，由用例降级读台账。
 */
export interface PendingConfirmPort {
  /** 登记一次挂起确认并返回 ticket（前缀 `pc-`；id 与时间由实现负责）。 */
  register(input: {
    windowKey: string
    requirementId: string
    target: 'artifact' | 'plan'
    kind?: ArtifactKind
  }): PendingConfirmation
  /** 按 ticket 取（窗口不符或已过期 → undefined）。 */
  get(ticket: string, windowKey: string): PendingConfirmation | undefined
  /** 回填后台作答结果（未知 ticket → undefined；幂等）。 */
  settle(ticket: string, outcome: PendingConfirmationOutcome): PendingConfirmation | undefined
  /** 本窗口**未作答**的挂起确认（FR-9 停手守卫）；没有则 undefined。 */
  pendingForWindow(windowKey: string): PendingConfirmation | undefined
  /**
   * 标记「阻塞等待期间被中止」（REQ-260927123256-196b FR-4）：只写首次 `interruptedAt`（幂等），
   * 未知 ticket → undefined（不抛）。中止记录以 `interruptedAt` 为过期基准，再获一个完整 TTL。
   */
  markInterrupted(ticket: string): PendingConfirmation | undefined
}


// ---------------------------------------------------------------------------
// 后台任务端口（REQ-260925110957-552d / FR-1）：实施链异步化
// ---------------------------------------------------------------------------

/** Job 启动参数 */
export interface JobStartSpec {
  /** Job 类型标识 */
  kind: string
  /** Job 标签（用于日志） */
  label: string
  /** Job 归属（调用方 agent） */
  owner?: unknown
  /** Job 执行函数 */
  run: (signal: AbortSignal) => Promise<void>
}

/** Job 状态快照 */
export interface JobSnapshot {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'killed'
  startedAt?: number
  finishedAt?: number
  error?: string
}

/**
 * 后台任务端口（REQ-260925110957-552d t2）。
 * 
 * 唯一实现 = `adapters/DshJobsAdapter.ts`（桥接 ctx.jobs.start/get）。
 * 缺省 = 后台任务系统不可用 → advanceRequirement 显式返回 {dispatched:false, reason:'jobs_unavailable'}。
 */
export interface JobsPort {
  /** 启动后台任务，返回 Job ID（同步返回，不等执行完成） */
  start(spec: JobStartSpec): Promise<string>
  /** 查询 Job 状态快照（不存在返回 null） */
  get(jobId: string): Promise<JobSnapshot | null>
  /** 检查是否可用 */
  available(): boolean
}

export interface UseCaseDeps {
  repo: ReqboardRepository
  docs: DocRepository
  clock: Clock
  ids: IdFactory
  session: SessionProbe
  questions: UserQuestionPort
  /**
   * 任务存储（队列）端口（REQ-260927202051-f6df I-1）。**缺省 = 未装配**：
   * 用例在读任务时必须显式判空并走"队列不可用"的明确失败/降级路径，
   * 不得假装成功（与 `workflow` / `teams` / `jobs` 的缺省语义一致）。
   */
  taskStore?: TaskStore
  /** done 批量关闭节流窗口（毫秒，默认 60000；测试可注入 0 关闭）。 */
  doneThrottleMs?: number
  /** 立项拒绝留痕（FR-5；缺省 = 无粘滞，行为与 FR-5 前一致）。 */
  rejections?: CaptureRejectionPort
  /**
   * 子卡执行端口（REQ-4842fe t4）。缺省 = 引擎不可用——执行子卡时**显式失败**
   * （ok:false, reason=engine_unavailable），绝不静默成功。
   */
  workflow?: WorkflowRunner
  /**
   * 团队执行端口（FR-11 路线 A / REQ-260926140539-457b）：子卡实施段改走 DSH 原生 Agent Teams。
   * 缺省 = 服务不可用 → 调用方退回 workflow 兼容路径（不静默成功）。
   */
  teams?: AgentTeamsPort
  /** 失败告警通道（缺省 = 只留痕不告警，由组合根决定）。 */
  alert?: FailureAlertPort
  /**
  /**
   * 挂起确认注册表（REQ-260924213231-b1c4 FR-3）。缺省 = 未装配非阻塞能力 →
   * 弹框保持旧的阻塞语义（宽限内作答与原返回体逐字一致）。
   */
  pendingConfirms?: PendingConfirmPort
  /**
   * 后台任务端口（REQ-260925110957-552d FR-1）。缺省 = 后台任务系统不可用 →
   * advanceRequirement 显式返回 {dispatched:false, reason:'jobs_unavailable'}。
   */
  jobs?: JobsPort
  /**
   * 在线 agent 查询（D14 修复）：子卡派发需要 agent 句柄（引擎读 request.parent.session），
   * 而看板「继续」/启动恢复这两条入口没有调用窗口的 exec。runSubtaskStep 据此按父卡所属
   * 需求的绑定窗口兜底解析；解不到则**响亮失败**（不再抛引擎 TypeError）。缺省 = 视为不在线。
   */
  agents?: () => { get?: (id: string) => unknown } | undefined
}