# 接口设计（REQ-260927100007-b8ba）

> 每个接口标注 `serves: FR-x`。内部收敛点是 application 层契约；工具接口是 agent 可见面。

## I-1 transitionTask（任务级收敛点） <!-- serves: FR-8 -->

### 签名 <!-- serves: FR-8 -->

```ts
// src/application/internal/task-transition.ts
export interface TaskTransitionOpts {
  at: number
  actor: ActorRef
  reason?: string
  role?: 'parent' | 'subtask' | 'legacy'
  allowIllegalTransition?: boolean
}
export function transitionTask(task: TaskRecord, to: TaskStatus, opts: TaskTransitionOpts): void
```

**调用方**：ExecuteTask / AdvanceChain / failure-handling / http tasks 路由（四处统一）。

### 输入输出与错误语义 <!-- serves: FR-8 -->

- **成功**：就地改 `status/version/updatedAt/updatedBy` + 追加 `statusHistory`；返回 void。
- **失败**：抛错且**不改动任何字段**（禁止半迁移态）；错误码沿用 domain 的
  `invalid_transition` / `human_gate` / `system_gate`。
- **默认**：`role` 缺省 `'legacy'`（既有调用点零改动即保持原行为）。

## I-2 reqboard_task_move <!-- serves: FR-7 -->

**用途**：agent 推进一张任务卡的状态（等价看板按钮的 HTTP 路径）。**调用方**：窗口 agent。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| task_id | string | 是 | 任务 id（t-xxxxxx） |
| to | string | 是 | 目标状态（todo/in_progress/integrating/testing/in_review/done/canceled） |
| reason | string | 否 | 留痕理由 |

**返回**：`{ success, task_id, from, to, status, version }`。
**错误**：非法转移 → `invalid_transition`；人工门越权 → `human_gate`；
任务不属于本窗口绑定需求 → `REQBOARD_NOT_BOUND_TO_WINDOW`。

## I-3 reqboard_move <!-- serves: FR-7,FR-13 -->

**用途**：agent 推进**需求**阶段（补齐缺失的工具面）。**调用方**：窗口 agent。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| requirement_id | string | 否 | 默认本窗口绑定需求 |
| to | string | 是 | 目标状态 |
| reason | string | 否 | 留痕理由 |

**返回**：`{ success, requirement_id, from, to, status }`。
**错误**：`invalid_transition` / `human_gate`（五道人工门 agent 一律不可越过）/
`REQBOARD_ARTIFACT_NOT_CONFIRMED`（产物未确认时拒绝）/ `REQBOARD_TASK_INCOMPLETE`（FR-3 守卫）。

## I-4 reqboard_decompose 返回体契约 <!-- serves: FR-5 -->

- `task_coverage`：**数组**（item 为对象，含 `task_id/task_key/task_title/covers_frs/covers_acceptance`）；
  工具 output schema 与用例返回值对齐。
- `coverage_check`：**对象**（`total_frs/covered_frs/unreceived_clauses/coverage_rate`），保持不变。
- 影响：调用方不再收到 `returned invalid output: value.task_coverage must be an object`。

## I-5 阶段推进守卫的错误契约 <!-- serves: FR-3 -->

**触发**：目标态 `implementing`、计划有任务、台账该需求 0 个未取消任务。
**返回**：拒绝推进，错误码 `REQBOARD_TASK_INCOMPLETE`，消息含：缺口（计划 N 张 / 台账 0 张）
+ 两条修复命令（`reqboard_decompose(requirement_id=…)` 或看板「拆分」）。

## I-6 RTM 触发点与刷新集合 <!-- serves: FR-6,FR-12 -->

| 触发点 | 刷新文件（本需求后） |
|---|---|
| create | `rtm-lifecycle.yml` |
| submit:requirement | `rtm-brainstorming.yml` + `rtm-lifecycle.yml` |
| confirm:artifact / submit:design | `rtm-design.yml` + `rtm-lifecycle.yml` |
| confirm:plan | `rtm-decomposing.yml` + `rtm-implementing.yml` + `rtm-lifecycle.yml` |
| **task:status / task:report** | `rtm-implementing.yml` + `rtm-implementing/<task>.yml` + **`rtm-decomposing.yml`（新增）** |
| **bind（新增）** | `rtm-lifecycle.yml`（窗口绑定变化时） |
| submit:verification | `rtm-accepting.yml` + `rtm-lifecycle.yml` |

## I-7 文字证据路径的推进 <!-- serves: FR-13 -->

**现状**：只落章，返回 note 指向未注册的 `reqboard_move` → 节点永久停在原地。
**目标**：落章后**同一调用内**推进（复用 `confirm-settle` 推进块）；若因人工门/守卫不推进，
必须返回 `advanced:false` + 明确原因 + 可执行命令。

## I-8 确认门挂起守卫 <!-- serves: FR-9 -->

- 挂起（`pending=true`、ticket 未作答）期间，同窗口的写路径工具（`reqboard_submit` / `reqboard_decompose` /
  `reqboard_move` / `reqboard_task_move`）返回 `REQBOARD_CONFIRM_PENDING` 并附取回执命令。
- `reqboard_status` / `reqboard_confirm_receipt` 不受限（否则人无法解除挂起）。
- `pending` 的 `note` 必须写明"收到作答前不得产出下游产物"。

## I-9 reqboard_status 返回体 lossless <!-- serves: FR-10 -->

- 契约：返回体可被 lossless JSON 序列化——**递归不得存在值为 `undefined` 的属性**。
- 现状违规点：`checkRTMHealth` 无失败记录时返回 `last_failure: undefined`（own property）。
- 修法：无记录时**省略该键**（条件展开）。

## I-10 Dive 人工门弹框（受信内部入口） <!-- serves: FR-14 -->

**用途**：Dive 在 `agent/status === 'idle'` 跑批时，若绑定需求处于**人工门**且门未被满足/未被推进，
由 Dive **主动弹框**（而不是只投一条"请 agent 去调 ask_confirm"的消息）。

**调用方**：Dive（`application/dive/session-driver.ts` 的 `driveIdle`）——**仅此一处**。

**接口定义**：

```ts
// application/ports.ts：新增受信内部端口（与工具层的 questions.ask 分开）
export interface GatePromptPort {
  /** 弹一次确认门；返回人是否点了肯定项。幂等由调用方（Dive）按 (需求, 门, 产物指纹) 保证。 */
  prompt(input: {
    windowKey: string
    requirementId: string
    gate: string                 // G1..G5
    kind: 'artifact' | 'plan'    // 确认产物 或 推进确认
    /** kind='artifact' 时必填：要确认的产物 kind */
    artifactKind?: string
    question: string
  }): Promise<{ answered: boolean; affirmative: boolean }>
}
```

**触发条件**（两条，互斥）：

| 分支 | 条件 | 弹什么 |
|---|---|---|
| (a) 门未满足 | 门 `requiredKind` 的产物**已登记未确认** | 「确认产物」框 |
| (b) 门已满足未推进 | 该产物**已确认**但状态未动（`advanceTargetFor(status)` 可达） | 「推进确认」框（肯定项 = 执行该 human-only 转移） |

**幂等与防刷屏**：

- 同 `(requirementId, gate, artifactFingerprint)` 在**一次等待内**只弹一次；
- **跨回合可再弹**：冷却 ≥ 5 分钟、上限 2 次；到顶写台账 comment 并停手（响亮，不静默）。

**认证例外（安全性说明）**：工具层 `requireLiveDriver` 要求 `agent.status === 'running'` 且
`currentInitiator() === agent`；Dive 跑在 **idle**，必然不满足。故本入口**只对 Dive 开放**，
不经工具层认证——但它**只发起弹框**，不代替人做决定：肯定项仍由 `actor=human` 走
`transitionRequirement`（五道人工门的 `human_gate` 判定不变）。

**错误语义**：弹框通道不可用 → 返回 `{answered:false}` 并**降级为投递消息**（保留现行"提醒 agent"路径）；
**绝不**因为无法弹框而替代人推进。

**兼容性**：`GatePromptPort` 未装配（测试/降级）→ Dive 行为与改动前逐字一致（仍只投提醒消息）。
