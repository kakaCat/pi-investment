---
title: 交易计划与反思闭环 · 架构设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: 要创建一个qs_plan里创建/REQ-261021222905-6dff/requirement.md
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
created: 2026-10-21
updated: 2026-10-21
---

# 交易计划与反思闭环 · 架构设计  serves: FR-1

## 摘要 `serves: FR-1`

- **问题**：系统无「交易计划」一等实体——建仓在 core_plan.json、盘中盯盘在 watch_rules、agent 盘前无计划可读、规则修改无理由链；agent 主下单路径成交后 watch 不收敛。
- **方案**：新增独立包 `packages/qs_plan`——计划实体 + 幂等编译器（计划→watch_rules）+ 成交归因回写 + 定时反思（四输入五问）+ 反思驱动计划修改通道；复用 WatchEngine 执行、不新增下单路径。
- **影响面**：新增 1 包 + 4 表；改动 qs_trading（成交发事件）、qs_watch（plan_id 列与统计）、qs_ops（2 个反思定时任务）、qs_agenthub（消费反思知识段）、agent-ts（盘前加载与反思会话）。

## 背景与问题 `serves: FR-1`

### 需求来源 `serves: FR-1`

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 「交易计划，我们是如何实现的？」（现状审计：无一等实体） | 新增 trading_plans 实体 + 生命周期状态机 + 版本化 |
| FR-2 | 流程图 F/H 节点（入场条件集合、二次校验）无归属 | 计划 spec 持有条件集，编译为托管 watch_rules |
| FR-3 | 「Agent启动：加载交易计划」断链（agent-ts 零引用 core_plan） | GET /api/plans/today 一屏聚合 |
| FR-4 | D-1「不自动下单是设计……agent做最后判断」 | execute_trade 发 FillEvent(plan_id) → FillSync 收敛 → 计划状态推进 |
| FR-5/FR-6 | D-5「缺少反思功能，定时器通过agent反思」；D-4「修改+错过机会+盈利+亏损做反思基础，通过反思修改交易计划」 | 定时器+材料包+五问议程+更新通道（预览→确认→apply） |
| FR-7 | 错过机会/被拦信号走势答不出 | 被拦归档触发纳入回填统计视图 + 成交 plan_id 归因 |
| FR-8 | D-2「agent来做……进化交易规则」+ D-3「不要搞混，三件事」 | 进化层只消费反思报告沉淀 agent_knowledge，结构性不可能写 plans |
| FR-9 | core_plan 与执行层无上下游 | 批次→draft 计划适配器（P2） |

### 现状与代价 `serves: FR-1`

2026-10-21 全链路审计（本窗口，逐节点取证）：流程图 21 节点等权完成度约 65%；
关键断点——agent 经 `/api/simulation/.../trade` 成交不产 FillEvent（生产 `watch_triggers.detail` 含 exec 的行=0）、
无计划实体（core_plan 明写「不含退出判断」）、agent-ts 对 core_plan 零引用、消息命中不建待办。

### 为什么是现在 `serves: FR-1`

用户连续裁定立项（D-1~D-6）；盯盘执行闭环（RFC 017）刚落地，计划层是其天然上层；
再不建计划层，反思/进化永远缺载体，规则修改继续无理由链。

## 目标与非目标 `serves: FR-1`

### 目标 `serves: FR-1`

- 计划 CRUD + 状态机（draft→active→holding→closing→closed→archived，含 paused）可用，非法迁移 4xx；
- 激活即编译：spec 幂等编译为带 plan_id 的 watch_rules，重复激活规则数不变；
- agent 盘前一个接口拿到今日计划（P95<500ms）；
- 带 plan_id 的成交回执收敛待办、翻转 position_state、推进计划状态，重放幂等；
- 盘后/周六定时器产出五问齐全的反思报告；反思提案经确认通道生效并重编译。

### 非目标 `serves: FR-1`

- 不做自动下单（D-1 宪法；做了 = 违反「agent 终判」裁定，资损责任链断裂）；
- 不做前端界面（sides 仅 backend；做了 = 多一条 UI 链路，本期价值不增）；
- 不新建执行引擎（做了 = 与 WatchEngine 双份维护、行为漂移）；
- 不让反思/进化直接写计划（D-3；做了 = 修改失去对照与审计）；
- 不改 WatchEngine 15 阶段流水线骨架（行为漂移风险）。

## 方案总览 `serves: FR-1, FR-2`

**一句话方案**：计划是「决策对象」，编译成盯盘规则去执行；成交与复盘数据回流推进计划状态；定时反思产提案，经确认通道改计划并重编译，形成日级闭环。

```text
agent/人 --> plan_async(API) --> qs_plan(service/compiler/aggregator/reflection_pack)
                                      | 编译                ^ FillEvent(plan_id)
                                      v                     |
                           watch_rules(plan_id) --> WatchEngine --> 指令卡/待办 --> agent 下单 --> execute_trade
qs_ops 定时器 --> reflection_pack(材料包) --> agent 反思 --> plan_reflections --> 更新通道 --> 重编译
```

**关键概念**：TradingPlan（计划实体）；托管规则（编译产物，带 plan_id+role）；编译器（幂等 diff）；材料包（反思证据快照）；更新通道（预览→确认→apply）。

## 架构与依赖 `serves: FR-1, FR-2, FR-4`

- **模块划分**：`qs_plan/domain/plan`（实体/状态机/退出策略/编译规则，纯逻辑无 I/O）；`qs_plan/application`（plan_service 生命周期、plan_compiler 编译、plan_aggregator today 视图、reflection_pack_service 材料包）；仓储走 L1 `adapters/outbound/repositories/trading_plan_repository.py`（与 watch 系同口径）；API 走 `adapters/inbound/fastapi_app/routes/plan_async.py`。
- **依赖方向**：`qs_plan → qs_watch / qs_trading / qs_sourcing / qs_market_data / qs_kernel`（单向，import-linter 强制）；反向回调（FillSync 推进计划状态）走端口注入，不反向 import。
- **外部依赖**：无新增三方依赖；qs_trading 挂掉时编译降级为「建仓面只读」；qs_market_data 快照缺失时环境闸维度标 skipped（沿用 fail-open）。
- **与既有架构的差异**：首个「跨包编排型」二方包（读多包、写 watch 规则）——依赖边已在 pyproject 声明并受 import-linter 守门；其余沿用 S1-S10 包格局。

## 数据模型 `serves: FR-1, FR-4, FR-5, FR-7`

详见 data-model.md。要点：新表 trading_plans / trading_plan_versions / trading_plan_rules / trading_plan_events / plan_reflections 共 5 张；既有表加可空列 watch_rules.plan_id、simulation_trades.plan_id+plan_version；NULL=非托管/计划外，fail-open；迁移 dry-run 默认、回滚=列保留无害/新表可 DROP。

## 接口设计 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-9`

接口全集与明细见 interfaces.md（「接口清单」节 16 条 IF）。骨架：

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | POST /api/plans | spec | 计划（status=draft, version=1） | spec 非法 → 400 PLAN_SPEC_INVALID | 新增，无旧方 |
| IF-2 | GET /api/plans/today | account | 聚合视图 | 无计划 → 200+empty | 新增 |
| IF-3 | POST /api/plans/{id}/apply | expected_version | 编译 diff 回执 | 409 VERSION_CONFLICT / 422 状态非法 | 新增 |
| IF-4 | POST /api/plans/{id}/reflections | 反思报告 | 落库回执 | 五问缺项 → 400 REFLECTION_INCOMPLETE | 新增 |

#### IF-1 POST /api/plans `serves: FR-1`

**语义**

创建 draft 计划。spec 必填段：targets、entry、exit（stop_loss 或 reduce_plan 至少其一）、monitoring、schedule；
缺必填段即拒，不收半成品。

**错误码**

400 PLAN_SPEC_INVALID（缺段/字段非法，响应含逐条缺项）→ 调用方补全后重试；401 账户不存在 → 放弃。

**兼容性**

新增接口，无旧调用方；spec JSONB 前向兼容（未知字段忽略但记 warning 日志）。

#### IF-2 GET /api/plans/today `serves: FR-1`

**语义**

agent 盘前聚合视图：该账户 active/holding 计划 + 每标的条件就绪度 + 环境闸当前 verdict + 持仓差额 + 未决待办数。

**错误码**

无计划 → 200 + `empty=true`（不是错误）；环境闸数据缺失 → 维度标 skipped（fail-open，不用 0 冒充）。

**兼容性**

新增接口；响应字段只增不改（additive）。

#### IF-3 POST /api/plans/{id}/apply `serves: FR-1`

**语义**

把 PATCH 暂存的 draft_spec 生效：version++ + 编译 diff 落库 + 审计；必须先经预览（PATCH 响应或 compile-preview）看到 diff。

**错误码**

409 VERSION_CONFLICT（expected_version 过期）→ 重读后重试；422 PLAN_STATE_ILLEGAL（如 closed 计划）→ 放弃；
400 修改纪律拒绝（观察窗内无说明横跳）→ 补说明或放弃。

**兼容性**

新增接口。

**幂等与重试**

同一 expected_version 重复 apply：第一次生效后版本已推进，重放即 409——天然幂等，不产生二次编译。

#### IF-4 POST /api/plans/{id}/reflections `serves: FR-1`

**语义**

agent 写回反思报告：五问（盈亏对质/修改评估/错过对质/逻辑存活/修改决议）+ verdict + 修改提案 + 材料包快照。

**错误码**

400 REFLECTION_INCOMPLETE（五问缺项、verdict=keep 无理由、adjust 无提案）→ 补全重试；404 PLAN_NOT_FOUND → 放弃。

**兼容性**

新增接口；报告只追加不改写（同一周期重写=新版本行，旧报告保留可查）。

## 备选方案 `serves: FR-1`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 独立包 qs_plan，编译复用 WatchEngine | 边界干净、执行零重写、可独立验收 | 多一个包的装配与迁移 | — |
| B | 塞进 qs_watch | 少一个包 | watch 使命膨胀成决策层；归因写 trading 加深耦合 | 包 CLAUDE.md 明写 watch=盘中守门员 |
| C | 塞进 qs_trading | 成交同域 | trading 需向上依赖 watch → 依赖倒挂 | import-linter 直接拦 |
| D：什么都不做 | 维持 core_plan.json + watch_rules 两层 | 零成本 | 计划/反思/进化永无载体；回执断点不修复 | 用户已裁定立项（D-1~D-6） |

## 四风险与证据 `serves: FR-1`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | agent/用户真的需要计划层吗 | 用户 6 轮对话逐层确认（D-1~D-6 落账）；现状审计 21 节点取证 | 已验证 |
| 可用性 | agent 会用 today 视图与反思会话吗 | 未验证（agent-ts 接线后才可证） | 部分 |
| 可行性 | 编译复用 WatchEngine 建得出来吗 | watch_rules CRUD/plan_id 列/FillSync 端口均已在生产；221 例闭环测试全绿 | 已验证 |
| 商业可行性 | 维护成本可接受吗 | 不新建引擎/不新增依赖；5 表 2 列 | 已验证 |

**未验证项的补课计划**：可用性 → FR-3 落地后让 agent 真实盘前拉取一次，以「计划被引用进当日决策」为证（实施期验证）。

## 失败模式与回滚 `serves: FR-1`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 编译中途失败 | 进程被杀/DB 异常 | 无（事务回滚，无半编译态） | 编译事务日志 + plan_events 缺席 | 重跑（幂等） | agent |
| execute_trade 发事件失败 | 端口异常 | 成交正常、回执缺失 | 事件发送 error 日志 | 不影响成交（只记日志）；事后补对账 | agent |
| 反思材料包组装失败 | 数据源异常 | 当日反思缺席 | overdue_count 递增 | 次日重试；连续 3 日告警 | agent |
| 误把既有规则当托管 | plan_id 写错 | 旧规则被编译器接管 | 迁移只写新规则，不动存量；审计行核查 | 清 plan_id 即恢复非托管 | 用户 |
| 计划状态机卡死 | 非法迁移 bug | 计划停在某状态 | 状态机守卫测试 + plan_events 对账 | 人工 force 迁移（留痕） | 用户 |

- **开关**：`PLAN_ENABLED`（默认 true）、`PLAN_REFLECTION_ENABLED`（默认 true）——关闭后计划 API 只读、反思任务空跑，盯盘行为与现状一致；
- **回滚演练**：上线前在 quant_test 库演练「关开关 → 行为与现状一致」；预计恢复 <5 分钟；
- **不可逆动作**：无（全部变更可回滚：列保留无害、新表可 DROP、开关可关）。

## 跨关注点 `serves: FR-1`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新鉴权面（内网 API 同现状） | agent 自主修改必须带 decision_audit_id（沿用 watch_rule_changes CHECK 纪律） |
| 隐私与合规 | 不涉个人信息 | 交易数据同既有口径 |
| 成本 | 5 表 2 列 + 每计划每拍零新增计算（编译产物走既有 tick） | 反思材料包每计划每日一次，体量 KB 级 |
| 可观测性 | plan_events 全量留痕；today 视图带环境闸 verdict；overdue 计数进 metrics | 复用 structlog + watch metrics 端点 |
| 性能与容量 | today 视图 P95<500ms（≤20 计划/账户） | 接口冒烟计时；先坏在材料包组装（有超时与降级） |
| 文档与支持 | 本设计集 + 包 CLAUDE.md（实施期补） | 拆分阶段任务卡引用 |

## 交付拆分与里程碑 `serves: FR-1`

（仅方向性里程碑，不含任务 DAG——任务表归拆分阶段。）

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 地基 | qs_plan 包 + 5 表迁移 + CRUD/状态机 + 编译器 | tests/plan/ 绿；激活→托管规则可见 plan_id | 本窗口 | 拆分后第 1 批 |
| M2 闭环 | today 视图 + execute_trade 事件 + FillSync 推进 + 统计归因 | 模拟成交全链收敛；回执重放幂等 | 本窗口 | 第 2 批 |
| M3 反思 | 定时器 + 材料包 + 反思落库 + 更新通道 + 纪律门 | 五问报告落库；横跳被拒 4xx | 本窗口 | 第 3 批 |
| M4 增强 | 进化对接 + core_plan 适配（P2） | knowledge 落库；结构检查脚本退出码 0 | 本窗口 | 第 4 批 |

## 需求追溯 `serves: FR-1`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | 架构与依赖 / 数据模型 | TC-1~TC-3（test-cases.md） | 状态机守卫用例数 |
| FR-2 | 架构与依赖 / 接口设计 | TC-4~TC-7 | 编译幂等断言 |
| FR-3 | 接口设计（IF-9） | TC-8 | P95<500ms |
| FR-4 | 架构与依赖 / 数据模型 | TC-9~TC-11 | 回执收敛率 100%（测试） |
| FR-5 | 方案总览 / 接口设计（IF-13/14） | TC-12~TC-14 | 五问齐全率 |
| FR-6 | 接口设计（IF-4/5） | TC-15~TC-17 | 横跳拒绝率 100% |
| FR-7 | 数据模型 / 接口设计（IF-16） | TC-18~TC-19 | 被拦信号回填覆盖率 |
| FR-8 | 备选方案 / 需求追溯 | TC-20 | 结构检查退出码 0 |
| FR-9 | 接口设计（IF-15） | TC-21 | 适配幂等 |

## 常见问题 `serves: FR-1`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 「又加一层」——回应：计划不执行，只是把已有规则归档归属；盯盘行为不变 |
| 6 个月后会成为什么负担 | 托管规则与非托管规则两套口径——用 plan_id 判空区分 + 编译器单写点控制 |
| 流量涨 10 倍先坏在哪里 | 材料包组装（N 计划 × 四输入查询）——有超时、降级与 overdue 兜底 |
| 谁半夜被叫起来、手上有什么 | 无人——反思缺席只递增 overdue，连续 3 日才告警；无资损路径 |
| 数据错了怎么修、修得回来吗 | 全部可回滚（列保留/表可 DROP/开关可关）；状态机有人工 force 通道 |
| 这个决定错了多久能发现 | 编译幂等/纪律门用例在 CI；生产以 plan_events 对账，T+1 可见 |

## 开放问题 `serves: FR-1`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 托管规则人工 force 通道的 API 形态 | A 现有 PATCH ?force=true；B 独立端点 | 本窗口 | 拆分前：倾向 A（复用既有守卫） |
| 材料包单份体量上限 | A 全量触发明细；B 截断+指针 | 本窗口 | 拆分前：倾向 B（超 50 条给指针） |
| 反思唤醒 agent 的通道 | A 既有 /wake 直连；B digest 摘要 | 本窗口 | 拆分前：倾向 A（与待办唤醒同源） |

## 附录 `serves: FR-1`

- **相关文档**：requirement.md（9 条 FR + D-1~D-6）；interfaces.md / data-model.md / test-cases.md / use-cases.md（同目录）
- **现状依据**：2026-10-21 本窗口全链路审计（21 节点完成度取证 + RFC 017 闭环 221 例测试全绿 + 生产库计数）
- **评审记录**：待设计确认门（kind=design）落章
- **变更历史**：v1 初稿（2026-10-21）
