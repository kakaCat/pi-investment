---
requirement_refs: [FR-1, FR-3, FR-4, FR-6]
---

# 数据模型（REQ-260927123256-196b）

> 读者：工程 / agent。**本需求不改持久化台账 schema**（`.dsh-data/dsh-reqboard.json` 一字不改）；
> 只改**内存**挂起确认记录的生命周期，并新增一个只读投影。

## 实体关系 <!-- serves: FR-1, FR-3, FR-4 -->

```
┌──────────────────────────┐   (内存，不落盘)
│ PendingConfirmation      │──── 登记：每次 ask_confirm 进入等待前
│  ticket / windowKey      │──── settle：作答 / 取消 / 后台落章
│  requirementId / target  │──── markInterrupted：阻塞被中止
│  kind? / createdAt       │
│  interruptedAt?          │
│  outcome?                │
└──────────┬───────────────┘
           │ 派生（只读，不落盘）
           ▼
┌──────────────────────────┐        ┌─────────────────────────────────┐
│ PendingConfirmView       │        │ RequirementRecord.artifacts[]   │
│ (reqboard_status 投影)    │◄──────│  confirmedAt / confirmedVia     │
└──────────────────────────┘  台账落章判定（targetConfirmedInLedger）
```

## T-1 `PendingConfirmation`（内存，改语义 + 增可选字段） <!-- serves: FR-1, FR-3, FR-4 -->

| 字段 | 类型 | 必填 | 变化 | 说明 |
|---|---|---|---|---|
| `ticket` | string | 是 | 不变 | 前缀 `pc-` + 随机 id |
| `windowKey` | string | 是 | 不变 | 归属窗口；回执不可跨窗口 |
| `requirementId` | string | 是 | 不变 | 目标需求 |
| `target` | `"artifact"|"plan"` | 是 | 不变 | 与 ask_confirm 同语义 |
| `kind` | `ArtifactKind` | 否 | 不变 | `target=artifact` 时的产物种类 |
| `createdAt` | number | 是 | 不变 | 登记时间（ms） |
| `outcome` | `PendingConfirmationOutcome` | 否 | 不变 | 初次 settle 后回填；**缺省 = 未作答** |
| `interruptedAt` | number | 否 | **新增（可选）** | 阻塞等待被 deadline / 取消中止的时刻（ms）；只写首次 |

**语义变化（FR-1/FR-3）**：`register` 不再只服务「超宽限」，而是**每次进入等待前**都执行。
因此：

```
outcome === undefined && interruptedAt === undefined  →  人还没答（阻塞中 或 非阻塞后台等待中）
outcome === undefined && interruptedAt !== undefined  →  等待被中止，弹框可能已消失（FR-4 的「响亮」记录）
outcome !== undefined                                  →  本次确认已有结论（放行）
```

**过期规则（FR-4）**：记录的有效期基准 = `interruptedAt ?? createdAt`，窗口 = `LIMITS.confirmEvidenceWindowMs`（1h）。
即中止记录在被标记后再获得一个完整 TTL，不会因为「登记早于中止 1h」而瞬间失效。

## T-2 `PendingConfirmView`（派生投影，不落盘） <!-- serves: FR-4 -->

| 字段 | 类型 | 来源 |
|---|---|---|
| `ticket` | string | `PendingConfirmation.ticket` |
| `requirement_id` | string | `requirementId` |
| `target` | string | `target` |
| `kind` | string（可选） | `kind` |
| `created_at` | number | `createdAt` |
| `interrupted` | boolean | `interruptedAt !== undefined` |
| `blocked_tools` | string[] | 常量：`['reqboard_submit','reqboard_decompose','reqboard_move','reqboard_task_move']` |
| `recovery` | string | 常量拼接：取回执 ticket + 看板确认两条路径 |

投影由 `livePendingConfirm(deps, windowKey)` 产出——已 settle / 已过期 / **台账已落章**的记录都返回 `undefined`
（陈旧记录不展示、不拦截）。

## T-3 台账落章谓词 `targetConfirmedInLedger`（既有逻辑提取，零行为变化） <!-- serves: FR-4, FR-6 -->

```typescript
function targetConfirmedInLedger(req: RequirementRecord, p: { target: 'artifact' | 'plan'; kind?: string }): boolean {
  if (p.target === 'plan') return req.plan?.approvedAt !== undefined
  const arts = (req.artifacts ?? []).filter(a => a.kind === p.kind)
  return arts.length > 0 && arts.every(a => a.confirmedAt !== undefined)
}
```

- **来源**：`ConfirmReceipt.ts:76-80` 的私有函数 `confirmedInLedger`（逐字提取，**不改判定**）。
- **消费者**：`ConfirmReceipt`（回执）、`pending-guard.livePendingConfirm`（守卫 + status 投影）。
- **为什么提取**：守卫的「解除」与回执的「以台账为准」必须是同一句话，否则会出现
  「回执说已确认、守卫还在拦」或反之的双口径。

## 索引与约束 <!-- serves: FR-1, FR-4 -->

| 约束 | 内容 | 理由 |
|---|---|---|
| ticket 唯一 | `pc-` 前缀 + 全表唯一 | 回执按 ticket 精确定位 |
| 窗口绑定 | `windowKey` 必须等于调用窗口 | 回执不可跨窗口取用 |
| 每窗口权威挂起 | 新的 `ask_confirm` 开始前 `settle` 本窗口既有未作答记录 | 保证「同一时刻一条权威挂起」，重新发起即显式解除 |
| 单次 settle | `outcome` 幂等，保留首次值 | 后台落章与同步落章共用，不互相覆盖 |
| 不回写台账 | 挂起/中止记录**不落盘** | 挂起是短时态，不是业务事实；业务事实以台账 `confirmedAt`/`approvedAt` 为准 |

## 版本兼容与迁移 <!-- serves: FR-4, FR-6 -->

| 问 | 答 |
|---|---|
| 台账要改 schema 吗？ | **不要**。无新表、无新字段、无迁移脚本、无数据回填 |
| 旧数据怎么办？ | 无需处理：挂起记录是内存态，进程重启即清空；台账字段语义不变 |
| 需要灰度开关吗？ | **不需要**：行为差异由 `inline_grace_ms` 显式声明；单进程插件重启即全量生效 |
| 回滚路径？ | 回退插件构建；内存记录不落盘，回滚无残留；`markInterrupted` 只影响内存 |
| 新增持久化？ | **无** |
