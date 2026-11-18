---
title: 账户级交易计划统一与数据库化重构 · 数据模型设计
status: draft
owner: PI Investment
reviewers: 用户（最终决策人）
prd: ../requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
created: 2026-10-26
updated: 2026-10-26
---

# 账户级交易计划统一与数据库化重构 · 数据模型设计

## 1. 摘要

本设计扩展现有五表，新增六类关系对象：稳定计划项、计划项版本、计划项执行状态、条件、运行记录和成交接收记录。`watch_rules` 与 `simulation_trades` 增加 `item_id`，实现精确归因。

核心不变量：

1. 已激活 revision 及其 item 决策不可变。
2. 当前执行状态独立更新，不覆盖历史决策。
3. 一个账户最多一份当前滚动主计划、一个当前激活 revision。
4. 一个 item 的同一角色/批次最多一条托管规则映射。
5. 一个 `trade_id` 最多推进一个 item 一次。
6. 历史成交不改写；旧计划减仓通过迁移基线延续。

## 2. ER 关系

```text
trading_plans 1───n trading_plan_versions
             1───n trading_plan_items 1───1 trading_plan_item_states
             │                         1───n trading_plan_item_versions
             │                         1───n trading_plan_fill_receipts
             │                                      │
trading_plan_versions 1───n item_versions 1───n trading_plan_conditions
             │                                      │
             └──── plan_version 归因 ───────────────┤
                                                   ▼
trading_plans/items ─── trading_plan_rules ─── watch_rules
trading_plans/items ─── simulation_trades（新成交）
trading_plans/items ─── trading_plan_events / plan_reflections
trading_plans ─── trading_plan_runs
```

## 3. 现有表扩展

### 3.1 `trading_plans`

保留现有列；新执行链路不再写 `spec/draft_spec`，旧列仅用于历史兼容。

| 新列 | 类型 | 空值/默认 | 说明 |
|---|---|---|---|
| `plan_kind` | varchar(16) | `legacy_single` | 新账户主计划为 `account` |
| `current_revision_id` | integer NULL | NULL | 当前生效 revision；延迟加 FK |
| `draft_revision_id` | integer NULL | NULL | 当前草稿 revision；延迟加 FK |
| `migrated_to_plan_id` | integer NULL | NULL | 旧计划迁移目标，自引用 FK |
| `lock_version` | integer | 1 | 主计划并发控制，每次写指针 +1 |

约束与索引：

- `plan_kind IN ('legacy_single','account')`。
- 新 `account` 行不再使用旧 `horizon/spec` 表达执行事实；迁移必须将这两列调整为可空，新账户主计划写入 NULL，旧行原值保留。
- 禁止为了绕过旧 NOT NULL 定义给新账户主计划写 `horizon='day'` 或 `spec='{}'` 等占位事实。
- 部分唯一索引：`account`，条件为 `plan_kind='account' AND status NOT IN ('closed','archived')`。
- `migrated_to_plan_id` 指向 `trading_plans.id`，`ON DELETE SET NULL`。
- 两个 revision 指针在版本表创建后添加 FK，避免循环建表问题。

### 3.2 `trading_plan_versions`

现有 `(plan_id, version)` 唯一约束保留。新增：

| 新列 | 类型 | 说明 |
|---|---|---|
| `trade_date` | date NULL | 计划所属交易日；旧行可为空 |
| `status` | varchar(16) NULL | `draft/reviewing/approved/active/superseded/rejected` |
| `data_as_of` | timestamptz NULL | 输入行情事实时点 |
| `market_gate` | jsonb NULL | 市场闸只读快照 |
| `risk_budget` | jsonb NULL | 总敞口、现金和亏损限制快照 |
| `generation_key` | varchar(120) NULL | 初始每日生成幂等键 |
| `reviewed_by` | varchar(50) NULL | 审核人/agent |
| `reviewed_at` | timestamptz NULL | 审核时间 |
| `activated_at` | timestamptz NULL | 激活时间 |
| `superseded_at` | timestamptz NULL | 被新 revision 取代时间 |

变更与约束：

- 新 revision 的 `spec` 为 NULL；迁移需将旧 `spec` 列调整为可空。新代码不读它作为执行事实。
- `status` 非空时应用 CHECK 限定上述值。
- 部分唯一索引：`(plan_id, trade_date)`，条件为 `status IN ('draft','reviewing','approved')`。
- 部分唯一索引：`plan_id`，条件为 `status='active'`，保证一个当前激活 revision。
- `(plan_id, trade_date, status)` 普通索引支撑 today。
- `generation_key` 在初始生成行上唯一；人工后续 revision 使用 NULL。

### 3.3 `trading_plan_rules`

| 新列 | 类型 | 说明 |
|---|---|---|
| `item_id` | integer NULL | → `trading_plan_items.id` |
| `plan_version` | integer NULL | 编译时 revision.version |

- 旧联合主键迁移期保留。
- 新规则必须同时具有 `item_id` 和 `plan_version`。
- 部分唯一索引：`(item_id, role, batch) WHERE item_id IS NOT NULL`。
- `rule_id` 既有唯一约束不变。
- `item_id ON DELETE SET NULL` 仅适用于历史保留；正常运行禁止删除有计划引用的 item。

### 3.4 事件、反思与执行表

- `trading_plan_events` 增加 `item_id integer NULL`、`plan_version integer NULL`，增加 `(item_id, created_at)` 索引。
- `plan_reflections` 增加 `item_id integer NULL`、`plan_version integer NULL`；账户级反思 `item_id=NULL`。
- `watch_rules` 增加 `item_id integer NULL` 及索引。
- `simulation_trades` 增加 `item_id integer NULL` 及 `(item_id, trade_date)` 索引。
- 上述归因 FK 均采用 `ON DELETE SET NULL`，防止误删计划导致执行历史丢失。

## 4. 新表

### 4.1 `trading_plan_items`

稳定计划项身份，跨 revision 复用。

| 列 | 类型 | 约束/说明 |
|---|---|---|
| `id` | serial PK | 对外 `item_id` |
| `plan_id` | integer | FK → plans，非空 |
| `symbol` | varchar(20) | 非空，统一完整证券代码 |
| `legacy_plan_id` | integer NULL | FK → 旧 plans，记录迁移来源 |
| `opened_at` | timestamptz | 非空 |
| `closed_at` | timestamptz NULL | 永久结束后关闭 |

- 部分唯一索引：`(plan_id, symbol) WHERE closed_at IS NULL`。
- 普通索引：`(plan_id, closed_at)`、`legacy_plan_id`。
- 同一标的新决策优先复用未关闭 item；不得同时建立冲突的 buy/hold/sell 项。

### 4.2 `trading_plan_item_versions`

每个 revision 中 item 的决策快照。

| 列 | 类型 | 约束/说明 |
|---|---|---|
| `id` | serial PK | 条件表父键 |
| `revision_id` | integer | FK → versions，非空 |
| `item_id` | integer | FK → items，非空 |
| `action` | varchar(12) | `buy/sell/hold/avoid` |
| `horizon` | varchar(16) | `day/swing` |
| `target_weight` | numeric(9,6) NULL | 0～1 |
| `max_weight` | numeric(9,6) NULL | 0～1 |
| `target_qty` | bigint NULL | ≥0 |
| `execution_batch` | integer NULL | 正整数执行批次；计划买入必填，缺失不默认放行 |
| `max_chase_pct` | numeric(6,3) NULL | 相对 price_break 阈值的最大追高幅度（%），由审核明确填写 |
| `entry_combinator` | varchar(8) | `all_of/any_of`，默认 `all_of` |
| `thesis` | text | 投资假设 |
| `invalidation` | text | 逻辑失效说明 |
| `entry_valid_until` | timestamptz NULL | 入场有效期 |
| `evidence` | jsonb | 非核心证据快照 |
| `created_at` | timestamptz | 非空 |

- `UNIQUE(revision_id, item_id)`。
- `revision_id` 与 `item_id` 必须属于同一 `plan_id`，由仓储在写入时锁定验证。
- 激活前应用层校验 buy/sell 的必要条件与权重；数据库负责值域和关联完整性。

### 4.3 `trading_plan_conditions`

| 列 | 类型 | 约束/说明 |
|---|---|---|
| `id` | serial PK | — |
| `item_version_id` | integer | FK → item_versions，非空 |
| `role` | varchar(16) | `entry/stop_loss/reduce` |
| `batch` | integer | 默认 0，≥0 |
| `sequence` | integer | 默认 0，≥0 |
| `condition_type` | varchar(40) | 复用 WatchEngine DSL 类型 |
| `params` | jsonb | 条件参数，不保存关联和状态 |
| `created_at` | timestamptz | 非空 |

- `UNIQUE(item_version_id, role, batch, sequence)`。
- `role/batch` 是规则幂等语义的一部分。
- 止损价格、减仓比例等关键参数由领域校验，不允许任意 JSON 绕过。

### 4.4 `trading_plan_item_states`

| 列 | 类型 | 约束/说明 |
|---|---|---|
| `item_id` | integer PK/FK | 一对一当前状态 |
| `state` | varchar(16) | 七种 item 状态 |
| `target_qty` | bigint NULL | 当前执行目标快照 |
| `filled_qty` | bigint | 默认 0，≥0 |
| `remaining_qty` | bigint NULL | 当前真实剩余，≥0 |
| `initial_position_qty` | bigint | 迁移持仓基线，默认 0 |
| `initial_sold_qty` | bigint | 迁移累计卖出基线，默认 0 |
| `last_fill_at` | timestamptz NULL | 最近成交 |
| `lock_version` | integer | 默认 1，CAS |
| `updated_at` | timestamptz | 非空 |

- 状态 CHECK：`planned/ready/entering/holding/reducing/exited/cancelled`。
- 数量字段均非负；数量真相由成交和持仓对账更新，不由用户直接编辑。
- 累计卖出：`initial_sold_qty + 当前 item 已接收 SELL 成交`。

### 4.5 `trading_plan_runs`

| 列 | 类型 | 约束/说明 |
|---|---|---|
| `id` | bigserial PK | — |
| `account` | varchar(60) | 非空 |
| `trade_date` | date | 非空 |
| `run_kind` | varchar(24) | `generate/review/readiness/reconcile/migrate` |
| `idempotency_key` | varchar(160) NULL | 初始生成等幂等操作的逻辑键 |
| `attempt` | integer | 默认 1，≥1；每次重试递增 |
| `plan_id` | integer NULL | 关联主计划 |
| `revision_id` | integer NULL | 关联 revision |
| `status` | varchar(16) | `running/succeeded/failed/degraded/interrupted` |
| `reasons` | jsonb | 结构化阻塞原因数组 |
| `error` | text NULL | 已脱敏错误摘要 |
| `started_at` / `finished_at` | timestamptz | 运行时间 |

- `UNIQUE(idempotency_key, attempt)`；重试新增 attempt，保留首次失败历史。
- 同一逻辑键的并发 attempt=1 由该唯一键兜底，业务层将冲突转为查询既有结果。
- 周期 readiness/reconcile 的 idempotency_key 使用 NULL，保留每次历史。
- `(account, trade_date, run_kind, started_at)` 索引。
- 长时 running 由对账任务按超时判定中断，不得自动视为成功。

### 4.6 `trading_plan_fill_receipts`

| 列 | 类型 | 约束/说明 |
|---|---|---|
| `trade_id` | varchar(120) PK | 来自全局 simulation trade id |
| `plan_id` | integer | 非空 |
| `item_id` | integer | 非空 |
| `plan_version` | integer | 非空 |
| `side` | varchar(4) | `buy/sell` |
| `qty` | bigint | >0 |
| `remaining_qty` | bigint NULL | 处理后的持仓事实 |
| `received_at` | timestamptz | 非空 |

- 与 `simulation_trades.item_id/plan_version` 一致，由写入端口保证。
- 插入冲突表示该成交已推进，直接返回既有结果，不重复改状态或规则。
- 表是推进幂等凭证，不替代原始成交表。

## 5. 关键查询与索引

| 场景 | 查询方式 |
|---|---|
| 今日计划 | 账户当前主计划 → current revision → 批量 items/item versions/states |
| 同日幂等生成 | 锁主计划行 + 同日 draft/reviewing/approved 部分唯一索引 |
| 当前激活版本 | `versions.plan_id + status=active` 部分唯一索引 |
| item 规则 diff | `watch_rules.item_id` + `trading_plan_rules.item_id/role/batch` |
| item 成交历史 | `simulation_trades(item_id, trade_date)` |
| 运行故障查询 | `runs(account, trade_date, run_kind, started_at)` |
| 历史迁移追踪 | `items.legacy_plan_id`、`plans.migrated_to_plan_id`、事件 |

## 6. 旧数据迁移算法

### 6.1 预检

按账户输出：旧计划数、状态分布、托管规则数、成交数、当前持仓和无法核实项。以下情况进入人工异常清单，不自动迁移：

- 有持仓但账户/标的归属不唯一。
- 旧成交或持仓数量读取失败。
- 同一规则存在多个无法解释的映射。
- 旧计划数据缺 symbol 或版本关系损坏。

### 6.2 迁移步骤

1. 锁待迁移账户的旧计划和主计划集合。
2. 创建一个 `plan_kind='account'` 主计划及迁移 revision。
3. 每个未归档旧计划转为一个带 `legacy_plan_id` 的 item；创建 item version、conditions 和 state。
4. 从旧成交汇总 SELL，从当前持仓读取剩余数量，写 `initial_position_qty/initial_sold_qty`。
5. 对仍需运行的规则：更新 `watch_rules.plan_id/item_id`，更新映射到新 plan/item/version，写编译迁移审计。
6. 旧计划写 `migrated_to_plan_id` 和 `migrated` 事件，退出新激活查询；旧版本、成交和反思不改写。
7. 对无持仓的纯草稿可迁移为 `planned`；已有持仓项恢复为 `holding/reducing`，由实际数量决定。
8. 每账户独立事务；一个账户失败不破坏其他账户，也不能留下半迁移账户。

### 6.3 减仓连续性

设迁移基线为 `S0=initial_sold_qty`，迁移后新 item 累计 SELL 为 `Sn`，当前剩余为 `R`：

```text
sold_ratio = (S0 + Sn) / (S0 + Sn + R)
```

`R=0` 且累计卖出大于零时比例为 1。不得把旧 `plan_id` 的历史成交直接改写成新 item 来凑比例。

## 7. 迁移文件与回滚

- 新迁移：`20261105d_account_trading_plan.py`；调度声明与数据结构分离。
- 默认 dry-run；只有 `--apply` 写库；支持显式 `--dsn` 指向 `quant_test`。
- 所有 DDL/约束/索引可重复预检，重跑不得重复迁移账户。
- 常规回滚不 DROP 表、不清空新数据；通过迁移映射恢复规则归属并停止新链路。
- 生产迁移前必须备份并验证恢复路径；本轮开发不执行生产迁移。

## 8. 与旧模型的兼容

- 旧 `trading_plans.plan_kind='legacy_single'`，旧仓储只读历史。
- 旧 `spec/draft_spec` 和版本 `spec` 不清空、不作为新执行事实源。
- 旧 `plan_id` 的历史成交和反思继续可查。
- 兼容期新表预检失败时，新写路径必须响亮失败；不得退回写 JSON 文件或旧单标执行。
