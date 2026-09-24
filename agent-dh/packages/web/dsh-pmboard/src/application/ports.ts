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

import type { ReqboardLedger, RequirementRecord, TaskRecord, TriageRecord, TokenSnapshot } from '../shared/protocol.js'
import type { ConfirmContext, GateId } from '../domain/gate/GateSpec.js'
import type { ChainRunSummary } from './gate/GatePostChain.js'

/** 只读台账视图（用例读路径的输入）。 */
export interface LedgerView {
  readonly schemaVersion: number
  readonly revision: number
  readonly requirements: readonly RequirementRecord[]
  readonly tasks: readonly TaskRecord[]
  readonly triages: readonly TriageRecord[]
}

/** 可写台账（仅在 mutate 回调内可见；写操作必须经 ReqboardRepository.mutate 单点）。 */
export type MutableLedger = ReqboardLedger

/** 一次 mutate 的变更集：只有这两个键（据此与"工具响应"区分，见 output-contract 扫描口径）。 */
export interface LedgerChange {
  requirements?: readonly RequirementRecord[]
  tasks?: readonly TaskRecord[]
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

/** 目录项（文件系统扫描的最小投影）。 */
export interface DocEntry {
  readonly name: string
  readonly isFile: boolean
  readonly mtimeMs: number
  readonly size: number
}

/** 文档仓储端口——产物落盘/读取/存在性校验的唯一入口（t5 实现）。 */
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

/** 用例的依赖集合（组合根构造后注入；用例不得自行 new 实现）。 */
/** 投递结果：三态都要可判（在线 / 离线 / 抛错），且**永不抛**。 */
export interface DeliveryResult {
  readonly delivered: boolean
  readonly reason?: string
}

/**
 * 会话投递端口（REQ-e3b6a0 t4 / FR-5）：H4 唤醒与看板通道共用。
 * 唯一实现 = `adapters/AgentDeliverer.ts`（形状纪律写在那里）。
 */
export interface AgentDeliveryPort {
  deliver(windowKey: string, message: { text: string; plugin?: string }): DeliveryResult
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

export interface UseCaseDeps {
  repo: ReqboardRepository
  docs: DocRepository
  clock: Clock
  ids: IdFactory
  session: SessionProbe
  questions: UserQuestionPort
  /** done 批量关闭节流窗口（毫秒，默认 60000；测试可注入 0 关闭）。 */
  doneThrottleMs?: number
  /** 立项拒绝留痕（FR-5；缺省 = 无粘滞，行为与 FR-5 前一致）。 */
  rejections?: CaptureRejectionPort
  /**
   * 子卡执行端口（REQ-4842fe t4）。缺省 = 引擎不可用——执行子卡时**显式失败**
   * （ok:false, reason=engine_unavailable），绝不静默成功。
   */
  workflow?: WorkflowRunner
  /** 失败告警通道（缺省 = 只留痕不告警，由组合根决定）。 */
  alert?: FailureAlertPort
  /**
   * 窗口投递端口（REQ-260923222557-d3b0 FR-2/FR-3）：事件型 worktree 提示词
   * （子任务完成 / 需求归档）经此投给窗口。缺省 = 不投递；**投递失败绝不阻断状态转移**。
   */
  delivery?: AgentDeliveryPort
}