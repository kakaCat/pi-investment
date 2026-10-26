---
title: 交易计划与反思闭环 · 后端设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: 要创建一个qs_plan里创建/REQ-261021222905-6dff/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
created: 2026-10-21
updated: 2026-10-21
---

# 交易计划与反思闭环 · 后端设计  serves: FR-1

## 摘要 `serves: FR-1`

- **问题**：后端服务/函数/接线点逐一编号定责（S-1~S-13），拆分阶段按表造卡。
- **方案**：qs_plan 四服务（PlanService/PlanCompiler/PlanAggregator/ReflectionPackService）+ 三处既有件接线（execute_trade 发事件、FillSync 推进计划、lesson_generator 消费知识）+ qs_ops 两定时任务。
- **影响面**：新包 qs_plan；改动 qs_trading / qs_watch / qs_ops / qs_agenthub 各 1-2 个文件。

## 背景与问题 `serves: FR-1`

### 需求来源 `serves: FR-1`

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1~FR-9 | requirement.md 功能点 | S-1~S-13 逐条映射（见需求追溯表） |

### 现状与代价 `serves: FR-1`

现状：计划所需服务全部不存在；三处接线点中两处（execute_trade 事件、FillSync 计划回调）是已证实的生产断点（exec 明细 0 行）。

### 为什么是现在 `serves: FR-1`

服务清单是拆分阶段的对照输入，不定死就会出现「清单里没有的卡凭空造出」。

## 目标与非目标 `serves: FR-1`

### 目标 `serves: FR-1`

- S-1~S-13 每个的类型/职责/输入/输出/调用方/依赖定死；数据流三条主链步骤化。

### 非目标 `serves: FR-1`

- 不写实现代码（签名到职责粒度）；不写任务 DAG（归拆分阶段）。

## 方案总览 `serves: FR-1`

**一句话方案**：四新服务 + 三接线 + 两任务，全部薄壳复用既有模式（watch 系服务层同款）。

```text
agent-dh/agent-ts --trading_plan 工具(S-14/S-15)--> plan_async(S-11) --> PlanService(S-1) --> PlanCompiler(S-2) --> watch_rules
                   --> PlanAggregator(S-3) --> today 视图
scheduler(S-8) --> ReflectionPackService(S-4) --> agent 反思 --> PlanService(apply)
execute_trade(S-6) --FillEvent--> FillSync(S-7) --端口回调--> PlanService(状态推进)
```

**关键概念**：无新增（同 architecture.md）。

## 架构与依赖 `serves: FR-1`

- **模块划分**：qs_plan(domain 纯逻辑 + application 四服务)；L1 仓储 S-10；路由 S-11；qs_ops 任务 S-8。
- **依赖方向**：S-11→S-1/2/3/4→S-10；S-7 经端口回调 S-1（不反向 import）；S-6 只发事件不依赖 qs_plan。
- **外部依赖**：无新增；S-8 复用 TradingDayGuard。
- **与既有架构的差异**：无。

## 数据模型 `serves: FR-1`

以 data-model.md 为唯一权威（5 表 2 列）；本文不重复字段定义。

## 接口设计 `serves: FR-1`

HTTP 接口契约以 interfaces.md 为唯一权威（IF-1~IF-16）。本节给内部服务接口骨架：

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | PlanService.apply(plan_id, expected_version, actor) | 计划 id + 版本 + 操作者 | ApplyResult(diff, version, audit_id) | VersionConflict / StateIllegal / ChangeLocked | 新增 |
| IF-2 | ReflectionPackService.build(plan_id, now) | 计划 id + 时钟 | EvidencePack(四输入) | 数据源异常 → 段级 missing | 新增 |

#### IF-1 PlanService.apply `serves: FR-1`

**语义**

两步提交第二步：校验版本/状态/纪律门 → 调编译器落 diff → 版本行冻结基线 → 事件留痕，单事务。

**错误码**

VersionConflict（重放即拒=幂等）；StateIllegal；ChangeLocked（附缺失说明项）。

**兼容性**

新增应用服务接口。

#### IF-2 ReflectionPackService.build `serves: FR-1`

**语义**

组装四输入材料包：修改历史（版本行+事件）、错过机会（被拦回填+踏空打分）、盈利、亏损（含止损后走势）；段级失败不拖垮整包。

**错误码**

整包失败 → 抛异常（任务层记日志+overdue，不写半成品）。

**兼容性**

新增。

## 服务与接口实现 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9`

| 编号 | 类型 | 名称 | 职责说明 | 输入 | 输出 | 调用方 | 依赖 | serves |
|---|---|---|---|---|---|---|---|---|
| S-1 | 模块 | PlanService | 计划 CRUD/生命周期/两步提交/纪律门 | plan_id, spec, actor, expected_version | Plan / ApplyResult / 错误码 | S-11 路由、S-7 回调 | S-10, S-2, S-5 | FR-1, FR-6 |
| S-2 | 模块 | PlanCompiler | spec→watch_rules 幂等 diff/apply/退役 | spec, 持仓真值, 现存托管规则 | CompileDiff(create/update/retire) | S-1 | S-10, watch_rule_repository | FR-2 |
| S-3 | 模块 | PlanAggregator | today 聚合视图组装 | account, now | TodayView(plans/env_gate/delta/todos) | S-11 | S-10, 环境闸服务, 持仓仓储 | FR-3 |
| S-4 | 模块 | ReflectionPackService | 四输入材料包组装 | plan_id, now | EvidencePack | S-8 | S-10, outcome 仓储, 成交仓储, missed_opportunity | FR-5, FR-7 |
| S-5 | 函数 | evaluate_plan_transition | 状态机守卫（纯函数：当前状态+目标→允许/拒绝+原因） | from_status, to_status, ctx | (ok, reason) | S-1 | 无（domain 纯逻辑） | FR-1 |
| S-6 | 服务 | AccountTradingService.execute_trade（改） | 成交后 emit FillEvent(plan_id, plan_version) | 成交入参（既有） | 成交结果（既有）+ 事件 | /trade 路由（既有） | IFillListener 端口（既有） | FR-4 |
| S-7 | 服务 | FillSyncService（改） | 收敛时按 plan_id 经端口回调推进计划状态 | FillEvent | 收敛结果（既有）+ 计划状态推进 | 组合根（既有） | IPlanProgressPort（新端口） | FR-4 |
| S-8 | 服务 | PlanReflectionJob（新，qs_ops） | 盘后/周六扫到期计划→组包→唤醒 agent→超时计 overdue | now | {packed, woken, overdue} | scheduler_tasks 调度 | S-4, TradingDayGuard, wake 通道 | FR-5 |
| S-9 | 服务 | LessonGenerator（改） | 消费 reflections.knowledge_updates 落 agent_knowledge | reflection 行 | knowledge 条目 | 既有进化调度 | plan_reflections（只读） | FR-8 |
| S-10 | 模块 | TradingPlanRepository（新，L1） | 五表读写 + 缺列预检降级 | 各表查询/写入 | ORM 行 | S-1/2/3/4 | ORM（既有 Base） | FR-1~FR-7 |
| S-11 | 模块 | plan_async 路由（新） | IF-1~IF-15 薄壳（校验+调服务+错误映射） | HTTP 请求 | 结构化响应 | agent/人 | S-1/2/3/4 | FR-1~FR-9 |
| S-12 | 函数 | build_blocked_stats（watch 侧扩） | 被拦/抑制触发的走势统计聚合 | since, horizon | 统计行 | IF-16 路由 | outcome 回填表（既有） | FR-7 |
| S-13 | 服务 | CorePlanAdapter（新，P2） | core_plan 批次→draft 计划（幂等） | account, batch | [plan_id] | IF-15 路由 | core_plan.json（只读）, S-1 | FR-9 |
| S-14 | 模块 | TradingPlanTool（agent-dh，packages/tools） | trading_plan 工具：封装 IF-1~15，账户取 agents.json（投资脑主消费方，D-9） | action + 操作参数 | 工具结果（透传+摘要） | 投资脑会话 | QuantsysV2Client（既有） | FR-3, FR-5, FR-6 |
| S-15 | 模块 | trading-plan-tool（agent-ts，src/infrastructure/tools） | 同契约双端实现（D-7） | action + 操作参数 | 工具结果 | fin-agent 会话 | quant-v2-client（既有） | FR-3, FR-5, FR-6 |

## 数据流 `serves: FR-1, FR-2, FR-4, FR-5`

**流程 A：激活编译（FR-2）**
```
事件：POST /api/plans/{id}/activate
 1. S-11 校验 → S-1.activate（S-5 守卫：draft/paused→active）
 2. S-1 调 S-2.compile：
    2.1 读现存托管规则（S-10）算 diff；
    2.2 create：写 watch_rules（plan_id/role/position_state=持仓真值）+ trading_plan_rules 映射；
    2.3 全部成功才提交（单事务，失败整体回滚）；
 3. S-1 写版本行 v1 + plan_events(compile)；返回编译回执。
副作用：watch_rules 新增托管规则、映射行、版本行、事件行（同事务）。
```

**流程 B：成交回执推进（FR-4）**
```
事件：agent 经 POST /api/simulation/accounts/{acct}/trade 成交
 1. S-6 成交落库（既有）→ emit FillEvent(plan_id, plan_version)（新增；失败只记日志不阻断成交）；
 2. S-7.on_fill：
    2.1 收敛待办/触发（既有）；
    2.2 有 plan_id → 经 IPlanProgressPort 回调 S-1.on_plan_fill：
        清仓 → active/holding→closing→closed；部分 → 对应批次规则退役，状态保持；
 3. 重放：FillSync 幂等（既有），计划回调以版本+成交 id 去重。
副作用：待办/触发收敛（既有）、计划状态行+事件行、规则退役。
```

**流程 C：定时反思（FR-5/FR-6）**
```
事件：scheduler 触发 plan_reflect_daily（盘后 15:35，交易日守卫）
 1. S-8 扫 review_due_at<=now 的计划；
 2. 逐计划调 S-4.build → 材料包（段级 missing 兜底；整包失败记日志+overdue）；
 3. S-8 经 wake 通道唤醒 agent（材料包随行）；超时未写回 → overdue_count+1（连续 3 日告警）；
 4. agent（投资脑 agent-dh / fin-agent agent-ts）经 trading_plan 工具（S-14/S-15 → IF-12）提交反思
   （S-11→S-1.record_reflection：五问校验 400/落库）；
 5. 提案经 IF-11 预览 → 确认 → IF-5 apply（S-1：版本 CAS+纪律门→S-2 重编译→基线冻结）。
副作用：plan_reflections 行、overdue 计数、（apply 时）规则重编译+版本行。
```

## 备选方案 `serves: FR-1`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 四服务分模块 + 端口回调 | 边界清、可单测（domain 纯逻辑） | 文件数多 | — |
| B | 单一大 PlanService（编译/聚合/材料包全塞） | 文件少 | 违本仓「服务单一职责」惯例，测试面爆炸 | watch 系已证明分模块可维护 |
| C：什么都不做 | 逻辑全写路由里 | 最少文件 | 无契约、不可单测 | 本仓分层纪律不允许 |

## 四风险与证据 `serves: FR-1`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | S 表覆盖全部 FR 吗 | 需求追溯表逐条对 | 已验证 |
| 可用性 | 端口回调模式可行吗 | IFillListener 既有同款（FillSyncService 已生产注册） | 已验证 |
| 可行性 | S-6 改动安全吗 | execute_trade 已有「审计/绩效不影响成交」先例（11b 旁路） | 已验证 |
| 商业可行性 | — | 无新依赖 | 已验证 |

**未验证项的补课计划**：无未验证项。

## 失败模式与回滚 `serves: FR-1`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| S-2 编译中途失败 | 仓储异常 | 无（事务回滚） | 编译日志 | 重跑幂等 | agent |
| S-6 事件失败 | 端口异常 | 回执缺失（成交正常） | error 日志 | 日频对账+人工 force | agent |
| S-8 材料包失败 | 数据源异常 | 当日反思缺席 | overdue 递增 | 次日重试 | agent |
| S-7 回调失败 | qs_plan 侧异常 | 计划状态不推进 | error 日志（不影响收敛主链） | 人工 force 迁移 | 用户 |

- **开关**：PLAN_ENABLED / PLAN_REFLECTION_ENABLED（默认值与粒度同 architecture.md）；
- **回滚演练**：quant_test 三流程各走一遍；
- **不可逆动作**：无。

## 跨关注点 `serves: FR-1`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 写操作审计号强制（S-1）；事件失败不阻断成交（S-6） | 既有 CHECK + 11b 旁路先例 |
| 隐私与合规 | 不适用 | — |
| 成本 | 无新资源 | — |
| 可观测性 | 三流程各有 plan_events 落点 + 既有 structlog | — |
| 性能与容量 | S-3 P95<500ms；S-4 有超时降级 | — |
| 文档与支持 | 本表+数据流即开发说明 | — |

## 交付拆分与里程碑 `serves: FR-1`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | S-1/2/5/10/11（实体+编译面） | TC-1~7 绿 | 本窗口 | 第 1 批 |
| M2 | S-3/6/7/12（视图+回执+统计） | TC-8~11、18/19 绿 | 本窗口 | 第 2 批 |
| M3 | S-4/8/9/13（反思+进化+适配） | TC-12~17、20/21 绿 | 本窗口 | 第 3-4 批 |

## 需求追溯 `serves: FR-1`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | S-1/5/10 | TC-1~3 | 状态机覆盖 |
| FR-2 | S-2/10 | TC-4~7 | 编译幂等 |
| FR-3 | S-3/14/15 | TC-8 / TC-22 | P95 |
| FR-4 | S-6/7 | TC-9~11 | 收敛率 |
| FR-5 | S-4/8/14/15 | TC-12~14 / TC-22 | 五问齐全率 |
| FR-6 | S-1/14/15 | TC-15~17 / TC-22 | 横跳拒绝率 |
| FR-7 | S-4/12 | TC-18/19 | 覆盖率 |
| FR-8 | S-9 | TC-20 | 结构检查退出码 0 |
| FR-9 | S-13 | TC-21 | 幂等 |

## 常见问题 `serves: FR-1`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 改动既有件三处——全部 additive（事件/回调/消费入口），不改既有行为 |
| 6 个月后会成为什么负担 | 端口回调链拉长——端口文档化（本表 S-7） |
| 流量涨 10 倍先坏在哪里 | S-4 材料包组装——超时+段级 missing+overdue 三级兜底 |
| 谁半夜被叫起来 | 无人——无资损新路径 |
| 数据错了怎么修 | 全部留痕可回放（版本行/事件行/审计行） |
| 这个决定错了多久能发现 | TC 与 UC 同剧本，CI 即知 |

## 开放问题 `serves: FR-1`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| S-7 回调端口形态 | A 新 IPlanProgressPort；B 复用事件总线 | 本窗口 | 拆分前：倾向 A（RFC 017 同款端口注入，不引入 pub/sub） |

## 附录 `serves: FR-1`

- **相关文档**：architecture.md / interfaces.md / data-model.md / test-cases.md / use-cases.md（同目录）；requirement.md
- **评审记录**：待设计确认门落章
- **变更历史**：v1 初稿（2026-10-21）
