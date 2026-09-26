---
req_id: REQ-260926215013-1568
kind: design
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-9, FR-10, FR-11
---

# 接口设计 · Dive 对齐 Goal driver

**需求**: REQ-260926215013-1568

新增接口全部落在 `application/dive/`（框架无关，端口注入），框架调用面只在 `ReqboardDiveManager` + `wiring/pm-capture-root.ts`。

## DiveRoundPorts（应用层端口） «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-9»

```typescript
/** 回合驱动器的全部 I/O 端口（实现全在 adapters/组合根；application 不 import 框架）。 */
export interface DiveRoundPorts {
  /** 台账读（snapshot / read）。判定「该 agent 绑定的 armed+active 需求」。 */
  repo: ReqboardRepository
  /** 精确活体查询 + 驱动串行化边界（对齐 ctx.agents.get / withoutInitiator）。 */
  agents: {
    get(id: string): unknown | undefined
    withoutInitiator<T>(operation: () => T): T
  }
  /** 驱动所在插件 fiber 是否 active（对齐 Goal 的 ctx.fiber.state === 2）。 */
  fiberActive(): boolean
  /** 构造回合消息（含 source:{kind:'dive',…}）但不投递；返回消息与身份。 */
  createRoundMessage(input: {
    requirementId: string; revision: number; round: number; text: string
  }): { message: unknown; messageId: string }
  /** 经 agent.followup 投递一条已构造消息；永不抛（失败以 delivered=false + reason 返回）。 */
  deliverMessage(windowKey: string, message: unknown): { delivered: boolean; reason?: string }
  /** 取消在飞回合（teardown cause='parent'）。 */
  cancel(agent: unknown, cause: 'parent'): void
  /** 等待 agent 静默（teardown 用）。 */
  whenIdle(agent: unknown): Promise<void>
  /** FR-3 耐久检查点：兑现台账写队列排空（= store.read(() => undefined)）。 */
  checkpoint(): Promise<void>
  /** 起轮/入队文案生成（纯函数注入，测试可固定）。 */
  renderRoundText(input: { requirementId: string; round: number; status: string }): string
  now(): number
  logger: { info(m: string): void; debug(m: string): void; warn(m: string, err?: unknown): void }
}
```

**错误契约**：以上端口**不抛**。`repo.mutate` 的 rejection 由调用点 `catch` → `logger.warn` + 解除武装；
驱动体任何异常都在 `requestDrive` 的 `try/catch` 与 `run.then(onRejected)` 双保险内被吞并留痕（FR-4）。

## DiveRoundDriver（状态机入口） «serves: FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, FR-9, FR-11»

```typescript
export type PreStepDecision = { kind: 'reject' } | { kind: 'enter'; messages: unknown[]; startsRequestSeries?: true }

export interface DiveRoundDriver {
  /** 每个宿主事件一个入口；全部同步返回（驱动体异步在内部排队）。 */
  onIdle(agent: unknown, captureTick: () => void): void
  onPreStep(
    agent: unknown, messages: unknown[], signal: { aborted: boolean },
    next: () => Promise<PreStepDecision>,
  ): Promise<PreStepDecision>
  onInboxInserted(agent: unknown, message: unknown): void
  onInboxClaimed(agent: unknown, message: unknown): void
  onInboxDiscarded(agent: unknown, message: unknown): void
  onAgentError(agent: unknown): void
  onAgentDisposed(agent: unknown): void
  onRequirementMoved(requirementId: string): void
  /** session/event 的回合侧簿记（采集侧由 session-driver 先做）。 */
  onSessionEvent(session: unknown, event: unknown): void
  /** 显式触发（兼容旧 checkAndContinue 语义；测试用）。 */
  requestDrive(agent: unknown): void
  /** 关闭准入 → 解除武装 → 取消在飞 → 等静默；幂等。 */
  teardown(): Promise<void>
  /** 当前是否有驱动链在跑或台账写在飞（测试/teardown 同步点）。 */
  whenQuiet(): Promise<void>
}
export function createDiveRoundDriver(ports: DiveRoundPorts): DiveRoundDriver
```

**返回 / 副作用**：
- `onRequirementMoved(requirementId)`：解析需求 → 绑定 agent → `needsCheckpoint=true` + `requestDrive`；**无返回值、绝不 followup**。
- `onPreStep`：返回 `reject`（陈旧/竞争/取消）或 `{...next(), startsRequestSeries:true}`（放行）。
- `onAgentDisposed`：删除该 agent 的 `DriverState`（幂等）。
- `whenQuiet()`：等到 `state.run` 结算且 `writes` 清空；无在飞即立即 resolve。

## pre-step 决策契约 «serves: FR-1, FR-10»

**认领谓词**（`round-state.ts`，纯函数）：

```typescript
/** 只认「本驱动器登记、且内容逐字一致」的回合消息。 */
function sameQueued(content: unknown, source: unknown, attempt: RoundAttempt): boolean

/** 进入 step 前/后的完整栅栏（fail-closed）。 */
function roundReservationValid(
  state: DriverState, content: unknown, source: DiveRoundSource, req: RequirementRecord | undefined,
): boolean
// = fiberActive ∧ !stopping ∧ attempt?.phase==='claimed' ∧ !attempt.stale ∧ !attempt.cancelled
//   ∧ sameQueued(content, source, attempt)
//   ∧ req.id===source.requirementId ∧ req.version===source.revision
//   ∧ req.dive.activation==='armed' ∧ req.dive.phase==='active'
//   ∧ source.round === req.dive.roundsInStage + 1
```

**`restoreOtherClaimed(agent, messages, messageId)`**：把同批中**非本回合**的已认领消息按原顺序 `prepend('next-step', …)` 放回，
跳过仍在 `nextStep/nextTurn` 的消息（幂等），然后返回 `{ kind: 'reject' }`。

## ReqboardDiveManager（订阅持有者） «serves: FR-5, FR-6, FR-9»

```typescript
export default class ReqboardDiveManager extends Service {
  static inject = ['agents', 'reqboard']            // 保持；store 由构造注入（不再依赖不存在的 ctx.reqboard）
  constructor(ctx: Context, store: ReqboardStore)   // 新增 store 形参
  /** 采集路订阅（保持既有签名，index.ts 不变）。 */
  attachSessionDriver(handler: (session: unknown, event: unknown) => void): (() => void) | undefined
  /** 驱动路订阅（保持既有签名）。 */
  attachAgentStatus(handler: (agent: unknown, status: unknown) => void): (() => void) | undefined
  /** round 半句柄：供 session-driver 在 idle 拍定序、供 index 登记 teardown。 */
  roundDriver(): DiveRoundDriver
  /** 解除武装 + 取消在飞 + 等静默；由 index.ts 的 disposer 调用。幂等。 */
  teardown(): Promise<void>
}
```

**自持订阅**（构造内 `ctx.on`，全部委托 round 半；成立与否写日志，失败「响亮」）：
`agent/pre-step`、`agent/inbox/inserted|claimed|discarded`、`agent/error`、`agent/disposed`、`reqboard/requirement-moved`。
`session/event` 与 `agent/status` 仍走 `attachSessionDriver/attachAgentStatus`（index.ts 装配，签名不变）。

**删除**：`shouldContinue` / `triggerContinuation` / `incrementRound` / `checkAndContinue`（逻辑迁入 round 半；全仓无外部调用者，
e2e 里的 `checkAndContinue` 仅为 TODO 注释）。

## AgentDeliveryPort 扩展 «serves: FR-10»

`application/ports.ts`：

```typescript
export interface AgentDeliveryPort {
  deliver(windowKey: string, message: { text: string; plugin?: string }): DeliveryResult
  /** 构造（不投递）带 source:{kind:'dive',requirementId,revision,round} 的回合消息。 */
  createRoundMessage(input: {
    requirementId: string; revision: number; round: number; text: string
  }): { message: unknown; messageId: string }
  /** 投递已构造消息（等价 deliver，但保留既有 source）。 */
  deliverMessage(windowKey: string, message: unknown): DeliveryResult
}
```

`adapters/AgentDeliverer.ts` 实现：`createRoundMessage` 生成
`{ id: idFactory(), role: 'user', content: [{ type: 'text', text }], source: { kind: 'dive', requirementId, revision, round } }`；
`deliverMessage` 复用现有三态守卫（agents 不可得 / 窗口离线 / 无 followup）与 `followup.call(agent, message)`，永不抛。

## 失败形态与留痕（FR-11 契约） «serves: FR-3, FR-4, FR-5, FR-8, FR-11»

| 情形 | 形态 | 留痕（必有） |
|------|------|--------------|
| 起轮 | `followup` 成功 | `info`：`dive round {round}/{max} queued for {reqId}` |
| 拒绝（陈旧/伪造/取消） | pre-step 返回 `reject` | `warn`：含 `reason`（revision/phase/content/source 哪一条不成立） |
| 让位 | `competingQueued=true` | `debug`：`competing input queued → yield until idle` |
| 检查点失败 | 不排队 + 解除武装 | `warn`：`durability checkpoint failed …` |
| 终态阻塞 | `dive.phase='paused'` + comment | `warn` 一次：含上限值与阶段 |
| teardown | 关准入 + 取消在飞 | `info`：`dive driver teardown: N agents, M rounds cancelled` |
| 驱动体异常 | 吞异常 + 解除武装 | `warn`：`dive driver failed …` + disarm 留痕 |

**禁止静默**：任何「到上限/投递失败/检查点失败/订阅未成立」路径都必须至少有 `warn`（订阅缺失在 `pm-capture-root.ts` 与 `ReqboardDiveManager` 两处响亮告警）。
