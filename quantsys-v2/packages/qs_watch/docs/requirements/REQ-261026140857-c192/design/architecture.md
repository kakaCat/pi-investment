---
title: 账户级交易计划统一与数据库化重构 · 架构设计
status: draft
owner: PI Investment
reviewers: 用户（最终决策人）
prd: ../requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
created: 2026-10-26
updated: 2026-10-26
---

# 账户级交易计划统一与数据库化重构 · 架构设计

## 1. 摘要

本设计将现有两套计划链路合并为一个执行事实源：

```text
PortfolioDecisionProvider（只产组合建议）
  → qs_plan（账户级计划、每日 revision、多标 item）
  → PostgreSQL quant schema（唯一事实源）
  → PlanCompiler（item 级规则）
  → WatchEngine → agent 终判 → 成交
  → item 级成交回流、对账、反思和次日滚动
```

`core_plan.json` 不再是生产输入或输出。组合算法保留，但只能以进程内 provider 返回决策数据。`qs_plan` 负责完整计划生命周期，WatchEngine 仍负责监控执行，交易终判和下单边界不变。

## 2. 架构决策

| 编号 | 决策 | 原因 |
|---|---|---|
| AD-1 | 扩展现有 `trading_plans` 体系，不另建第二套主计划表 | 保留历史、规则、成交和反思关联 |
| AD-2 | 主计划、revision、稳定 item、item 决策版本、item 当前状态分离 | 同时满足历史不可变和成交持续更新 |
| AD-3 | 一个账户最多一份当前滚动主计划、一个当前激活 revision | 防止多调度实例产生竞争计划 |
| AD-4 | 组合决策通过端口注入，`qs_plan` 不 import 根应用服务 | 保持包依赖方向，避免再次形成上层反向依赖 |
| AD-5 | 计划生成、激活、成交推进分别使用数据库工作单元 | 消除跨仓储分别提交造成的半完成状态 |
| AD-6 | 外部 agent 唤醒不放入数据库事务 | 避免长事务和分布式事务；唤醒可从持久状态重建 |
| AD-7 | 激活前做决策 preflight，激活后持续 readiness/对账 | 未审核或条件不全的计划不能上线，线上漂移能被发现 |
| AD-8 | 历史成交不改归属，迁移基线进入 item 状态 | 保留审计且保证累计减仓连续 |
| AD-9 | readiness 失败禁止新计划激活和新入场执行，不屏蔽风险退出 | 防止未就绪建仓，同时不削弱止损保护 |
| AD-10 | 生产切换独立授权，测试库与生产变更分离 | 避免文档或代码完成被误当成生产已切换 |

## 3. 模块边界

### 3.1 `qs_plan/domain/plan`

纯 Python、无 I/O：

- `models.py`：`TradingPlan`、`PlanRevision`、`PlanItem`、`ItemDecision`、`ItemState`、`Condition` 等领域值对象。
- `item_state_machine.py`：计划项合法迁移和成交推进判定。
- `state_machine.py`：账户主计划生命周期及由 item 推导整体状态。
- `validation.py`：revision 激活前完整性、权重、条件、有效期和数据时点校验。

### 3.2 `qs_plan/application`

| 服务 | 单一职责 |
|---|---|
| `PlanGenerationService` | 每日幂等生成、组合目标与持仓合并、跨日滚动 |
| `PlanService` | 草稿修改、CAS 生效、暂停/恢复/关闭/归档 |
| `PlanActivationService` | 激活 preflight、规则编译和统一事务 |
| `PlanCompiler` | item 决策版本到期望规则的纯 diff 与编译编排 |
| `PlanReadinessService` | 激活前检查和激活后就绪判定 |
| `PlanReconciliationService` | 规则、成交和实际持仓对账 |
| `PlanProgressService` | 成交接收、item 状态和减仓批次推进 |
| `PlanAggregator` | today/detail 只读视图 |
| `ReflectionPackService` / `PlanReflectionJob` | item 归因材料包、反思和 overdue |
| `TradingPlanJob` | 每日生成、盘前 readiness、盘中/收盘对账任务 |

### 3.3 L1 adapters

- `TradingPlanRepository`：关系查询和持久化，不承载业务流程。
- `TradingPlanUnitOfWork`：向计划、规则、规则变更、成交接收等仓储提供同一 SQLAlchemy session。
- `PortfolioDecisionProvider`：调用重构后的组合算法并返回结构化决策，不写文件。
- `PlanRulePort`：在 UoW session 中读写 `watch_rules`、映射和审计。
- `PlanProgressPort`：连接既有 `FillSyncService` 与 `PlanProgressService`。
- `FillEvent` 扩展 `item_id`；既有交易执行服务只增加归因传递，不新增下单路径。

### 3.4 inbound 与组合根

- `plan_async.py`：参数校验、调用应用服务、错误映射；不得直接编排多次提交。
- `core_plan_async.py`：兼容期数据库只读适配，标记 deprecated。
- `main.py`：注入 provider、UoW、持仓/行情端口，注册新 job，移除旧文件生成 job。
- agent-dh / agent-ts 通过 `trading_plan` 工具消费新契约；外部仓库配置形成部署协同项。

## 4. 核心数据流

### 4.1 每日生成

```text
scheduler
  1. 创建 running 运行记录并提交
  2. 调用 provider、持仓/行情/风险端口（事务外）
  3. 校验 account、trade_date、data_as_of 和风险事实
  4. 开启 UoW，锁定账户主计划行
  5. 若同日 draft/reviewing/approved/active 已存在，返回既有结果
  6. 否则创建 revision + item versions + conditions + states + event
  7. 标记运行成功并提交
  8. 事务后创建/重试 agent 审核唤醒；失败只影响 readiness，不改写生成事实
```

provider 失败时，生成事务不写任何计划内容；任务入口用独立短事务把原运行记录标为失败。崩溃后长期 `running` 的记录由对账任务标记为中断并可重试。

### 4.2 草稿修改与激活

```text
PATCH
  → 基于当前 revision 创建/更新草稿
  → 返回 item diff 和 compile preview（不落规则）

APPLY
  → 锁主计划和草稿 revision
  → 校验 expected_version、修改纪律、decision_audit_id
  → 冻结为 approved，记录 reviewed_by/at，清空 draft 指针
  → 当前 active revision 及其执行状态保持不变

ACTIVATE（一个 UoW）
  → preflight：审核、条件、数据、权重、持仓迁移异常
  → 计算期望规则 diff
  → 写规则、映射、审计
  → 旧 active revision → superseded，新 revision → active
  → 更新主计划指针和事件
  → 一次 COMMIT
```

WatchEngine 只能读取 COMMIT 后的规则，因此不会看到半编译状态。激活重放由版本状态和数据库唯一约束拒绝，不产生第二次副作用。

### 4.3 成交推进

```text
execute_trade（既有）
  → FillEvent(plan_id, item_id, plan_version, trade_id)
  → FillSyncService 既有收敛
  → PlanProgressPort
      1. 开启 UoW
      2. insert fill receipt（trade_id 冲突 = 已处理）
      3. 读取并锁 item state
      4. 更新 filled/remaining/state/last_fill_at
      5. 按累计卖出比例退役对应批次规则
      6. 写 item event 和主计划派生状态
      7. 一次 COMMIT
```

成交主表写入与计划回调不作为分布式事务。回调失败通过对账发现，并可依据 `trade_id` 安全重放；fill receipt 防重复推进。

### 4.4 readiness 与对账

- **激活 preflight**：检查今日 revision、数据新鲜度、审核、条件完整性、权重、迁移异常；失败则没有规则上线。
- **激活后 readiness**：检查激活 revision、实际规则 diff、孤儿规则、未管理持仓、成交回流和对账错误。
- `not_ready` 时禁止新入场，agent 交易工具必须返回阻塞原因；`exit_stop` 等风险退出不得被 readiness 全局开关屏蔽。
- 对账只根据数据库事实更新检查结果，不得在没有证据时自动修复持仓或成交数量。

### 4.5 反思与跨日

盘后按账户当前 revision 聚合材料，保留 item 明细。反思提案只能生成新草稿。次日生成复制未完成 item 的最新决策和状态，新增当日组合建议；已完成 item 保留在历史 revision，不重新激活。

## 5. 事务与外部副作用边界

| 编号 | 同一事务内 | 事务外 | 失败恢复 |
|---|---|---|---|
| TX-1 生成 | revision、items、条件、状态、事件、运行成功 | provider、行情和持仓读取 | 整体回滚，运行记录独立标失败 |
| TX-2 生效/激活 | 版本、规则、映射、审计、指针、事件 | compile preview | 整体回滚，可安全重试 |
| TX-3 成交推进 | receipt、item state、批次规则、事件 | 原始成交落库、FillSync 其他收敛 | 对账发现，按 trade_id 重放 |
| TX-4 readiness | 运行记录和检查结果 | 批量事实读取 | 重新运行，保留历史 |
| TX-5 反思 | 反思报告、版本和事件 | agent 会话、知识消费 | 唤醒失败不推进 due，知识失败不回滚反思 |

不得把 HTTP 调用、agent 唤醒或慢行情查询包进计划写事务。

## 6. 并发与幂等

- 账户主计划行使用 `SELECT ... FOR UPDATE` 串行化同日生成和激活。
- 数据库唯一索引兜底“一账户一当前主计划、一当前激活 revision、一同日草稿”。
- `expected_version` 与主计划 `lock_version` 共同防止过期修改。
- 规则以 `(item_id, role, batch)` 幂等；`rule_id` 全库唯一映射。
- 成交以 `trade_id` 的 fill receipt 幂等。
- 生成 run 使用确定性 `idempotency_key`；周期对账允许保留多次运行历史。

## 7. 文件链路退出

1. 组合算法重构为 `portfolio_decision_service.build_decision()`，删除 `OUT.write_text()`。
2. `CorePlanAdapter` 和 `/api/plans/from-core-plan` 删除，不再做文件到计划的转换。
3. `/api/core-plan` 暂时保留响应兼容，但数据来自 `PlanAggregator`。
4. 策略注册和 candidate-hunt 改为 `trading_plan.today`；删除 `plan_file` 消费提示。
5. 生产源码、配置和 agent 提示全部迁移后，才停止旧调度并移除文件产物。

## 8. 可用性、性能与安全

- today 按 `(account, trade_date)` 和当前指针查询，批量加载 item、状态和规则，禁止 N+1。
- 每日生成允许耗时，但不持有数据库写事务调用外部数据源。
- readiness、规则对账和成交失败均有持久记录、结构化日志和指标。
- API 不返回 DSN、凭据或内部敏感配置；写操作保留 actor 和 decision audit。
- 无新增三方依赖；数据库继续复用 `quant` schema 和现有 SQLAlchemy 引擎。

## 9. 回滚策略

- 代码回滚前，先停止新调度并禁止新 revision 激活。
- 已迁移规则的归属和旧计划映射必须可通过迁移审计还原；不得直接 DROP 新表作为常规回滚。
- 新增表和可空列在代码回滚期保留，避免再次迁移造成历史丢失。
- 生产回滚以“停止新写入、恢复旧消费者、保留新数据”为原则；旧文件链路已经删除后不得通过临时手工 JSON 恢复生产。
- 上线前必须在 `quant_test` 演练生成失败、激活失败、回调丢失、迁移回滚和服务重启。

## 10. 需求追溯

| 需求 | 架构章节 |
|---|---|
| FR-1 | AD-1/4、模块边界、文件链路退出 |
| FR-2 | AD-2/3、domain 与 item 模型 |
| FR-3 | 每日生成、并发与幂等 |
| FR-4 | 草稿修改与激活、TX-2 |
| FR-5 | PlanCompiler、item 级规则 |
| FR-6 | 成交推进、TX-3 |
| FR-7 | readiness 与对账 |
| FR-8 | 反思与跨日 |
| FR-9 | 历史迁移、文件链路退出、回滚 |
| FR-10 | 运行记录、可观测性和审计 |
