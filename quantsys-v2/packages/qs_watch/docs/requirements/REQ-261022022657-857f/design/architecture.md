---
title: 交易闭环补口 · 架构设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: docs/requirements/REQ-261022022657-857f/requirement.md
serves: FR-1, FR-2, FR-3, FR-4
created: 2026-10-22
updated: 2026-10-22
---

# 交易闭环补口 · 架构设计 `serves: FR-1`

## 摘要 `serves: FR-1, FR-2, FR-3, FR-4`

- **问题**：三处断点——反思组包不唤醒、减仓批次不收敛、消息只通知不进待办。
- **方案**：全部复用既有框架接线：调度走 `scheduler_tasks + job_registry`、唤醒走 `AgentNotificationService.notify_agent → POST /wake`、待办走 `TodoService`、回执走 `FillSync → PlanService`；不新建通道、不改 schema。
- **影响面**：`qs_plan`（reflection_job / plan_service）、`qs_watch`（news_watch_service 新增联动模块）、`main.py` 组合根；无迁移。

## 背景与问题 `serves: FR-1, FR-2, FR-3, FR-4`

**需求来源**

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1 | 反思到点要叫醒 agent | `build_plan_jobs()` 注入既有 `notify_agent`，失败计 overdue |
| FR-2 | 部分成交要收敛减仓批次 | `PlanService.on_fill` 按累计比例匹配批次、退役规则、写事件 |
| FR-3 | 消息命中持仓要进待办并唤醒 | news/policy 扫描尾部新增 linkage：建 P1 待办（evidence 带 news_id）+ 唤醒 |
| FR-4 | 可回归可观测 | 三条读数（woken/batch/news todo）+ 两套件回归 |

**现状与代价**

- 反思：`reflection_job.py:39/44` waker 缺省 None；`main.py:141` 未注入 → 任务只落包。
- 批次：`plan_service.py:on_fill` 只有 `closing→holding` 绕回，无批次/rule 退役。
- 消息：`news_watch_service.py` 无 todo/wake 调用 → 消息→离场整链缺失。

**为什么是现在**

交易计划已上线（REQ-261021222905-6dff 归档），闭环缺这三处就无法产生真实执行/反思样本。

## 目标与非目标 `serves: FR-1, FR-2, FR-3, FR-4`

**目标**

- 盘后任务到点后 agent 收到唤醒（日志可查 woken 计数）；
- 部分成交后对应批次退役、`trading_plan_events.detail.batch` 可查；
- 持仓消息 critical 命中生成待办（`evidence->>'source'='news'`）并唤醒，24h 去重。

**非目标**

- 不自动下单（执行仍由 agent 终判，D-1）；改了会越过资损责任链；
- 不改消息分级词表；改了会与既有 critical/soft 口径分叉；
- 不新建调度/唤醒通道；新建会与 `scheduler_tasks + job_registry + /wake` 形成双源；
- 不改 watch_todos 表结构；改表会牵动待办状态机与既有查询。

## 方案总览 `serves: FR-1`

```text
scheduler_tasks(plan_reflect_daily 15:35) --> job_executor.get('plan_reflect_daily')
    --> PlanReflectionJob.run --> 组四输入材料包
        --> waker(plan, pack) = AgentNotificationService.notify_agent('plan_reflection', {...}, target='agent-dh')
            --> POST http://127.0.0.1:13080/wake  （失败 → overdue+1，不阻塞组包）

FillEvent(plan_id) --> FillSync --> PlanProgressPort --> PlanService.on_fill
    --> 累计卖出比例匹配批次 --> 退役 reduce 规则 + 事件(kind=fill, detail.batch)

news/policy 扫描命中 critical + 持仓
    --> NewsExitLinkage --> TodoService.create(P1, action_kind=rule_change, evidence={source:news,...})
    --> wake_todo_owner(todo)   （24h 去重：evidence->>'news_id' + symbol）
```

**关键概念**：`waker`（既有 notify_agent 的可注入包装）；批次进度（`detail.batch`）；消息待办（evidence.source=news）。

## 架构与依赖 `serves: FR-1, FR-2, FR-3`

- **模块划分**：`qs_plan/application/reflection_job.py`（waker 注入与调用）、`qs_plan/application/plan_service.py`（批次匹配）、`qs_watch/.../news_exit_linkage.py`（新增，消息→待办）、`main.py`（组合根注入）。
- **依赖方向**：qs_plan → qs_agenthub（notify_agent）；qs_watch → qs_agenthub（wake）与 qs_plan（进度端口，已有）。均为已声明单向边。
- **外部依赖**：agent-dh /wake（13080）；不可用时 overdue/日志降级，不静默。
- **与既有架构的差异**：无新增通道、无新表。

## 数据模型 `serves: FR-2, FR-3`

**不适用：不改表/schema**。复用既有字段：
- `trading_plan_events(kind='fill', detail={batch, trade_id, qty, remaining_qty})`；
- `watch_todos.evidence`（jsonb）承载 `{source:'news', news_id, title, hits, symbol, plan_id}`；
- `watch_rules.enabled=false` 表示批次退役（复用退役守卫，需 context 理由）。

## 接口设计 `serves: FR-1, FR-2, FR-3`

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `PlanReflectionJob(..., waker=fn)` | plan, pack | bool（是否唤醒成功） | 抛错 → overdue+1 | 新增可选参数，缺省 None=旧行为 |
| IF-2 | `match_reduce_batches(batches, sold_ratio)` | 批次列表, 累计卖出比例 | 应退役批次索引 | 比例非法 → ValueError | 新增纯函数 |
| IF-3 | `PlanService.on_fill(..., sold_ratio=0.0)` | 成交回执 | 计划状态 | 无批次 → degraded 事件 | 新增可选参数 |
| IF-4 | `link_news_to_todo(...)` | 消息+持仓+计划 | todo 或 None | 去重命中 → None | 新增函数 |
| IF-5 | `GET /api/watch/metrics` | — | 含 news_todo/woken 计数 | 缺数 → null | 既有端点扩展字段 |

**IF-1 PlanReflectionJob waker**

**语义**

组包成功后调用注入的 waker；签名 `waker(plan, pack) -> bool`。返回 False 或抛错均记 overdue 并继续下一张计划。

**错误码**

无 HTTP；失败只记日志与 `reflection_overdue_count+1`。

**兼容性**

waker 缺省 None = 只组包（旧行为），向后兼容。

**IF-2 match_reduce_batches**

**语义**

纯函数：按 `sell_ratio` 累计，返回累计比例 ≤ sold_ratio 的批次下标（跨批成交一次退役多批）。

**错误码**

sold_ratio 不在 [0,1] → ValueError；batches 为空 → 返回空列表。

**兼容性**

新增纯函数，无调用方依赖。

**IF-3 PlanService.on_fill 扩展**

**语义**

新增 `sold_ratio` 可选参数；>0 时匹配批次并退役对应 reduce 规则、写 fill 事件；重复回执按 trade_id 幂等。

**错误码**

无匹配批次 → 事件 `degraded=true`，不退役。

**兼容性**

缺省 0.0 = 仅推进状态（旧行为）。

**IF-4 link_news_to_todo**

**语义**

critical 命中持仓/计划标的 → 建 P1 待办（evidence 含 news_id/source=news）→ 调 `wake_todo_owner`；24h 内同 news_id+symbol 已存在则跳过。

**错误码**

待办创建失败 → 记日志不抛（扫描继续）；`out_of_scope` 账户 → 跳过并留痕。

**兼容性**

新增函数，仅在扫描尾部调用（开关默认开）。

**IF-5 metrics 扩展**

**语义**

`/api/watch/metrics` 增加 `news_todos_today`、`reflection_woken_today`（读当日计数），缺数据返回 null。

**错误码**

无（只读）。

**兼容性**

additive 字段，旧消费者不受影响。

## 备选方案 `serves: FR-1, FR-2, FR-3, FR-4`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 复用调度/唤醒/待办既有框架，仅接线 | 无双源、无迁移 | 依赖既有通道可用性 | — |
| B | 新建反思专用推送服务 | 解耦 | 第二套唤醒通道，维护翻倍 | 与「单一唤醒主路」纪律冲突 |
| C：什么都不做 | 保持断点 | 零成本 | 反思/批次/消息三条链永远不闭环 | 用户已立项（D-1） |

## 四风险与证据 `serves: FR-1, FR-2, FR-3, FR-4`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 三处断点真的影响闭环吗 | 代码行号 + 今天验证记录 | 已验证 |
| 可用性 | 既有 /wake 能被复用吗 | `watch_channels.py:158` 直连 /wake 为已验证主路 | 已验证 |
| 可行性 | 批次比例匹配够用吗 | 部分成交/合单下按笔不可靠（设计推演） | 部分 |
| 商业可行性 | 无新依赖/新表 | — | 已验证 |

**未验证项的补课计划**：批次匹配 → 用 30%/50%/80% 成交用例证伪；上线首日看事件表。

## 失败模式与回滚 `serves: FR-1, FR-2, FR-3, FR-4`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| /wake 不可达 | agent-dh 挂/端口不通 | 反思不唤醒 | overdue 计数、日志 | 修复 agent-dh；任务下周期重试 | 用户 |
| 批次匹配错 | 合单成交跨批 | 退役错批 | 事件表对账 | 手工恢复规则 enabled + 修正事件 | 用户 |
| 消息待办风暴 | 词表误召 | 待办堆积 | watch_todos 当日计数 | 关 `NEWS_TODO_ENABLED=false` | 用户 |
| 去重失效 | 并发扫描 | 重复待办 | 唯一性查询 | 补唯一索引（后续） | 用户 |

- **开关**：`NEWS_TODO_ENABLED`（默认 true）、`PLAN_REFLECTION_WAKE_ENABLED`（默认 true）；
- **回滚演练**：quant_test 关闭开关跑一遍，确认行为退回旧态；
- **不可逆动作**：无。

## 跨关注点 `serves: FR-1, FR-2, FR-3, FR-4`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 无新暴露面 | 复用内网 /wake 与既有鉴权 |
| 隐私与合规 | 不适用 | — |
| 成本 | 无新资源 | 消息待办仅在 critical 命中时产生 |
| 可观测性 | 三个计数 + 事件表 | metrics 扩展与日志 |
| 性能与容量 | 扫描尾部 O(持仓数) | 复用 sidecar 节流 |
| 文档与支持 | 指南补三节 | `docs/guides/trading-plan.md` 增「消息→离场」「批次进度」 |

## 交付拆分与里程碑 `serves: FR-1, FR-2, FR-3, FR-4`

（仅方向性里程碑，不含任务 DAG。）

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 反思唤醒 | waker 注入 + 测试 | test_reflection_job 绿 | 本窗口 | 第 1 批 |
| M2 批次收敛 | 匹配函数 + on_fill 扩展 | test_plan_batch_convergence 绿 | 本窗口 | 第 2 批 |
| M3 消息联动 | linkage + 去重 + 唤醒 | test_news_exit_linkage 绿 | 本窗口 | 第 3 批 |
| M4 收口 | 回归 + 读数 | 两套件无新增红 | 本窗口 | 第 4 批 |

## 需求追溯 `serves: FR-1, FR-2, FR-3, FR-4`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | 方案总览 / 接口设计 IF-1 | TC-1, TC-2 | woken_today |
| FR-2 | 数据模型 / IF-2/IF-3 | TC-3~TC-5 | 事件 detail.batch |
| FR-3 | 方案总览 / IF-4 | TC-6~TC-8 | news_todos_today |
| FR-4 | 跨关注点 | TC-9 | 两套件回归 |

## 常见问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 消息待办噪音——只在 critical 且持仓命中时建单 |
| 6 个月后会成为什么负担 | 批次匹配规则复杂化——保持纯函数 + 事件留痕 |
| 流量涨 10 倍先坏在哪里 | 消息扫描尾部 O(持仓) 查询——有 24h 去重与 sidecar 节流 |
| 谁半夜被叫起来 | 无人——全链路无自动下单 |
| 数据错了怎么修 | 规则/待办均可在看板人工修正；事件表留痕 |
| 这个决定错了多久能发现 | 首日读数（woken/batch/news）+ 回归套件 |

## 开放问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 消息待办挂在哪个账户 | A 持仓账户；B 计划账户 | 本窗口 | 已决：A（持仓是事实源） |
| waker 目标 agent | A 固定 agent-dh；B 按计划账户路由 | 本窗口 | 已决：B（复用 route_owner） |

## 附录 `serves: FR-1, FR-2, FR-3, FR-4`

- **相关文档**：requirement.md（本需求）、`docs/guides/trading-plan.md`
- **评审记录**：待设计确认门落章
- **变更历史**：v1.0（2026-10-22）
