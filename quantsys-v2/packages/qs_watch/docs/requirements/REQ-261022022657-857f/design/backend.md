---
title: 交易闭环补口 · 后端设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: docs/requirements/REQ-261022022657-857f/requirement.md
serves: FR-1, FR-2, FR-3, FR-4
created: 2026-10-22
updated: 2026-10-22
---

# 交易闭环补口 · 后端设计 `serves: FR-1`

## 摘要 `serves: FR-1, FR-2, FR-3, FR-4`

- **问题**：三处接线落在哪些文件、怎么装配、失败怎么降级。
- **方案**：6 个服务级改动点（S-1~S-6），全部复用既有框架；无新增进程/线程。
- **影响面**：qs_plan 2 文件、qs_watch 3 文件、main.py 组合根。

## 背景与问题 `serves: FR-1, FR-2, FR-3, FR-4`

**需求来源**

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1~FR-4 | 可执行的后端改动点 | S-1~S-6 |

**现状与代价**

现状断点位置见 architecture.md 背景节；不定服务级改动点则实施会重复探测。

**为什么是现在**

拆分按 S-x 定卡。

## 目标与非目标 `serves: FR-1, FR-2, FR-3, FR-4`

**目标**

- 每处改动有文件、职责、失败降级、开关；无新线程/新表。

**非目标**

- 不重构 news_watch_service 扫描主体；重构会牵动既有 15 分钟 sidecar。

## 方案总览 `serves: FR-1`

```text
S-1 build_plan_jobs(waker)       # 组合根注入 notify_agent
S-2 PlanReflectionJob.run        # 调 waker + overdue
S-3 batch_matcher               # 纯函数
S-4 PlanService.on_fill          # 批次退役 + 事件
S-5 news_exit_linkage           # 消息→待办→唤醒 + 去重
S-6 metrics 扩展                # 两个计数
```

**关键概念**：组合根装配、纯函数、JSONB 契约。

## 架构与依赖 `serves: FR-1`

- **模块划分**：见下 S 表。
- **依赖方向**：qs_plan → qs_agenthub；qs_watch → qs_agenthub（既有白名单）。
- **外部依赖**：agent-dh /wake。
- **与既有架构的差异**：无。

## 数据模型 `serves: FR-2`

同 data-model.md（无迁移）。

## 接口设计 `serves: FR-1`

同 interfaces.md（IF-1~IF-6）。

## 服务级设计 `serves: FR-1, FR-2, FR-3, FR-4`

| 编号 | 改动点 | 文件 | 职责 | 失败降级 | 开关 |
|---|---|---|---|---|---|
| S-1 | 组合根注入 waker | `adapters/inbound/fastapi_app/main.py` | 构造 notify_agent 包装传入 build_plan_jobs | 注入失败 → 日志 + 不唤醒 | PLAN_REFLECTION_WAKE_ENABLED |
| S-2 | 反思任务调用 waker | `packages/qs_plan/qs_plan/application/reflection_job.py` | 组包后调 waker；失败 overdue+1 | 异常捕获不中断批次 | 同上 |
| S-3 | 批次匹配纯函数 | 新增 `packages/qs_plan/qs_plan/domain/plan/batch_matcher.py` | 累计比例 → 批次下标 | 比例非法 ValueError | — |
| S-4 | on_fill 批次退役 | `packages/qs_plan/qs_plan/application/plan_service.py` | 退役 reduce 规则 + 写事件 + 状态 | 无批次记 degraded | — |
| S-5 | 消息联动 | 新增 `packages/qs_watch/qs_watch/application/services/watch_engine/news_exit_linkage.py` | 建 P1 待办 + 唤醒 + 24h 去重 | 待办异常记日志继续 | NEWS_TODO_ENABLED |
| S-6 | metrics 扩展 | `adapters/inbound/fastapi_app/routes/watch_async.py` | 两个当日计数 | 缺数 null | — |

**S-1 组合根注入 waker**

**职责**：`build_plan_jobs(waker=...)`；waker = `AgentNotificationService.notify_agent` 的薄包装（event=`plan_reflection`，data 含 plan_id/period/四段摘要）。

**失败降级**：装配异常只记日志，任务仍按旧行为组包。

**开关**：`PLAN_REFLECTION_WAKE_ENABLED`（默认 true）。

**S-2 反思任务调用 waker**

**职责**：每张到期计划组包成功后调用 waker；False/异常 → `bump_overdue`；成功 → `set_review_due`。

**失败降级**：单计划失败不中断整批。

**S-3 批次匹配**

**职责**：`match_reduce_batches(batches, sold_ratio) -> list[int]`；按 `at_pct` 排序累计。

**失败降级**：比例越界 ValueError；空批次返回 [].

**S-4 on_fill 批次退役**

**职责**：读 `remaining_qty` 与持仓算 `sold_ratio`（由 FillSync 传入）→ 匹配 → 逐批 `retire`（enabled=false + context 理由）→ 写 `kind=fill` 事件；剩余 0 → closing→closed。

**失败降级**：无匹配批次写 `degraded_fill` 事件，不退役。

**S-5 消息联动**

**职责**：在 `news_watch_service` 扫描结果尾部调用；critical 且标的在持仓/激活计划 → 建 P1 待办（evidence 契约）→ `wake_todo_owner`；24h 同 news_id+symbol 跳过。

**失败降级**：`out_of_scope` 跳过留痕；异常记日志继续。

**开关**：`NEWS_TODO_ENABLED`（默认 true）。

**S-6 metrics 扩展**

**职责**：`/api/watch/metrics` 增加 `news_todos_today`、`reflection_woken_today`。

**失败降级**：查询异常返回 null（不用 0 冒充）。

## 备选方案 `serves: FR-1, FR-2, FR-3, FR-4`

| 方案 | 一句话说明 | 优点 | 代价 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 6 个服务级改动 | 面小可回滚 | 无 | — |
| B | 独立微服务 | 解耦 | 新进程/新运维 | 过度设计 |
| C：不做 | — | — | 闭环断 | 需求要求 |

## 四风险与证据 `serves: FR-1, FR-2, FR-3, FR-4`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 改动覆盖断点 | S 表逐条映射 FR | 已验证 |
| 可用性 | 复用既有装配 | main.py 已有 build_plan_jobs 调用 | 已验证 |
| 可行性 | 无新依赖 | — | 已验证 |
| 商业可行性 | — | — | 已验证 |

**未验证项的补课计划**：sold_ratio 由谁算是实施首要确认点（已决 FillSync）。

## 失败模式与回滚 `serves: FR-1, FR-2, FR-3, FR-4`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| waker 装配失败 | 服务未起/异常 | 反思不唤醒 | 日志 | 修组合根；开关关 | 本窗口 |
| 退役失败 | DB 异常 | 批次重复喊 | 事件表 | 人工恢复 enabled | 用户 |
| 待办风暴 | 词表误召 | 待办堆积 | metrics | 关 NEWS_TODO_ENABLED | 用户 |

- **开关**：2 个（见 S 表）；
- **回滚演练**：quant_test 关开关跑套件；
- **不可逆动作**：无。

## 跨关注点 `serves: FR-1, FR-2, FR-3, FR-4`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 复用内网通道 | /wake 既有鉴权 |
| 隐私 | 不适用 | — |
| 成本 | 无新增资源 | — |
| 可观测性 | S-6 + 事件表 | — |
| 性能与容量 | 扫描尾部 O(持仓) | sidecar 节流 |
| 文档与支持 | 指南补三节 | trading-plan.md |

## 交付拆分与里程碑 `serves: FR-1, FR-2, FR-3, FR-4`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | S-1/S-2 | TC-1/2 绿 | 本窗口 | 第 1 批 |
| M2 | S-3/S-4 | TC-3~5 绿 | 本窗口 | 第 2 批 |
| M3 | S-5 | TC-6~8 绿 | 本窗口 | 第 3 批 |
| M4 | S-6 + 回归 | TC-9 + 两套件 | 本窗口 | 第 4 批 |

## 需求追溯 `serves: FR-1, FR-2, FR-3, FR-4`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | S-1/S-2 | TC-1/2 | woken |
| FR-2 | S-3/S-4 | TC-3~5 | batch |
| FR-3 | S-5 | TC-6~8 | news todo |
| FR-4 | S-6 | TC-9 | metrics |

## 常见问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 消息待办噪音——critical + 持仓双条件 |
| 6 个月后负担 | linkage 与词表耦合——独立模块 |
| 流量涨 10 倍 | 扫描尾部查询——去重 + 限量 |
| 谁半夜被叫起来 | 无人 |
| 数据错了怎么修 | 事件/待办人工修正 |
| 错了多久发现 | 首日读数 |

## 开放问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| sold_ratio 计算位置 | A FillSync；B PlanService 自算 | 本窗口 | 已决：A |

## 附录 `serves: FR-1, FR-2, FR-3, FR-4`

- **相关文档**：architecture.md / interfaces.md / data-model.md / test-cases.md / use-cases.md
- **评审记录**：待确认门落章
- **变更历史**：v1.0
