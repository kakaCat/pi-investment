# REQ-47939a 技术设计 · 领域模型与用例

> 上游：`architecture.md`（分层与依赖）、`../requirement.md` §5 不变量清单。
> 本文件给出**签名级**设计：类型、规约、用例的入参/出参/前置/后置。

## 1. 聚合与实体

采用两个聚合根（理由：任务有独立生命周期与独立状态机，但依附于需求存在；把任务做成需求的内嵌实体会让 84 个任务的台账渲染与增量更新都要经需求根，收益不足而成本明显）：

| 聚合根 | 标识 | 不变量载体 |
|--------|------|-----------|
| `Requirement` | `RequirementId`（`REQ-[0-9a-f]{6}`） | 状态转移、产物确认门、计划批准、验收与归档、文档同步标记 |
| `Task` | `TaskId`（`t-[0-9a-f]{6}`） | 任务状态转移、done 凭证门、执行段（executions）结算 |

```ts
// domain/requirement/Requirement.ts
export interface Requirement {
  readonly id: RequirementId
  readonly title: string
  description: string
  category: RequirementCategory          // v5 起必填（缺省 feature）
  status: RequirementStatus
  readonly sourceSessionId?: WindowKey
  artifacts: StageArtifact[]
  plan?: Plan
  verification?: Verification
  archive?: Archive
  docSyncPending: DocSyncPending[]
  statusHistory: StatusEvent[]           // v5 起必填（backfill 后无 undefined）
  comments: Comment[]
  version: number
  readonly createdAt: number
  updatedAt: number
}
```

**聚合根上的守卫方法**（非法即抛 `invalid_transition` / `human_gate`，不返回布尔）：

```ts
canMoveTo(this: Requirement, to: RequirementStatus, by: ActorKind): TransitionVerdict
requireArtifact(this: Requirement, kind: ArtifactKind): StageArtifact   // 缺 → missing_artifact
requirePlanApproved(this: Requirement): void                            // 未批 → plan_not_approved
requireAccepting(this: Requirement): void                               // 非验收态 → bad_status
archive(this: Requirement, materials: ArchiveMaterials, by: ActorRef, at: number): void
```

## 2. 值对象

| 值对象 | 形态 | 说明 |
|--------|------|------|
| `RequirementId` / `TaskId` | 品牌字符串 | 构造时校验正则 |
| `WindowKey` | 品牌字符串 | 会话窗口标识（`session-*`） |
| `ActorRef` | `{ kind, sessionId? }` | 沿用现状 |
| `TransitionVerdict` | `{ ok: true } \| { ok: false; code; reason; gate? }` | 所有判定统一返回体 |
| `AcceptanceCriterion` | `{ text; verifiable: boolean; anchor?: string }` | `checkAcceptance()` 的产物 |
| `EvidenceRef` | `{ raw; kind: 'path'\|'command'\|'assertion'; exists?: boolean }` | 证据存在性校验的产物 |
| `SheetItem` | `{ id; source: {'requirement'}\|{'task',taskId}; criterion; evidence; status }` | v5：source 由字符串改为判别联合 |
| `ArchiveMaterials` | `{ dir; docs; mergedInto; indexEntry; manualUpdates?; manualNote? }` | 归档材料 |
| `TaskReport` | `{ at; reportIndex; filesChanged; completed }` | done 凭证门的证据源 |

## 3. 规约（Specification，全部纯函数）

```ts
// domain/requirement/RequirementStatus.ts
export function canReqTransition(from: RequirementStatus, to: RequirementStatus, by: ActorKind): TransitionVerdict
export function agentNextActions(status: RequirementStatus): RequirementStatus[]
export function humanGateFor(from: RequirementStatus, to: RequirementStatus): string | undefined

// domain/task/TaskStatus.ts
export function canTaskTransition(from: TaskStatus, to: TaskStatus, by: ActorKind, openerWindow?: WindowKey, actorWindow?: WindowKey): TransitionVerdict

// domain/task/Acceptability.ts
export function checkAcceptance(text: string): AcceptanceCriterion            // 空话 → verifiable=false
export function checkPlanTasks(tasks: readonly PlanTaskInput[]): PlanTaskCheck  // 两遍：键唯一 + 前向引用；锚点与 implementation 必填

// domain/workflow/DoneEvidenceSpec.ts
export interface DoneEvidenceInput {
  task: Task
  hasReport: boolean
  windowToolActivitySince: number      // 开工以来本窗口最后一次真实工具动作的时间戳（0=无）
  sinceInProgress: number
  now: number
  doneThrottleMs: number
  clientBuildFresh: boolean            // 页面插件任务的构建新鲜度
}
export function checkDoneEvidence(input: DoneEvidenceInput): TransitionVerdict

// domain/workflow/DecomposeSpec.ts
export function checkDecomposeIdempotency(status: RequirementStatus, existingTaskCount: number): TransitionVerdict

// domain/workflow/RollupSpec.ts
export interface RollupDecision { moves: { reqId: RequirementId; from: RequirementStatus; to: RequirementStatus; rule: 'R1'|'R2'|'R3'; note: string }[] }
export function planRollup(view: LedgerView, reqId: RequirementId): RollupDecision
export function planPickupReconcile(view: LedgerView): RollupDecision

// domain/workflow/AcceptanceSheetSpec.ts
export function buildSheet(req: Requirement, tasks: readonly Task[]): VerificationSheet
export function applyVerdicts(sheet: VerificationSheet, verdicts: readonly Verdict[], by: ActorRef, at: number, nextId: () => string): { sheet: VerificationSheet; reworkTasks: ReworkTaskSpec[] }
export function isAllPassed(sheet: VerificationSheet): boolean

// domain/artifact/ArtifactSpec.ts
export function requiredArtifactsFor(stage: StageKey, category: RequirementCategory): readonly ArtifactKind[]
export function confirmGateFor(kind: ArtifactKind): StageKey | undefined
export function archiveDocRulesFor(category: RequirementCategory): ArchiveDocRule
export function checkArchiveMaterials(category: RequirementCategory, m: ArchiveMaterials): TransitionVerdict
export function kindForRelPath(relPath: string): ArtifactKind | undefined

// domain/workflow/DocSyncSpec.ts
export function downstreamOf(kind: ArtifactKind): readonly ArtifactKind[]
export function applyDocSync(req: Requirement, changed: ArtifactKind, at: number): void
export function clearDocSync(req: Requirement, resubmitted: ArtifactKind): void
export function docSyncWarnings(req: Requirement): readonly string[]

// domain/workflow/MilestoneSpec.ts
export function shouldRemindConfirm(req: Requirement, now: number, reminderAfterMs: number): boolean

// domain/stage/StagePromptSpec.ts
export const STAGE_PROMPTS: Readonly<Record<StagePromptKey, string>>
```

## 4. 不变量 → 模块映射（requirement.md §5）

| 不变量 | 唯一实现位置 | 消费方 |
|--------|-------------|--------|
| INV-1 状态机 + 人工闸门 | `domain/requirement/RequirementStatus.ts`、`domain/task/TaskStatus.ts` | `application/use-cases/MoveRequirement.ts`、`MoveTask.ts`、`http/routers/*`、client 渲染 |
| INV-2 单点实现 + 适配层无状态判断 | `tests/layer-boundary.test.ts`（机械检查） | CI/验收 |
| INV-3 幂等 | `domain/workflow/DecomposeSpec.ts`、`ArtifactSpec` 登记去重 | `Decompose.ts`、`SubmitArtifact.ts` |
| INV-4 done 凭证门 | `domain/workflow/DoneEvidenceSpec.ts` | `application/use-cases/MoveTask.ts` |
| INV-5 rollup R1/R2/R3 | `domain/workflow/RollupSpec.ts` | `application/use-cases/MoveTask.ts`、`http/routers/tasks.ts` |
| INV-6 验收单与返工 | `domain/workflow/AcceptanceSheetSpec.ts` | `application/use-cases/{SubmitArtifact,AcceptSheet}.ts`、`http/routers/verdicts.ts` |
| INV-7 产物登记/上浮/证据/漏登 | `domain/artifact/ArtifactSpec.ts` + `adapters/FileDocRepository.ts` | `SubmitArtifact.ts`、`ReportTask.ts`、`http/routers/artifacts.ts` |
| INV-8 迁移无损 | `application/use-cases/MigrateLedger.ts` + `domain/ledger/LedgerV5.ts` | 启动路径 + 迁移脚本 |

## 5. 端口（application/ports.ts）

```ts
export interface ReqboardRepository {
  read<T>(fn: (view: LedgerView) => T): Promise<T>
  snapshot(): LedgerView
  mutate(reason: string, fn: (ledger: MutableLedger) => LedgerChange | undefined): Promise<MutateResult>
  /** 迁移专用：以 v5 结构重写整个台账（备份 + 原子写由实现者负责） */
  replaceAll(reason: string, next: LedgerV5): Promise<void>
}
export interface DocRepository {
  exists(relPath: string): boolean
  read(relPath: string): Promise<string>
  write(relPath: string, content: string): Promise<void>
  list(relDir: string): readonly { name: string; isFile: boolean; mtimeMs: number; size: number }[]
  resolve(relPath: string): string          // 工作区绝对路径（用于候选路径探测）
}
export interface Clock { now(): number }
export interface IdFactory { requirement(): string; task(): string; execution(): string; comment(): string }
export interface SessionProbe {
  windowKey(exec: unknown): string
  requireLiveDriver(exec: unknown): void      // 抛 caller_not_live
  requireDirectHuman(exec: unknown): void     // 抛 delegated_caller / not_direct_human
  toolActivitySince(windowKey: string, since: number): number
  matchesRecentUserMessage(evidence: string, sinceMs: number): boolean
}
export interface UserQuestionPort {
  available(): boolean
  ask(questions: AskQuestion[], opts: { agent?: unknown; signal?: unknown }): Promise<AskAnswer[]>
}
```

**适配层实现**：`JsonLedgerRepository`（现 `store.ts`，保留原子写与损坏隔离）、`FileDocRepository`（现内嵌 fs + `sync-artifacts.ts`）、`SystemClock`、`RandomIdFactory`、`SessionProbeAdapter`（现 `capture-hook.ts`）、`UserQuestionsAdapter`（现 `deps.userQuestions` 接缝）。

## 6. 用例清单（application/use-cases/）

约定：`execute(input, ctx) → Result`；`ctx` 由组合根注入（工具壳或 HTTP 路由构造）；用例**不含** HTTP/工具 schema 细节。

| 用例 | 入参（要点） | 前置 | 后置 |
|------|-------------|------|------|
| `CreateRequirement` | title/category/summary/reason/windowKey | 窗口无绑定需求 | 新需求 draft + statusHistory 首条 |
| `MoveRequirement` | requirementId/to/windowKey | 本窗口绑定 + 合法转移（INV-1） | 状态更新 + 事件 + 评论；人工闸门抛 `human_gate`（附 `gate_question`） |
| `SubmitArtifact` | kind/路径与内容/windowKey | 阶段产物要求（INV-7） | 产物登记（幂等）+ 下游 `docSyncPending` 标记 |
| `ConfirmArtifact` | kind \| plan / 证据来源 | 产物已登记 | 落章 `confirmedVia/confirmedAt/evidence`；计划批准同语义 |
| `AskConfirm` | target/kind/question/options | 绑定的进行中需求 | 弹框 → 落章 → 白名单推进（brainstorming/planning/decomposing 三态） |
| `Decompose` | tasks[]（可省略=落库批准计划） | 计划已批准 + 未拆分（INV-3）+ DAG 合法 | 任务卡落库 + `decomposition.md` + `tasks/<id>.md` 骨架 |
| `MoveTask` | taskId/to/windowKey | 合法转移 + 越权检查 + done 凭证门（INV-4） | 状态更新；开工返回任务卡全文；离开 in_progress 结算执行段；触发 rollup（INV-5） |
| `ReportTask` | taskId/summary/completed/filesChanged/nextStep | 任务属于本窗口需求 | 追加任务卡文档段 + `lastReport` + files 上浮为 `task_output`（INV-7） |
| `AcceptSheet` | batchSize/version | 存在验收单 | 弹框逐项 → 裁决落库 → 未过项生成返工任务并打回 implementing（INV-6）；全过则弹终确认 → archived |
| `SubmitVerification` | summary/evidence[] | 实施态或验收态 | 证据存在性校验 + 生成/续版验收单（v2 只含未过项） |
| `SubmitArchive` | materials | 已 archived/done | 材料登记 + 漏登警告 + archivePath |
| `MigrateLedger` | dry-run 标志 | 台账 schemaVersion ≤ 4 | v5 结构 + `migrations[]` 记录；失败回滚 |
| `QueryState`/`QueryStageDetail`/`QueryStageOverview` | windowKey/requirementId | — | 纯读投影（供 HTTP 与看板渲染） |

**查询用例**（`application/query/`）不写台账，只投影 `LedgerView`，不触发副作用——现 `stage-detail.ts` 的灵魂在此保留。

## 7. 错误码约定（domain/errors.ts）

| code | 触发 | 适配层映射 |
|------|------|-----------|
| `invalid_input` | 入参非法 | HTTP 400 / 工具拒绝 |
| `invalid_transition` | 状态机拒绝 | HTTP 409 |
| `human_gate` | 人工闸门（agent 调用） | HTTP 409 + 返回 `gate_question` 供弹框 |
| `not_bound_to_window` | 需求不属本窗口 | HTTP 403 / 工具拒绝 |
| `no_bound_req` | 窗口无进行中需求 | HTTP 404 |
| `missing_artifact` | 产物未登记就确认/推进 | HTTP 409 |
| `plan_not_approved` | 未批准计划就拆分 | HTTP 409 |
| `already_decomposed` | 重复拆分（INV-3） | HTTP 409 |
| `done_evidence_missing` | 凭证门拒绝（INV-4） | HTTP 409 + 缺失项清单 |
| `bulk_close` | 60s 内连环关任务 | HTTP 409 |
| `stale_build` | 页面插件未构建 | HTTP 409 |
| `version_mismatch` | 验收单版本不符 | HTTP 409 |
| `store_inconsistent` | 台账写入后状态异常 | HTTP 500 |
| `migration_failed` | 迁移校验不通过 | 脚本退出码 1 + 回滚 |

## 8. 与现状的语义等价声明

本设计**不改变**任何现有可观察行为：13→9 工具收敛只减少入口数量，9 个入口的语义与拒绝条件逐一对应现状（逐条对照表在 `test-cases.md` §5）。改动仅限"规则住在哪个文件"与"谁调用谁"。
