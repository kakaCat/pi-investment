---
title: 交易计划与反思闭环 · 数据模型设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: 要创建一个qs_plan里创建/REQ-261021222905-6dff/requirement.md
serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7
created: 2026-10-21
updated: 2026-10-21
---

# 交易计划与反思闭环 · 数据模型设计  serves: FR-1

## 摘要 `serves: FR-1`

- **问题**：计划/版本/规则映射/事件/反思五类数据需要落库契约；既有表需要归因列。
- **方案**：新建 5 表（trading_plans / trading_plan_versions / trading_plan_rules / trading_plan_events / plan_reflections）；既有表加可空列（watch_rules.plan_id、simulation_trades.plan_id+plan_version）。
- **影响面**：quant schema 新增 5 表 2+2 列；迁移 dry-run 默认；全部可回滚。

## 背景与问题 `serves: FR-1`

### 需求来源 `serves: FR-1`

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 计划实体与生命周期 | trading_plans + trading_plan_events |
| FR-2/FR-6 | 编译映射与版本对照 | trading_plan_rules + trading_plan_versions（基线冻结） |
| FR-4/FR-7 | 成交归因 | simulation_trades.plan_id/plan_version；watch_rules.plan_id |
| FR-5 | 反思报告与材料包快照 | plan_reflections |

### 现状与代价 `serves: FR-1`

现状：watch_rules 无归属列（规则是谁的、为什么存在答不出）；simulation_trades 只按 signal_id/strategy_name 归因（无计划维度）。

### 为什么是现在 `serves: FR-1`

表结构是编译器与归因的先决条件；迁移必须先于任何代码上线。

## 目标与非目标 `serves: FR-1`

### 目标 `serves: FR-1`

- 5 表字段/约束/索引定死；迁移幂等（重跑 0 变更）；既有行行为零变化（NULL fail-open）。

### 非目标 `serves: FR-1`

- 不动既有表既有列语义；不做历史数据回填（历史成交标「计划外」）；
- 不加 CHECK 枚举约束（值域由应用层把守——沿用 watch_rules position_state 的裁定口径，给未来扩枚举留余地）。

## 方案总览 `serves: FR-1`

**一句话方案**：计划本体 + 版本快照 + 规则映射 + 事件留痕 + 反思档案五表正交，既有表只加可空归因列。

```text
trading_plans 1───n trading_plan_versions（每次 apply 一行，冻结基线）
             1───n trading_plan_rules（编译产物映射：plan_id+role+symbol → rule_id）
             1───n trading_plan_events（状态/修改留痕）
             1───n plan_reflections（反思报告+材料包快照）
watch_rules.plan_id ─┐
                     ├─ 归因（NULL=非托管/计划外，fail-open）
simulation_trades.plan_id/plan_version ─┘
```

**关键概念**：版本快照（version 行不可变，是修改对照的基线来源）；归因列 NULL 语义（不是「无计划」，是「不参评」）。

## 架构与依赖 `serves: FR-1`

- **模块划分**：ORM 模型落 infrastructure/persistence/orm/models/trading_plan.py；仓储落 L1 adapters/outbound/repositories/trading_plan_repository.py（与 watch 系同层）。
- **依赖方向**：qs_plan → 仓储端口 → L1 仓储 → ORM（与 watch 系同口径）。
- **外部依赖**：无；迁移走 infrastructure/persistence/migrations/ 既有目录与 dry-run 约定。
- **与既有架构的差异**：无。

## 数据模型 `serves: FR-1, FR-2, FR-4, FR-5, FR-6, FR-7`

### trading_plans `serves: FR-1`

| 字段 | 类型 | 必填 | 说明 | 约束 |
|---|---|---|---|---|
| id | serial PK | 是 | 计划 id | — |
| account | varchar(60) | 是 | 归属账户（单计划单账户） | 非空 |
| name | varchar(120) | 是 | 计划名 | — |
| horizon | varchar(16) | 是 | day / swing | 应用层枚举 |
| status | varchar(16) | 是 | draft/active/holding/closing/closed/archived/paused | 应用层枚举；非法迁移 422 |
| spec | JSONB | 是 | targets/entry/exit/monitoring/schedule | 创建时四段必填校验 |
| draft_spec | JSONB | 否 | PATCH 暂存（apply 后清空） | — |
| version | int | 是 | 当前版本（从 1 起） | apply 时 +1（乐观锁） |
| stats | JSONB | 否 | 命中率/盈亏/时延缓存（系统写） | 只读 |
| review_interval_days | int | 否 | 反思周期（缺省 1=每日） | >0 |
| review_due_at | timestamptz | 否 | 下次反思到期 | — |
| last_reflected_at | timestamptz | 否 | 最近反思时间 | — |
| reflection_overdue_count | int | 否 | 连续缺席计数（默认 0） | ≥0 |
| activated_at / closed_at | timestamptz | 否 | 生命周期时间戳 | — |
| close_reason | text | 否 | 关闭理由 | closed 时必填 |
| created_by | varchar(50) | 是 | agent/user | — |
| created_at / updated_at | timestamptz | 是 | 时间戳 | — |

索引：`(account, status)` 普通（today 视图主查询）；`(review_due_at)` 普通（反思到期扫描）。

### trading_plan_versions `serves: FR-1`

| 字段 | 类型 | 必填 | 说明 | 约束 |
|---|---|---|---|---|
| id | serial PK | 是 | — | — |
| plan_id | int FK | 是 | → trading_plans.id | 级联删除 |
| version | int | 是 | 版本号 | (plan_id, version) 唯一 |
| spec | JSONB | 是 | 该版本 spec 快照 | 行不可变 |
| baseline | JSONB | 否 | 修改前冻结基线指标 | apply 时写入 |
| window_days | int | 否 | 观察窗交易日数 | 默认 10 |
| window_ends_at | date | 否 | 观察窗到期日 | — |
| change_reason | text | 否 | 修改理由（横跳时强制） | — |
| hypothesis | JSONB | 否 | 假设卡（change/evidence/expected） | agent 修改必填 |
| created_by / decision_audit_id / created_at | — | 是 | 留痕三件套 | agent 修改时 audit 必填 |

### trading_plan_rules `serves: FR-1`

| 字段 | 类型 | 必填 | 说明 | 约束 |
|---|---|---|---|---|
| plan_id | int FK | 是 | → trading_plans.id | (plan_id, role, symbol) 联合唯一=幂等键 |
| rule_id | int FK | 是 | → watch_rules.id | 一规则最多属一计划 |
| role | varchar(24) | 是 | entry/stop_loss/take_profit/reduce/news | 应用层枚举 |
| symbol | varchar(20) | 是 | 标的（归一码） | — |
| created_at | timestamptz | 是 | — | — |

### trading_plan_events `serves: FR-1`

| 字段 | 类型 | 必填 | 说明 | 约束 |
|---|---|---|---|---|
| id | serial PK | 是 | — | — |
| plan_id | int FK | 是 | → trading_plans.id | — |
| kind | varchar(24) | 是 | status_change/spec_change/compile/drift/reflection/fill | — |
| from_status / to_status | varchar(16) | 否 | 状态变迁（kind=status_change 时必填） | — |
| detail | JSONB | 否 | 变更明细/diff/drift 对照 | — |
| reason | text | 否 | 理由 | — |
| actor | varchar(50) | 是 | agent/user/system | — |
| decision_audit_id | varchar(64) | 否 | agent 自主变更必填 | 沿用 CHECK 纪律 |
| created_at | timestamptz | 是 | — | — |

索引：`(plan_id, created_at)` 普通（时间线查询）。

### plan_reflections `serves: FR-1`

| 字段 | 类型 | 必填 | 说明 | 约束 |
|---|---|---|---|---|
| id | serial PK | 是 | 报告 id | — |
| plan_id | int FK | 是 | → trading_plans.id | — |
| kind | varchar(16) | 是 | daily/weekly/due/event | 应用层枚举 |
| period | varchar(16) | 是 | 周期标识（如 2026-10-21） | (plan_id, kind, period) 唯一=同周期重写为新版本行 |
| version | int | 是 | 同周期内版本（从 1 起） | — |
| evidence_pack | JSONB | 是 | 材料包快照（四输入） | — |
| answers | JSONB | 是 | 五问作答（缺项即 400，不落库） | — |
| verdict | varchar(16) | 是 | keep/adjust/close/observe | keep/observe 必须 reasoning 非空 |
| reasoning | text | 否 | 理由 | — |
| actions | JSONB | 否 | 修改提案数组 | verdict=adjust/close 必填 |
| knowledge_updates | JSONB | 否 | 进化层消费段 | 只读 |
| agent_session_id | varchar(120) | 否 | 反思会话溯源 | — |
| created_at | timestamptz | 是 | — | — |

### 既有表加列 `serves: FR-1`

| 表 | 列 | 类型 | 语义 | 兼容 |
|---|---|---|---|---|
| watch_rules | plan_id | int NULL | 托管归属（NULL=非托管） | 既有行 NULL，行为零变化 |
| simulation_trades | plan_id | int NULL | 计划归因（NULL=计划外） | 历史行 NULL，不回填 |
| simulation_trades | plan_version | int NULL | 成交时计划版本（实验对照） | 同上 |

- **约束与不变量**：trading_plan_rules 联合唯一键即编译幂等键；plan_reflections (plan_id,kind,period) 唯一；版本行只插不改（审计不可变）。
- **迁移与回填**：迁移文件 `infrastructure/persistence/migrations/20261105_trading_plan.py`（dry-run 默认；--apply 写库；生产与 *_test 各一次）；无历史回填；重跑幂等（IF NOT EXISTS）。
- **生命周期**：计划 closed→30 天后可 archived（事件留痕保留）；reflections 不删；版本行随计划级联删除（仅 DROP 表场景）。

## 接口设计 `serves: FR-1`

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | 仓储 create_plan(spec) | 计划字段 | 计划行 | 缺必填段 → ValueError | 新增 |
| IF-2 | 仓储 record_reflection(report) | 五问报告 | report_id | 唯一键冲突 → 版本+1 新行 | 新增 |

#### IF-1 仓储 create_plan(spec) `serves: FR-1`

**语义**

单事务写计划行+首个版本行+事件行（同生共死，无半成品）。

**错误码**

spec 缺段 → ValueError（路由层转 400 PLAN_SPEC_INVALID）。

**兼容性**

新增端口，无旧调用方。

#### IF-2 仓储 record_reflection(report) `serves: FR-1`

**语义**

反思落库；同 (plan_id,kind,period) 再写时 version+1 新行（旧报告保留可查）。

**错误码**

五问缺项在路由层已 400，仓储层不再二次校验（单点校验在 plan_service）。

**兼容性**

新增端口。

## 备选方案 `serves: FR-1`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 5 表正交+可空归因列 | 语义清晰、回滚简单 | 表数多 | — |
| B | 单表（spec+versions+events 全塞 JSONB） | 表少 | 版本对照/时间线查询只能全行扫 | 修改评估是核心场景 |
| C：什么都不做 | 计划存 JSON 文件（仿 core_plan） | 零迁移 | 归因无法 join、并发无 CAS、审计无从谈起 | D-4 要求修改有对照 |

## 四风险与证据 `serves: FR-1`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 五表是反思/归因的必要条件吗 | FR-4/5/6/7 逐条映射 | 已验证 |
| 可用性 | 仓储口径与既有 watch 系一致吗 | 同层同模式（BaseORMRepository） | 已验证 |
| 可行性 | 迁移风险 | 全部新建/加可空列；dry-run 先行 | 已验证 |
| 商业可行性 | 存储成本 | KB 级/日/计划 | 已验证 |

**未验证项的补课计划**：无未验证项。

## 失败模式与回滚 `serves: FR-1`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 迁移半执行 | --apply 中途失败 | 缺表/缺列 | dry-run 报告+启动预检 | 重跑迁移（幂等） | agent |
| 缺列库上运行新代码 | 迁移未跑 | 读写报错 | 仓储列预检（沿用 _COLUMNS_SQL 模式）→ 降级 fail-open | 跑迁移 | agent |
| 版本行膨胀 | 高频修改 | 表变大 | 每日行数监控 | 归档策略（后续需求） | 用户 |

- **开关**：PLAN_ENABLED=false 时新表无人写（代码路径整体关闭）；
- **回滚演练**：quant_test 库 migrate→rollback（DROP 新表/列保留）演练一次；
- **不可逆动作**：无（新表可 DROP、列保留无害）。

## 跨关注点 `serves: FR-1`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新暴露面 | 仓储参数化（SQLAlchemy 绑定变量） |
| 隐私与合规 | 不适用 | — |
| 成本 | 5 表 2 列，KB 级/日 | — |
| 可观测性 | 迁移 dry-run 报告；缺列预检日志 | 沿用既有模式 |
| 性能与容量 | today 主查询走 (account,status) 索引；反思扫描走 review_due_at | 索引设计见上 |
| 文档与支持 | 本文档 + 迁移文件 docstring | — |

## 交付拆分与里程碑 `serves: FR-1`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | 5 表迁移 + ORM + 仓储 | dry-run 报告 0 差异；仓储测试绿 | 本窗口 | 第 1 批 |
| M2 | 归因列接线（规则/成交） | 归因读写测试绿 | 本窗口 | 第 2 批 |

## 需求追溯 `serves: FR-1`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | trading_plans/events | TC-1~TC-3 | 状态机用例数 |
| FR-2 | trading_plan_rules/versions | TC-4~TC-7 | 幂等键断言 |
| FR-4 | simulation_trades.plan_id | TC-9~TC-11 | 归因正确率 |
| FR-5 | plan_reflections | TC-12~TC-14 | 五问齐全率 |
| FR-6 | versions.baseline | TC-15~TC-17 | 横跳拒绝率 |
| FR-7 | blocked 统计视图 | TC-18/19 | 覆盖率 |

## 常见问题 `serves: FR-1`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 表多——五表正交各有单一职责，比单表 JSONB 好查 |
| 6 个月后会成为什么负担 | versions 膨胀——已登记归档策略为后续需求 |
| 流量涨 10 倍先坏在哪里 | reflections evidence_pack 体积——超 50 条给指针（见 architecture.md 开放问题） |
| 谁半夜被叫起来 | 无人——迁移失败有预检降级 |
| 数据错了怎么修 | 版本行不可变，错误修改只能再 apply 新版本纠正（审计链完整） |
| 这个决定错了多久能发现 | 仓储测试 CI；dry-run 报告每次迁移可见 |

## 开放问题 `serves: FR-1`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| plan_reflections 是否保留 evidence_pack 全量 | A 全量；B 截断+指针 | 本窗口 | 拆分前：倾向 B 超 50 条截断 |
| versions 归档策略 | A 保留全部；B 保留近 50 版 | 本窗口 | 后续需求（本轮保留全部） |

## 附录 `serves: FR-1`

- **相关文档**：architecture.md / interfaces.md / test-cases.md / use-cases.md（同目录）；requirement.md
- **迁移文件**：`infrastructure/persistence/migrations/20261105_trading_plan.py`（实施期创建）
- **评审记录**：待设计确认门落章
- **变更历史**：v1 初稿（2026-10-21）
