---
title: 交易闭环补口 · 数据模型设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: docs/requirements/REQ-261022022657-857f/requirement.md
serves: FR-2, FR-3
created: 2026-10-22
updated: 2026-10-22
---

# 交易闭环补口 · 数据模型设计 `serves: FR-2`

## 摘要 `serves: FR-1, FR-2, FR-3, FR-4`

- **问题**：批次进度与消息待办需要落库口径，但不应改表。
- **方案**：复用 `trading_plan_events.detail` 与 `watch_todos.evidence` 两个 JSONB 字段；无迁移。
- **影响面**：零 schema 变更；仅写入格式契约。

## 背景与问题 `serves: FR-1, FR-2, FR-3, FR-4`

**需求来源**

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-2 | 批次进度可见 | events.detail.batch 契约 |
| FR-3 | 消息待办可查/去重 | watch_todos.evidence.source/news_id 契约 |

**现状与代价**

两字段均 JSONB 且已在生产使用（events 已有 kind/detail；todos 已有 evidence），加结构不牵动表。

**为什么是现在**

拆分前定死字段格式，避免实现各自发明键名。

## 目标与非目标 `serves: FR-1, FR-2, FR-3, FR-4`

**目标**

- `detail.batch`、`evidence.source/news_id` 键名与类型定死；查询样例可跑。

**非目标**

- 不加列/索引（去重靠 24h 查询 + 后续按需加索引）；加了会牵动迁移与回滚。
- 不加 CHECK 约束（JSONB 值域应用层把守）。

## 方案总览 `serves: FR-2`

```text
trading_plan_events: kind=fill, detail={batch:int, trade_id:int, qty:int, remaining_qty:int, degraded?:bool}
watch_todos.evidence: {source:'news', news_id:'...', title:'...', hits:[...], symbol:'...', plan_id:int|None}
```

**关键概念**：JSONB 契约（只增键不改语义）。

## 架构与依赖 `serves: FR-2`

- **模块划分**：qs_plan（写 events）、qs_watch（写 todos）。
- **依赖方向**：无新依赖。
- **外部依赖**：无。
- **与既有架构的差异**：无。

## 数据模型 `serves: FR-2, FR-3`

**不新增表/列**。既有字段使用契约：

| 表 | 字段 | 写入方 | 契约 |
|---|---|---|---|
| trading_plan_events | kind | PlanService | `fill`（批次进度）、`degraded_fill`（匹配失败） |
| trading_plan_events | detail | PlanService | `{batch, trade_id, qty, remaining_qty}`，batch 为 0-based 批次下标 |
| watch_todos | evidence | NewsExitLinkage | `{source:'news', news_id, title, hits, symbol, plan_id}` |
| watch_todos | level/action_kind | NewsExitLinkage | `P1` / `rule_change` |

- **查询样例**：`select detail from quant.trading_plan_events where kind='fill' order by id desc limit 5;`
  `select id, level, evidence->>'news_id' from quant.watch_todos where evidence->>'source'='news' order by id desc limit 5;`
- **迁移与回填**：无。
- **生命周期**：与既有行一致（不新增归档逻辑）。

## 接口设计 `serves: FR-2`

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | 写 events detail | dict | — | 写入失败记日志 | 追加键，兼容旧消费者 |

**IF-1 写 events detail**

**语义**

按上表契约写入；旧消费者忽略未知键。

**错误码**

无 HTTP；DB 异常由调用方兜底。

**兼容性**

JSONB 只增键。

## 备选方案 `serves: FR-1, FR-2, FR-3, FR-4`

| 方案 | 一句话说明 | 优点 | 缺点 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | JSONB 契约 | 零迁移 | 查询需 ->> | — |
| B | 加 batch 列 + 索引 | 查询快 | 迁移 + 回滚成本 | 当前量级不需要 |
| C：不做 | — | — | 进度不可见 | 需求要求 |

## 四风险与证据 `serves: FR-1, FR-2, FR-3, FR-4`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 字段够用吗 | 需求四输入与批次定义 | 已验证 |
| 可用性 | 查询可行吗 | 生产 events 已有 detail | 已验证 |
| 可行性 | 无迁移 | — | 已验证 |
| 商业可行性 | — | — | 已验证 |

**未验证项的补课计划**：无。

## 失败模式与回滚 `serves: FR-1, FR-2, FR-3, FR-4`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 键名漂移 | 实现自行改名 | 查询不到 | 契约测试 | 按本表修正 | 本窗口 |

- **开关**：无；
- **回滚演练**：不适用（无 schema）；
- **不可逆动作**：无。

## 跨关注点 `serves: FR-1, FR-2, FR-3, FR-4`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 不适用 | — |
| 隐私与合规 | 不适用 | — |
| 成本 | 零 | — |
| 可观测性 | 两条 SQL 样例 | 上表 |
| 性能与容量 | JSONB 查询仅当日行 | 限量 order by id desc |
| 文档与支持 | 指南引用 | — |

## 交付拆分与里程碑 `serves: FR-1, FR-2, FR-3, FR-4`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | 契约落地 | 测试断言键名 | 本窗口 | 第 2/3 批 |

## 需求追溯 `serves: FR-1, FR-2, FR-3, FR-4`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-2 | 数据模型 | TC-4 | detail.batch |
| FR-3 | 数据模型 | TC-7 | evidence.news_id |

## 常见问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | JSONB 查询慢——限量 + 后续按需加索引 |
| 6 个月后负担 | 键名膨胀——本表即契约 |
| 流量涨 10 倍 | JSONB 扫描变慢——加表达式索引 |
| 谁半夜被叫起来 | 无人 |
| 数据错了怎么修 | 事件可人工修正/补写 |
| 错了多久发现 | 查询样例每日可跑 |

## 开放问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 是否为 news_id 加表达式索引 | A 暂不加；B 本轮加 | 本窗口 | 已决：A（量级小，先观测） |

## 附录 `serves: FR-1, FR-2, FR-3, FR-4`

- **相关文档**：architecture.md、interfaces.md
- **评审记录**：待确认门落章
- **变更历史**：v1.0
