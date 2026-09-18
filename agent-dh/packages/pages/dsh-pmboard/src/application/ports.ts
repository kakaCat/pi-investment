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

/** 弹框端口（reqboard_ask_confirm / accept_sheet 的 UI 通道）。 */
export interface UserQuestionPort {
  available(): boolean
  ask(
    questions: readonly AskQuestion[],
    opts: { agent?: unknown; signal?: unknown },
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
export interface UseCaseDeps {
  repo: ReqboardRepository
  docs: DocRepository
  clock: Clock
  ids: IdFactory
  session: SessionProbe
  questions: UserQuestionPort
  /** done 批量关闭节流窗口（毫秒，默认 60000；测试可注入 0 关闭）。 */
  doneThrottleMs?: number
}
