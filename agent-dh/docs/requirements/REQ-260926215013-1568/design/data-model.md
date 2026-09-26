---
req_id: REQ-260926215013-1568
kind: design
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
---

# 数据模型设计 · Dive 对齐 Goal driver

**需求**: REQ-260926215013-1568

本需求**不新增落盘字段**，只修正一个既有字段的值域 + 新增两个内存态契约与一个消息来源契约。数据契约如下。

## RequirementDive 契约变更 «serves: FR-6, FR-7, FR-8, FR-9»

`packages/web/dsh-pmboard/src/shared/protocol.ts` 的 `RequirementDive`：

| 字段 | 类型 | 约束 / 变化 |
|------|------|-------------|
| `phase` | `'idle' \| 'active' \| 'paused'` | **值域修正**（原为「阶段名联合」：brainstorming/design/…，与 `docs/architecture/reqboard-dive-mode.md`、ClearPause、FR-6/FR-8 全不一致）。驱动器只在 `'active'` 起轮；FR-8 写 `'paused'` |
| `activation` | `'armed' \| 'disarmed'` | 不变。解除武装只改此字段，保留 `phase` |
| `roundsInStage` | `number` | 不变，但**写入口径改变**：仅 admission 时 +1（见 §回合号与计数） |
| `pausedReason` | `string?` | 终态原因，本需求引入稳定值 `'round-limit'`（FR-8）与 `'aborted'`（FR-9）；`clear_pause` 清除 |
| `maxRoundsPerStage` | `number` | 保留（历史字段）。**上限的权威来源是 `getStageConfig(req.status).maxRounds`**；该字段本轮不读取、不写入 |
| `currentStage` / `lastActiveAt` | 可选 | 不变；起轮/解除武装时刷新 `lastActiveAt` |

**约束**：`phase='active' ∧ activation='armed'` 是唯一的「可起轮」态；`phase='paused'` 是终态，除人工 `reqboard_clear_pause` 外不由驱动器改回。

## 回合消息来源契约 «serves: FR-10»

新增结构类型（`shared/protocol.ts`，纯 JSON，无框架依赖）：

```typescript
/** Dive 自动续跑回合消息的来源标识（机器可识别；不变量守卫的锚点）。 */
export interface DiveRoundSource {
  kind: 'dive'
  requirementId: string   // REQ-xxxxxx
  revision: number        // 预留时的 req.version（乐观锁栅栏）
  round: number           // 预留的回合号 = roundsInStage + 1（严格 > 0）
}
export function isDiveRoundSource(s: unknown): s is DiveRoundSource
```

**为什么不做框架级 module augmentation**：Goal 用 `ctx.goals` + `MessageSourceMap` 扩展（`kind:'goal'`）走 `@deepseek-ai/dsh-llm`；
而 pmboard 的依赖树**解析不到** `@deepseek-ai/dsh-llm`（`adapters/AgentDeliverer.ts` 文件头记录过），且 application 层禁 `@deepseek-ai/*` import。
故 `DiveRoundSource` 只在**本包内**以结构类型流通：生产者（AgentDeliverer）写入 `message.source`，消费者（round 驱动 pre-step/认领）结构读取。
框架无需认识该 kind（它只透传未知来源）。

**消息内容不变量**：内容 = 一个文本块，逐字由 `renderDiveRoundText(requirementId, round, status)` 生成；
只有 `source` 逐字段相等**且** `content` 与预留登记逐字相等（`deepEqualJson`）才认领。

## 内存驱动状态契约 «serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-7, FR-9»

```typescript
/** 每 agent 一个（Map<Agent, DriverState>）；进程内存态，不落盘。 */
export interface DriverState {
  agent: unknown              // 精确活体（agents.get(id) === state.agent 才算存活）
  attempt?: RoundAttempt      // 至多一个在飞预留
  competingQueued: boolean    // 有非本回合的入队输入 → 让位到下次空闲
  needsCheckpoint: boolean    // 有耐久义务待兑现
  requested: boolean          // 合并触发标志
  run?: Promise<void>         // 串行驱动链（withoutInitiator）
  stopping: boolean           // teardown 已关准入
}

export interface RoundAttempt {
  requirementId: string
  revision: number            // 预留时需求 version
  round: number               // = 预留时 roundsInStage + 1
  messageId: string           // 消息身份（user/message 认领锚点）
  content: unknown            // 模型可见内容（逐字比对）
  phase: 'queued' | 'claimed' | 'admitted'
  cancelled: boolean          // discarded / aborted / cancel
  stale: boolean              // revision 失效 / 竞争让位
}
```

**状态迁移不变量**：`queued → claimed → admitted` 单向；`cancelled/stale` 可置位任意阶段，置位后该预留永不被准入（不计数）。
`admitted` 之后保留 attempt（供 turn/end 的 aborted 处理），直到下一轮空闲清理。

## 回合号与计数不变量 «serves: FR-7, FR-8»

1. **预留号** = `roundsInStage + 1`；在 `attempt` 登记时确定。
2. **只有 admission 落库**：`session/event: user/message` 的 `data.id === attempt.messageId` → `phase='admitted'` 且
   `roundsInStage += 1`（**恰好一次**；以 `phase !== 'admitted'` 作幂等闸）。
3. **不计数的形态**：pre-step `reject`、`discarded`、`cancelled`、`stale`、`followup` 抛错 —— `roundsInStage` 不变，
   且下次仍用**同一个** `round` 号。
4. **上限**：`roundsInStage >= getStageConfig(req.status)?.maxRounds ?? 10` → 写终态（FR-8），此后该需求不再起轮。
   判定在 `drive()` 的排队点，每需求至多一次（`phase='paused'` 后不再满足可起轮条件）。

## 台账写入（reasons） «serves: FR-5, FR-7, FR-8, FR-9»

所有写入经 `ReqboardRepository.mutate`（唯一写入口），reason 固定值便于审计：

| reason | 触发 | 改动 |
|--------|------|------|
| `dive-round-admitted` | 回合消息进入 history | `dive.roundsInStage + 1`、`dive.lastActiveAt`、`req.version + 1` |
| `dive-terminal-block` | roundsInStage 达上限 | `dive.phase='paused'`、`dive.pausedReason='round-limit'`、追加一条 comment、`version + 1` |
| `dive-aborted-pause` | 空闲时发现 `attempt.cancelled` | `dive.phase='paused'`、`pausedReason='aborted'`、comment、`version + 1` |
| `dive-disarm` | 检查点失败 / max-tokens / 驱动异常 / 排队失败 | `dive.activation='disarmed'`、`lastActiveAt`、`version + 1` |

## 迁移与兼容 «serves: FR-7, FR-8»

- **无回填**：没有任何写者产出过阶段名态 `phase`（唯一写者 ClearPause 写 `'idle'`），不存在需要转换的历史值。
- **读容错**：`roundLimitFor` 对未知/缺失 `status` 回落 10；`phase` 缺失读出即非 `'active'`，不驱动。
- **类型收窄的编译影响**：`ClearPause.ts` 的 `dive` 字面量缺 `maxRoundsPerStage` 曾是 tsc 噪音；本设计将其标注为可选并同步修正（包级错误数**不得高于改动前基线**）。
- **不 bump `schemaVersion`**：无新增必填字段、无字段删除，旧台账可直接读。
