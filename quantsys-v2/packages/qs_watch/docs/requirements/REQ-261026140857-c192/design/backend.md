---
title: 账户级交易计划统一与数据库化重构 · 后端实现设计
status: draft
owner: PI Investment
reviewers: 用户（最终决策人）
prd: ../requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
created: 2026-10-26
updated: 2026-10-26
---

# 账户级交易计划统一与数据库化重构 · 后端实现设计

## 1. 实现总览

后端实现分为四条主线：

1. 组合算法无文件化，并通过 provider 注入 `qs_plan`。
2. 账户主计划、每日 revision、稳定 item 和独立执行状态落库。
3. 生成、激活、成交推进使用显式 UnitOfWork。
4. readiness、对账和反思将执行结果送入次日 revision。

数据字段以 `data-model.md` 为唯一权威，HTTP 字段以 `interfaces.md` 为唯一权威。

## 2. 领域模型与状态

### 2.1 主计划状态

新 `plan_kind='account'` 主计划使用：

```text
draft → reviewing → active ↔ paused → closed → archived
```

- `holding/closing` 不再作为新账户主计划的直接持仓状态，而由 item 聚合派生到 today 视图。
- 旧 `legacy_single` 行保留原状态，仅用于历史读取和迁移。
- 有未关闭持仓 item 时关闭主计划必须提供持仓处置方案。
- 有反思 overdue 时仍禁止归档。

### 2.2 revision 状态

```text
draft → reviewing → approved → active → superseded
  └──────────────→ rejected
```

- 每日生成初始为 `draft`；agent 开始审核可转 `reviewing`。
- PATCH 只能修改 `draft/reviewing`，修改后可回到 `reviewing`。
- APPLY 校验修改纪律和版本后冻结为 `approved`，写 `reviewed_by/at`。
- ACTIVATE 只允许 `approved → active`；旧 active 同时转 `superseded`。
- `approved` 尚未上线，不改变当前 active revision 或规则。
- `active/superseded/rejected` 的决策内容不可改；新修改必须创建新 revision。

### 2.3 item 状态

```text
planned → ready → entering → holding → reducing → exited
    └──────────────→ cancelled
```

- `buy` 审核完整后可为 `ready`，买入成交后为 `holding`。
- `sell` 且已有持仓时按剩余量进入 `reducing/exited`。
- `hold` 有真实持仓时为 `holding`，无持仓时必须对账异常，不得伪造 holding。
- `avoid` 只能为 `planned/cancelled`，不得编译入场规则。
- `exited/cancelled` 是终态；再次交易同标的需新的决策 revision，是否复用未关闭 item 由关闭标记决定。

## 3. 服务清单

| 编号 | 服务/端口 | 职责 |
|---|---|---|
| S-1 | `PortfolioDecisionProvider` | 返回组合目标、风险预算、数据时点和证据，不写文件 |
| S-2 | `PlanGenerationService` | 每日幂等生成、持仓合并、跨日滚动 |
| S-3 | `PlanService` | 主计划生命周期、PATCH/APPLY、修改纪律 |
| S-4 | `PlanActivationService` | preflight、编译、激活统一事务 |
| S-5 | `PlanCompiler` | item revision → 期望规则集与 diff |
| S-6 | `PlanReadinessService` | preflight 与运行时就绪原因 |
| S-7 | `PlanReconciliationService` | 规则、成交和实际持仓对账 |
| S-8 | `PlanProgressService` | 成交接收、item 状态和减仓批次推进 |
| S-9 | `PlanAggregator` | today/detail 批量只读聚合 |
| S-10 | `ReflectionPackService` | 账户 revision + item 归因材料包 |
| S-11 | `TradingPlanUnitOfWork` | 同 session 事务、锁和提交/回滚 |
| S-12 | `TradingPlanRepository` | 关系查询和持久化，不包含业务编排 |
| S-13 | `TradingPlanJob` | 每日生成、readiness、对账和反思调度入口 |
| S-14 | `LegacyPlanMigrator` | 预检、按账户迁移、基线与映射审计 |

## 4. 内部接口

### 4.1 组合决策端口

```python
class PortfolioDecisionProvider(Protocol):
    def build(self, *, account: str, trade_date: date) -> PortfolioDecision: ...

@dataclass(frozen=True)
class PortfolioDecision:
    account: str
    trade_date: date
    data_as_of: datetime
    targets: tuple[TargetAllocation, ...]
    market_gate: dict
    risk_budget: dict
    evidence: dict
```

- provider 不返回 file path，也不负责创建 `TradingPlan`。
- 重构 `core_plan_service.generate()` 时保留计算公式，将文件写、控制台输出和快照读取移出核心计算。
- `data_as_of` 来自行情事实，不等于服务当前时间。

### 4.2 每日生成

```python
class PlanGenerationService:
    def generate(self, *, account: str, trade_date: date,
                 actor: str, idempotency_key: str) -> GenerationResult: ...
```

算法：

1. 创建 `running` run；外部事实读取失败时独立标记 `failed`。
2. 校验 decision 的账户和交易日，校验 `data_as_of` 符合当前交易日数据政策。
3. 读取真实持仓和已有主计划，形成 `target_by_symbol`、`position_by_symbol`、`open_item_by_symbol`。
4. 开启 UoW 并锁主计划；不存在则创建账户主计划。
5. 同日已有 `draft/reviewing/approved/active` revision 时返回 `existing=True`。
6. 确定新 revision.version 为当前最大版本 +1，写 `trade_date/data_as_of/risk_budget`。
7. 对所有目标与持仓的并集生成 item 决策：
   - 新候选：`buy`，目标权重来自 provider，入场条件由审核补全。
   - 已有持仓且在目标中：复用 open item，延续退出条件和状态，默认 `hold`。
   - 已有持仓但不在目标中：复用 open item，生成待审核 `hold` 管理项，不自动产生 sell。
   - provider 明确给出退出建议时也只能形成待审核 `sell` 决策，不直接下单。
8. 复制未完成 item 的必要执行状态；新 item 初始化 `planned`。
9. 写 conditions、event、run 成功结果并提交。
10. 事务后请求 agent 审核；唤醒失败记录 `review_pending`，不删除已生成 revision。

### 4.3 PATCH 与 APPLY

```python
patch(plan_id, expected_version, item_patches, reason, actor, decision_audit_id)
apply(plan_id, expected_version, actor, decision_audit_id, reason, hypothesis)
```

- PATCH 基于当前 revision 创建草稿，或修改同日现有草稿。
- `item_patches` 必须按 `item_id` 寻址；禁止用数组下标识别标的。
- 每次 PATCH 返回 item diff、规则 preview 和新的 `lock_version`。
- APPLY 锁主计划与 revision，检查版本和修改纪律；通过后 `reviewing/draft → approved`。
- APPLY 不清空或覆盖当前 active revision，不编译线上规则。

### 4.4 激活工作单元

```python
with uow:
    plan = uow.plans.lock_for_update(plan_id)
    revision = uow.versions.lock_approved(plan_id, expected_version)
    readiness.preflight(plan, revision, uow=uow)
    diff = compiler.diff(revision, managed_rules=uow.rules.list_for_plan(plan_id))
    compiler.apply(diff, uow=uow)
    uow.versions.supersede_current(plan_id, exclude=revision.id)
    uow.versions.mark_active(revision.id)
    uow.plans.set_current_revision(plan_id, revision.id)
    uow.events.record_activation(...)
    uow.commit()
```

- 任一异常执行 rollback；路由不再做二次补偿。
- `PlanRulePort` 和 `WatchRuleChangeRepository` 必须接收 UoW session，不得在方法内 commit/close。
- 审计写入是事务必填步骤，不得捕获后仅记日志并继续成功。
- `PlanCompiler` 不负责 HTTP，不直接建立 session。
- 入场条件已完整的 buy/add 项在激活事务内由 `planned` 推进到 `ready`，并把 item 清单写入激活审计；仍缺条件的项不得借成交直接跳到 holding。

### 4.5 item 编译规则

期望键：

```text
(item_id, role, batch)
```

映射：

- `entry + conditions` → `role=entry, intent=entry`。
- `stop_loss` → `role=stop_loss, intent=exit_stop`。
- `reduce` → `role=reduce, intent=exit_take_profit`，保留 batch。
- `avoid` 或入场 pending → 不生成 entry；持仓管理项仍按有效退出条件生成风险规则。
- 每条 payload 写 `plan_id/item_id/plan_version`，position_state 来自真实持仓。
- diff 比较 conditions、action_params、interval、enabled 和归因版本；`position_state` 与生命周期写入的 context 附注属于运行时状态，不单独构成 drift。无持仓的退出规则允许被生命周期正常停用；有持仓时退出规则停用仍报 drift。

### 4.6 成交推进

```python
on_fill(fill: FillEvent) -> ProgressResult
```

1. 新链路要求 `plan_id/item_id/plan_version/trade_id` 全存在，否则 `rejected`。计划买入在执行前还必须提供 A/B 级 `signal_grade` 和事前 `decision_audit_id`，复核当前激活版本与 readiness；计划卖出不受新入场禁令影响。买入项必须有正整数 `execution_batch` 和 `entry_valid_until`；同日禁止跨批，不同批次至少间隔 7 天。`price_break/above` 还必须有非负 `max_chase_pct` 和有效决策价，超过阈值允许幅度即拒单；缺失这些字段时不默认放行。
2. UoW 内先插 `trading_plan_fill_receipts`；主键冲突返回 `duplicate=True`。
3. 锁 item state，校验 fill 的 plan/item 与数据库一致。
4. 从持仓端口读取 remaining；读失败则回滚 receipt 并返回 `degraded`，等待重试。
5. 更新数量、状态和事件；卖出按以下口径计算：

   ```text
   total_sold = initial_sold_qty + 当前 item 已接收 SELL 数量
   sold_ratio = total_sold / (total_sold + remaining_qty)
   ```

6. 按累计比例退役已经完成的 reduce 批次；已退役批次跳过，不重复写成功事件。
7. 主计划保持运行，除非所有 item 均终态且用户发起关闭。
8. 提交后返回 item state 和 sold_ratio；异常由对账任务发现并允许按 trade_id 重放。

### 4.7 readiness 与对账

`PlanReadinessService.evaluate(account, trade_date, stage)` 返回：

```python
ReadinessResult(ready: bool, reasons: tuple[ReadinessReason, ...], checked_at: datetime)
```

`stage='activation'` 检查：

- `REVISION_MISSING`、`DATA_STALE`、`REVIEW_REQUIRED`、`ENTRY_INCOMPLETE`、`EXIT_INCOMPLETE`、`WEIGHT_INVALID`、`MIGRATION_REQUIRED`。

`stage='runtime'` 额外检查：

- `RULE_MISSING`、`RULE_ORPHAN`、`RULE_VERSION_MISMATCH`、`RULE_DRIFT`。
- `POSITION_UNMANAGED`、`POSITION_MISMATCH`、`FILL_PROGRESS_MISSING`、`GENERATION_FAILED`。

对账规则：

- 计划期望规则与实际规则双向 diff，不能只查“期望规则存在”。
- 实际正持仓必须有未关闭 item；无持仓 item 不得长期保持 holding。实际已有持仓但 item 仍为 planned/ready 且没有成交回写时，同样报 `POSITION_MISMATCH`，不得以 ready=true 掩盖断链。
- 已存在成交但没有 fill receipt 的，标 `FILL_PROGRESS_MISSING`，通过重放修复。
- 数量不一致只报告事实和修复建议，不自动篡改成交历史。

### 4.8 today、反思与次日

- today 一次查主计划和 revision，再批量查 item versions/states/rules/run 结果，避免 N+1。
- `ready=false` 仍返回 HTTP 200 和完整原因；账户参数缺失或内部未知错误才返回 4xx/5xx。
- 材料包头部使用账户 revision，成交和修改按 item 分组；缺数据段标 `missing`。
- 反思报告账户级 `item_id=NULL`，item 级可关联 item。
- 次日生成读取最新 active/superseded 决策、item state 和最近反思，不读取 JSON 快照恢复状态。

## 5. 调度实现

| Job | 行为 | 成功条件 |
|---|---|---|
| `trading_plan_generate_daily` | 每交易日盘前生成 draft | revision 和全部 item 完整落库；不是“已激活” |
| `trading_plan_readiness_premarket` | 审核后 readiness/对账 | ready 或明确 not_ready，均写运行结果 |
| `trading_plan_reconcile_intraday` | 规则、成交和持仓对账 | 检查完成；发现差异不能静默 |
| `trading_plan_reconcile_close` | 收盘最终对账 | 留下当日收盘对账结果 |
| `plan_reflect_daily/weekly` | 现有任务改为账户 revision + item 材料包 | 材料包和唤醒状态真实可查 |

- 交易日判断复用 `TradingDayGuard`，周度反思不套交易日守卫。
- 外部唤醒在数据库提交后执行；失败可由后续任务根据 `review_pending` 重试。
- 测试环境使用 fake waker，禁止真实外呼。

## 6. 组合根与文件调整

主要实现位置：

- 新增：`qs_plan/application/{plan_generation_service,plan_activation_service,plan_readiness_service,plan_reconciliation_service,plan_progress_service,plan_job}.py`。
- 新增：`qs_plan/application/ports.py` 和领域模型/状态机文件。
- 修改：`plan_service.py`、`plan_compiler.py`、`plan_aggregator.py`、`reflection_pack_service.py`、`reflection_job.py`。
- 新增/重构：L1 `TradingPlanUnitOfWork`、repository、provider 和 progress/rule ports。
- 修改：`FillSyncService` 与 `FillEvent` 归因传递，既有下单路径不变。
- 修改：FastAPI `main.py` 注入所有端口，禁止应用服务自行 import 根 `core_plan_service`。
- 将 `application/services/core_plan_service.py` 重构为 `portfolio_decision_service.py`，保留算法、删除文件副作用。
- 删除 `CorePlanAdapter` 及其生产路由；相关测试由生成与迁移测试取代。

## 7. 错误处理与恢复

| 场景 | 返回/记录 | 恢复方式 |
|---|---|---|
| provider/行情失败 | run=failed，`PLAN_DATA_STALE` 或数据源错误 | 修复数据后重跑同一幂等键 |
| 激活任一步失败 | 整体回滚，API 返回原始领域错误 | 修复后重试 approved revision |
| agent 审核唤醒失败 | review_pending、ready=false | 后续任务从数据库重建唤醒 |
| 成交持仓读取失败 | degraded，不提交 receipt | 同一 FillEvent 重试 |
| 成交回调遗漏 | 对账 `FILL_PROGRESS_MISSING` | 按原始 trade_id 重放 |
| 进程崩溃留下 running | 超时标记 interrupted/failed | 新建 attempt，保留旧 run |
| 迁移账户异常 | 该账户回滚并列异常清单 | 人工核实后只重跑该账户 |

## 8. 实施顺序

1. 数据迁移与 ORM、关系仓储和迁移测试。
2. 领域模型、每日生成与多标状态机。
3. UoW、编译和激活事务。
4. item 成交推进、readiness 与对账。
5. API、调度、反思和 agent 契约。
6. 文件消费者迁移、旧链路删除和全链路验收。

每一步必须保持测试可运行，不允许先删旧链路再长时间留下不可用的中间状态。
