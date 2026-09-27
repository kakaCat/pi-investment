# 数据模型（REQ-260927100007-b8ba）

> 本需求**不新增台账字段、不升 schemaVersion、不做数据迁移**。本文件只登记读写了哪些既有字段。

## 1. 不变量 <!-- serves: FR-1,FR-5,FR-8,FR-13 -->

- `RequirementRecord` / `TaskRecord` 的字段集合不变 → 无需迁移脚本、无需版本升级。
- 旧记录（缺可选字段）读出即旧行为；收敛点对可选字段做防御性初始化。
- `task_coverage` 的取值形状本来就是数组，本需求只把**工具声明**改成一致（契约修正，非数据变更）。

## 2. 需求侧既有字段 <!-- serves: FR-1,FR-2,FR-3,FR-13 -->

| 字段 | 本需求语义 |
|---|---|
| `status` | 只经 `transitionRequirement` 改；落库/守卫失败时**保持不变** |
| `plan.tasks[]` | 批准后落库的**唯一**内容来源；`length > 0` 是守卫触发条件 |
| `plan.approvedAt` | 落库前置（`planApproved`） |
| `autoRun` | 仅在落库成功后置 true |
| `advance.pausedReason` | 落库/推进失败时写入（响亮化锚点） |
| `artifacts[].confirmedAt/confirmedVia/confirmedEvidence` | 落章三元组；证据路径写 `session` + 答复原文 |
| `sourceSessionId` | 窗口侧绑定的需求侧锚点，RTM 投影来源 |

## 3. 任务侧既有字段与收敛点写入语义 <!-- serves: FR-7,FR-8 -->

| 字段 | 收敛点写入语义 |
|---|---|
| `status` | 只由 `transitionTask` 改 |
| `version` / `updatedAt` / `updatedBy` | 成功流转时一并更新；**拒绝时不变** |
| `statusHistory[]` | 成功流转追加一条 |
| `claimedAt` / `claimedBy` | 进入执行段时写、离开时清（调用方负责） |
| `executions[]` | 开工开段、离开 `in_progress` 结算（调用方负责） |
| `attempt` / `revisions[]` | 失败回退 / 重开时追加（append-only） |
| `requirementRefs` | 落库时写入；条款门禁第二来源经 `decomposition.md` 对照表 |

## 4. RTM 投影字段 <!-- serves: FR-6,FR-12 -->

- `rtm-lifecycle.yml` 的 `requirement.source_session`：由 `lifecycle-generator` 写入台账 `sourceSessionId`；
  现状**无生产读取方**，需按决策补齐消费者或如实标注。
- 刷新集合：`task:status`/`task:report` 补 `rtm-decomposing.yml`；新增 `bind` 触发点刷新 `rtm-lifecycle.yml`。
- 窗口侧锚点（triage `resultRequirementId`）当前**未投影**；是否新增投影字段由三项决策之一决定。

## 5. 兼容与回滚 <!-- serves: FR-4,FR-12 -->

- 本需求全部为**行为修正**，无数据形态变更 → 回滚 = 回滚代码，台账无副作用。
- 存量需求（无 `artifacts`）在全部相关闸门/守卫处**豁免**（沿用既有 `isLegacy` 口径）。
- 74 个无 RTM 文件的历史需求：不回填；新逻辑对"无 RTM"保持"不拦截"边界语义。
