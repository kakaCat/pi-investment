---
title: 交易闭环补口 · 接口设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: docs/requirements/REQ-261022022657-857f/requirement.md
serves: FR-1, FR-2, FR-3, FR-4
created: 2026-10-22
updated: 2026-10-22
---

# 交易闭环补口 · 接口设计 `serves: FR-1`

## 摘要 `serves: FR-1, FR-2, FR-3, FR-4`

- **问题**：三处接线需要定死内部契约（waker、批次匹配、消息联动）与一个只读指标扩展。
- **方案**：6 条接口，全部为内部函数/既有端点扩展，无新增 HTTP 面、无 schema 变更。
- **影响面**：qs_plan 2 处、qs_watch 2 处、metrics 1 处。

## 背景与问题 `serves: FR-1, FR-2, FR-3, FR-4`

**需求来源**

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 反思唤醒 | IF-1 waker 注入口 |
| FR-2 | 批次收敛 | IF-2 纯函数 + IF-3 on_fill 扩展 |
| FR-3 | 消息→待办 | IF-4 联动函数 + IF-5 读数 |
| FR-4 | 可观测 | IF-5 metrics 扩展 |

**现状与代价**

现状：三处均为内部调用缺失；接口不定死则实现会各自发明参数（例如用笔数而非比例）。

**为什么是现在**

拆分阶段要按接口清单「一接口一卡」对照。

## 目标与非目标 `serves: FR-1, FR-2, FR-3, FR-4`

**目标**

- 6 条接口签名/错误语义一次定死；全部向后兼容（可选参数/新增函数）。

**非目标**

- 不新增 HTTP 端点（消息联动走内部扫描）；新增端点会扩大鉴权面；
- 不改 `/wake` 协议（复用 event+data 信封）。

## 方案总览 `serves: FR-1`

```text
PlanReflectionJob(waker=notify_agent 包装) --> /wake
PlanService.on_fill(sold_ratio) --> match_reduce_batches --> retire rules + event
NewsExitLinkage.link(...) --> TodoService.create --> wake_todo_owner
```

**关键概念**：waker 包装器、累计比例、evidence.source=news。

## 架构与依赖 `serves: FR-1`

- **模块划分**：qs_plan（reflection_job / plan_service / batch_matcher）、qs_watch（news_exit_linkage）、routes（metrics）。
- **依赖方向**：qs_plan → qs_agenthub（notify_agent）；qs_watch → qs_agenthub（wake_todo_owner，已有）。
- **外部依赖**：agent-dh /wake。
- **与既有架构的差异**：无。

## 数据模型 `serves: FR-2, FR-3`

不改表。字段级契约：`trading_plan_events.detail={batch,trade_id,qty,remaining_qty}`；
`watch_todos.evidence={source:'news',news_id,title,hits,symbol,plan_id}`。

## 接口设计 `serves: FR-1, FR-2, FR-3`

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `fn PlanReflectionJob(..., waker=None)` | waker(plan, pack) | — | 构造无副作用 | 缺省 None=旧行为 |
| IF-2 | `fn match_reduce_batches(batches, sold_ratio)` | list, float | list[int] | ValueError(比例越界) | 新增纯函数 |
| IF-3 | `fn PlanService.on_fill(..., sold_ratio=0.0)` | 回执+比例 | 状态字符串 | degraded 事件 | 可选参数 |
| IF-4 | `fn link_news_to_todo(ctx)` | 消息/持仓/计划 | todo_id 或 None | 去重→None；异常记日志 | 新增 |
| IF-5 | `GET /api/watch/metrics` | — | 扩展字段 | 缺数 null | additive |
| IF-6 | `fn wake_todo_owner(todo, ctx=None)` | todo | bool | 既有语义 | 复用不改 |

**IF-1 PlanReflectionJob waker**

**语义**

waker 由组合根注入（AgentNotificationService.notify_agent 的薄包装，event=`plan_reflection`，data 含 plan_id/period/pack 摘要）；返回 False 或抛错 → overdue+1 并继续。

**错误码**

无 HTTP；错误进日志与 overdue 计数。

**兼容性**

缺省 None → 只组包，行为与现状一致。

**IF-2 match_reduce_batches**

**语义**

按 `at_pct` 排序后累计 `sell_ratio`，返回累计 ≤ sold_ratio 的批次下标；sold_ratio≥1 返回全部。

**错误码**

sold_ratio ∉ [0,1] → ValueError；batches 空 → []。

**兼容性**

新增纯函数。

**IF-3 PlanService.on_fill 扩展**

**语义**

新增 `sold_ratio=0.0`；>0 且计划有 reduce_plan 时按 IF-2 匹配、逐批退役规则并写 `kind=fill` 事件；剩余 0 → closing→closed。

**错误码**

无匹配批次 → 事件 detail.degraded=true；同一 trade_id 重放 → 幂等跳过。

**兼容性**

缺省 0.0 = 仅推进状态。

**IF-4 link_news_to_todo**

**语义**

critical 命中持仓/激活计划 → TodoService.create(level=P1, action_kind=rule_change, evidence={source:news,...}) → wake_todo_owner；24h 内同 news_id+symbol 存在则 None。

**错误码**

todo out_of_scope → 跳过留痕；创建异常 → 记日志继续扫描。

**兼容性**

新增；受 `NEWS_TODO_ENABLED` 开关控制（默认 true）。

**IF-5 metrics 扩展**

**语义**

返回 `news_todos_today`（当日 evidence.source=news 计数）与 `reflection_woken_today`（当日唤醒计数），缺数据 null。

**错误码**

只读无错误。

**兼容性**

additive 字段。

**IF-6 wake_todo_owner**

**语义**

既有函数（watch_channels.py:202）：直连 /wake 为主路、facade 兜底。本需求不改其语义，仅复用。

**错误码**

既有（返回 bool）。

**兼容性**

不改。

## 接口清单 `serves: FR-1, FR-2, FR-3, FR-4`

| 接口 id | 形态 | 职责 | serves |
|---|---|---|---|
| IF-1 | `函数 PlanReflectionJob(..., waker=fn)` | 反思任务可注入唤醒通道 | FR-1 |
| IF-2 | `函数 match_reduce_batches(batches, sold_ratio)` | 按累计比例匹配应退役批次 | FR-2 |
| IF-3 | `函数 PlanService.on_fill(..., sold_ratio=0.0)` | 部分成交退役批次并留痕 | FR-2 |
| IF-4 | `函数 link_news_to_todo(ctx)` | 持仓消息 critical → 待办 + 唤醒（去重） | FR-3 |
| IF-5 | `GET /api/watch/metrics`（扩展字段） | news 待办/反思唤醒当日计数 | FR-4 |
| IF-6 | `函数 wake_todo_owner(todo, ctx=None)` | 既有唤醒（复用不改） | FR-1, FR-3 |

## 备选方案 `serves: FR-1, FR-2, FR-3, FR-4`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 内部函数 + 一个 metrics 扩展 | 面小、无鉴权变化 | 无对外可见 API | — |
| B | 新增 /api/plans/{id}/reflect-workflow 端点 | 可外部触发 | 新鉴权面、重复调度入口 | 与调度框架单源冲突 |
| C：什么都不做 | — | — | 闭环仍断 | 用户已立项 |

## 四风险与证据 `serves: FR-1, FR-2, FR-3, FR-4`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 契约是否覆盖三处断点 | FR 逐条映射 | 已验证 |
| 可用性 | 既有函数签名可扩展吗 | on_fill 已含 **kwargs 语义的显式参数 | 部分 |
| 可行性 | 无新依赖 | — | 已验证 |
| 商业可行性 | — | — | 已验证 |

**未验证项的补课计划**：on_fill 调用方（PlanProgressPort）需同步传 sold_ratio，实施期核对。

## 失败模式与回滚 `serves: FR-1, FR-2, FR-3, FR-4`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 参数不兼容 | 旧调用方未传新参 | 行为退回旧态 | 测试 | 缺省值保证兼容 | 本窗口 |
| metrics 扩展破坏前端 | 字段命名冲突 | 前端读不到 | 契约测试 | 改名 | 本窗口 |

- **开关**：NEWS_TODO_ENABLED / PLAN_REFLECTION_WAKE_ENABLED；
- **回滚演练**：关开关跑既有套件；
- **不可逆动作**：无。

## 跨关注点 `serves: FR-1, FR-2, FR-3, FR-4`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新增端点 | 复用既有鉴权 |
| 隐私与合规 | 不适用 | — |
| 成本 | 无 | — |
| 可观测性 | metrics + 事件表 | IF-5 |
| 性能与容量 | 扫描尾部 O(持仓) | sidecar 节流 |
| 文档与支持 | 指南补三节 | trading-plan.md |

## 交付拆分与里程碑 `serves: FR-1, FR-2, FR-3, FR-4`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | IF-1 | 测试绿 | 本窗口 | 第 1 批 |
| M2 | IF-2/IF-3 | 测试绿 | 本窗口 | 第 2 批 |
| M3 | IF-4/IF-6 | 测试绿 | 本窗口 | 第 3 批 |
| M4 | IF-5 | 读数可查 | 本窗口 | 第 4 批 |

## 需求追溯 `serves: FR-1, FR-2, FR-3, FR-4`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | IF-1 | TC-1/TC-2 | woken |
| FR-2 | IF-2/IF-3 | TC-3~TC-5 | batch |
| FR-3 | IF-4/IF-6 | TC-6~TC-8 | news todo |
| FR-4 | IF-5 | TC-9 | metrics |

## 常见问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | on_fill 参数变多——全部可选并带缺省 |
| 6 个月后负担 | 接口膨胀——清单即契约，新增需评审 |
| 流量涨 10 倍 | 不适用（内部调用） |
| 谁半夜被叫起来 | 无人 |
| 数据错了怎么修 | 事件/待办均可人工修正 |
| 错了多久发现 | 首日读数 |

## 开放问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| sold_ratio 由谁计算 | A FillSync 按持仓算；B PlanProgressPort 算 | 本窗口 | 已决：A（持仓真值在 watch 侧） |

## 附录 `serves: FR-1, FR-2, FR-3, FR-4`

- **相关文档**：architecture.md、data-model.md、test-cases.md、backend.md
- **评审记录**：待确认门落章
- **变更历史**：v1.0
