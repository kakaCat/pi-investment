---
req_id: REQ-260927121324-abde
title: 节点级 Token 统计写路径收口 · 数据模型
stage: design
requirement_refs: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7, FR-8
---

# 数据模型（REQ-260927121324-abde）

**结论（可证伪，一句话）**：本需求**不新增字段、不改 schemaVersion（保持 8）**，只改「谁写、写不写」；
每条已存在字段的缺失语义（`undefined` = 不知道，`0` = 确实没花）与 delta 产出条件保持并锁死。

## 数据契约总览（不新增字段） <!-- serves: FR-4, FR-5, FR-6, FR-7 -->

| 记录 | 字段 | 本需求是否改契约 | 本需求改什么 |
|---|---|---|---|
| `RequirementRecord` | `tokenUsage.byStage` / `.totals` | 否（沿用） | 需求迁移的 `snap` 补齐后，byStage 更容易有值 |
| `StatusEvent` | `tokenSnapshot?` | 否 | 迁移路径补齐后，事件带上进入快照（或诚实缺省） |
| `ExecutionRecord` | `sessionId?` / `trigger` / `startedAt` / `endedAt?` / `outcome` | 否 | 落库入口收敛到 `openExecution` / `closeExecutions` |
| `ExecutionTokenUsage` | `start?` / `end?` / `delta?` | 否 | 四处产生点开始真实写入 start/end |
| `RequirementTokenView` | `degraded` | 否（形状不变） | 判定从「仅 unavailable」扩为「缺失或不可得」 |
| `REQBOARD_SCHEMA_VERSION` | `8` | **不改** | 无 v9，无迁移脚本 |

> 不新增字段的理由：`tokenSnapshot` / `tokenUsage` 在 REQ-a33899 已进契约，本需求是**写路径回归与漏链**，
> 加字段只会制造第二份真相。

## 字段明细 <!-- serves: FR-1, FR-2, FR-4, FR-5, FR-7 -->

**① StatusEvent.tokenSnapshot（已存在，读写语义收紧）**

| 字段 | 类型 | 必填 | 语义 / 约束 |
|---|---|---|---|
| `sessionId` | `string?` | 否 | 快照所属执行会话；参与「同会话才相减」判定 |
| `seq` | `number?` | 否 | 投影日志序号（判断两次快照可否相减；可选） |
| `at` | `number` | 是 | 快照时刻（ms） |
| `totals` | `TokenBuckets` | 是 | 该会话累计四桶；`source='unavailable'` 时为全 0 占位 |
| `source` | `'projection' | 'unavailable'` | 是 | `projection`=可算；`unavailable`=服务不可得 |

缺失（`tokenSnapshot` 为 `undefined`）与 `unavailable` **都不可算**，读路径同等计入 `degraded`。
**禁止**在缺失时补全 0 快照（会把「不知道」洗成「确实没花」）。

**② ExecutionTokenUsage（已存在，本次首次被真实写入）**

| 字段 | 类型 | 必填 | 语义 / 约束 |
|---|---|---|---|
| `start` | `TokenSnapshot?` | 否 | 开工快照；`undefined` = 该次执行未接入快照 |
| `end` | `TokenSnapshot?` | 否 | 完工 / 中途汇报快照 |
| `delta` | `TokenBuckets?` | 否 | **仅** `start`、`end` 同为 `projection` 且会话不冲突时产出 |
| `costEstimateCny` | `number?` | 否 | 折算金额（本需求不改） |

**③ RequirementTokenUsage（已存在，本需求只补写入频率）**

| 字段 | 类型 | 必填 | 语义 / 约束 |
|---|---|---|---|
| `byStage` | `Partial<Record<StageKey, TokenBuckets>>` | 是 | 离开节点结算的增量聚合；无键 = 该节点无快照 |
| `totals` | `TokenBuckets` | 是 | 恒等于 `Σ byStage`（写路径单点重算） |
| `updatedAt` | `number` | 是 | 最近一次结算时刻 |

**④ ExecutionRecord（已存在，本需求约束其产生方式）**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `id` | `string` | 是 | 由 `deps.ids.execution()` / `newExecutionId()` 生成 |
| `sessionId` | `string?` | 否 | 执行会话；自动链父卡开工可缺省 |
| `trigger` | `'manual' | 'auto'` | 是 | agent/看板 = manual；自动链 = auto |
| `startedAt` | `number` | 是 | 开工时刻 |
| `endedAt` | `number?` | 否 | 收尾时刻；缺省 = 运行中 |
| `outcome` | `'running' | 'succeeded' | 'failed' | 'cancelled'` | 是 | 收尾结果 |
| `tokenUsage` | `ExecutionTokenUsage?` | 否 | 无 = 该次执行无快照（读路径按缺失降级） |

## 不变式 <!-- serves: FR-4, FR-5, FR-7, FR-8 -->

1. **缺失 ≠ 0**：`undefined` 表示「不知道」，`0` 表示「确实没花」；两者在 UI 与读路径必须可区分。
2. **delta 三条件**：`start.source==='projection'` ∧ `end.source==='projection'` ∧ 会话不冲突
   （任一方 `sessionId` 缺省视为兼容）→ 才产出 `delta = subBuckets(end.totals, start.totals)`；
   否则 `delta` 缺省（不写 0、不用单端累计冒充）。负分量由 `subBuckets` 截断为 0。
3. **totals = Σ byStage**：由 `recomputeTotals` 单点维护；读路径禁止另算一份。
4. **节点可算**：`entrySnapshotFor(req, stage)` 取该阶段最近一条**可得**快照；找不到即该段不可算。
5. **只有助手写**：`execution.tokenUsage` 的写点与 `task.executions` 的增改只允许出现在
   `application/internal/token-usage.ts`；`req.status` 的写只允许出现在 `transitionRequirement` 内。

## 读路径判定（degraded，FR-7 唯一变更点） <!-- serves: FR-7 -->

```ts
// application/query/QueryRequirementToken.ts
function hasSnapshotGap(req: RequirementRecord, ledger: Pick<LedgerView, 'tasks'>): boolean {
  // ① 需求侧：任何一条状态事件缺失或不可得 → 该节点进入快照不可知
  for (const e of req.statusHistory ?? []) {
    if (e.tokenSnapshot === undefined || e.tokenSnapshot.source !== 'projection') return true
  }
  // ② 任务侧：运行中要求 start 可得；已闭合要求 start/end 都可得
  for (const t of ledger.tasks) {
    if (t.requirementId !== req.id) continue
    for (const e of t.executions) {
      const startOk = e.tokenUsage?.start?.source === 'projection'
      const endOk = e.tokenUsage?.end?.source === 'projection'
      if (e.endedAt === undefined ? !startOk : !(startOk && endOk)) return true
    }
  }
  return false
}
// degraded = req.tokenUsage === undefined || hasSnapshotGap(req, ledger)
```

- **对「没走过的节点」不判缺失**：只看台账里真实存在的 `statusHistory` 事件与 `executions`，
  不对 `ALL_STAGE_KEYS` 中「从未进入」的节点报警（否则每个需求恒为 degraded，信号失效）。
- **对外形状不变**：`RequirementTokenView.degraded` 仍是 `boolean`；不新增字段、改字段名会被端侧契约测试拦下。
- **既有断言必须保持**：全投影数据（事件与执行两端均 projection）时 `degraded=false`
  （`tests/token-endpoint.test.ts` 首个用例）。

## 版本兼容与迁移 <!-- serves: FR-7, FR-9 -->

- **载入旧台账**：v5~v8 无 token 字段照常载入；读路径可选解析，缺失即「无快照」（`tests/ledger-v6-token.test.ts` v5 用例锁死）。
- **不回填**：不写迁移脚本、不在 load 时就地升级文件版本（读路径不自动迁移是既有纪律）。
- **不新增开关/灰度**：写路径收口无运行时开关；行为变更只影响「修复之后」发生的迁移与执行。
- **跨版本混跑**：旧代码载入新台账时忽略新增快照字段，无破坏；新代码载入旧台账按缺失处理。

## 回滚路径 <!-- serves: FR-7 -->

回滚 = 还原 host 侧代码并重启（`agent-dh/scripts/restart-with-build.sh`）。已写入的 `tokenSnapshot` /
`tokenUsage` 是既有可选字段，无需清理、无需数据修复；回滚后读路径退回旧判定（`degraded` 可能再次漏报），
但**不回退台账结构**，不会产生不可逆损坏。
