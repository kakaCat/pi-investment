---
title: 交易闭环补口 · 测试用例设计
status: draft
owner: 本窗口（lead）
reviewers: 用户（最终决策人）
prd: docs/requirements/REQ-261022022657-857f/requirement.md
serves: FR-1, FR-2, FR-3, FR-4
created: 2026-10-22
updated: 2026-10-22
---

# 交易闭环补口 · 测试用例设计 `serves: FR-1`

## 摘要 `serves: FR-1, FR-2, FR-3, FR-4`

- **问题**：三处接线需要可证伪用例，覆盖成功/失败/去重/幂等。
- **方案**：9 条用例，假件为主（沿用 watch/plan 测试模式），DB 断言用 quant_test。
- **影响面**：新增 3 个测试文件 + 1 个 metrics 断言。

## 背景与问题 `serves: FR-1, FR-2, FR-3, FR-4`

**需求来源**

| 需求编号 | 原始诉求 | 本设计如何回应 |
|---|---|---|
| FR-1~FR-4 | 可执行判据 | TC-1~TC-9 |

**现状与代价**

无对应用例；不加用例则三处接线只能靠日志碰运气。

**为什么是现在**

拆分阶段按用例定卡。

## 目标与非目标 `serves: FR-1, FR-2, FR-3, FR-4`

**目标**

- 每条 FR 至少一条用例；失败与幂等各有断言。

**非目标**

- 不做真实 agent 会话端到端（人工验收）；做了需要 LLM 环境，CI 不稳定。

## 方案总览 `serves: FR-1`

```text
tests/plan/test_reflection_job.py（扩展 TC-1/2）
tests/plan/test_plan_batch_convergence.py（TC-3~5）
tests/plan/test_news_exit_linkage.py（TC-6~8）
tests/plan/test_metrics_ext.py（TC-9）
```

**关键概念**：假件注入（waker/repo/notifier）。

## 架构与依赖 `serves: FR-1`

- **模块划分**：tests/plan 下新增文件。
- **依赖方向**：直接 import qs_plan/qs_watch 生产代码。
- **外部依赖**：quant_test 库（联动用例）。
- **与既有架构的差异**：无。

## 数据模型 `serves: FR-1`

用 data-model.md 的 JSONB 契约做断言。

## 接口设计 `serves: FR-1`

| 编号 | 接口 | 输入 | 输出 | 失败与错误 | 兼容性 |
|---|---|---|---|---|---|
| IF-1 | `pytest tests/plan -q` | — | 退出码 | 失败=1 | — |

**IF-1 pytest tests/plan**

**语义**

全部 plan/补口用例入口。

**错误码**

1 = 有用例失败。

**兼容性**

新增文件不影响既有。

## 功能测试用例 `serves: FR-1, FR-2, FR-3, FR-4`

**TC-1 waker 被调用一次 `validates: FR-1`**

注入记录型 waker，跑到期计划 → 每张调用一次，review_due_at 前移。

**TC-2 waker 失败计 overdue `validates: FR-1`**

waker 抛错 → 该计划 overdue+1，其余计划继续。

**TC-3 卖 1/3 退役首批 `validates: FR-2`**

sold_ratio=0.33 → 仅批次 0 退役；事件 detail.batch=0；计划仍 holding。

**TC-4 卖完全批退役并 closed `validates: FR-2`**

sold_ratio=1.0 → 全批退役；remaining=0 → closed。

**TC-5 批次匹配边界与幂等 `validates: FR-2`**

比例 0/0.8/1.0 三档断言；同一 trade_id 重放 → 不重复退役/事件。

**TC-6 消息 critical 建待办并唤醒 `validates: FR-3`**

假件持仓 + critical 消息 → TodoService.create 被调用（P1/rule_change/evidence.source=news）+ wake 一次。

**TC-7 24h 去重 `validates: FR-3`**

同 news_id+symbol 再扫 → 不建第二条。

**TC-8 非持仓不建待办 `validates: FR-3`**

无持仓/无计划 → 只通知，不建 todo。

**TC-9 metrics 扩展读数 `validates: FR-4`**

插入 news 待办后 /api/watch/metrics 返回 news_todos_today ≥1；缺数据 null。

## 备选方案 `serves: FR-1, FR-2, FR-3, FR-4`

| 方案 | 一句话说明 | 优点 | 缺点 | 为什么未选 |
|---|---|---|---|---|
| A（选用） | 假件 + quant_test 断言 | 快、稳 | 不覆盖真实 /wake | — |
| B | 起 agent-dh 真会话 | 端到端 | 慢、依赖 LLM | 放人工验收 |
| C：不做 | — | — | 无回归 | — |

## 四风险与证据 `serves: FR-1, FR-2, FR-3, FR-4`

| 风险类型 | 判断问题 | 现有证据 | 结论 |
|---|---|---|---|
| 价值 | 覆盖三处断点 | FR 映射 | 已验证 |
| 可用性 | 假件模式可复用 | 既有 117 例 plan 测试 | 已验证 |
| 可行性 | 新文件可独立跑 | — | 已验证 |
| 商业可行性 | — | — | 已验证 |

**未验证项的补课计划**：真实 /wake 由上线首日日志验证。

## 失败模式与回滚 `serves: FR-1, FR-2, FR-3, FR-4`

| 失败场景 | 触发条件 | 用户可见影响 | 检测手段 | 回滚动作 | 决策人 |
|---|---|---|---|---|---|
| 用例互相污染 | 共享账户/符号 | 偶发红 | 独立 ACC/SYM | 隔离夹具 | 本窗口 |

- **开关**：无；**回滚**：不适用；**不可逆**：无。

## 跨关注点 `serves: FR-1, FR-2, FR-3, FR-4`

| 关注点 | 结论 | 依据与措施 |
|---|---|---|
| 安全 | 用 quant_test | 根 conftest 守卫 |
| 隐私 | 不适用 | — |
| 成本 | <10s | — |
| 可观测性 | TC 编号=FR 对照 | — |
| 性能 | 不适用 | — |
| 文档 | 本文件即索引 | — |

## 交付拆分与里程碑 `serves: FR-1, FR-2, FR-3, FR-4`

| 里程碑 | 内容 | 出口判据 | 负责人 | 目标日期 |
|---|---|---|---|---|
| M1 | TC-1/2 | 绿 | 本窗口 | 第 1 批 |
| M2 | TC-3~5 | 绿 | 本窗口 | 第 2 批 |
| M3 | TC-6~9 | 绿 | 本窗口 | 第 3 批 |

## 需求追溯 `serves: FR-1, FR-2, FR-3, FR-4`

| 需求编号 | 设计节 | 测试用例 | 指标 |
|---|---|---|---|
| FR-1 | TC-1/2 | TC-1, TC-2 | woken |
| FR-2 | TC-3~5 | TC-3/4/5 | batch |
| FR-3 | TC-6~8 | TC-6/7/8 | news todo |
| FR-4 | TC-9 | TC-9 | metrics |

## 常见问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 回答 |
|---|---|
| 最可能被投诉什么 | 假件与真实 /wake 行为差异——按接口契约断言 |
| 6 个月后负担 | 用例随链路增加——按 FR 归属 |
| 流量涨 10 倍 | 不适用 |
| 谁半夜被叫起来 | CI 提交者 |
| 数据错了怎么修 | 假件内存态 |
| 错了多久发现 | 每次 CI |

## 开放问题 `serves: FR-1, FR-2, FR-3, FR-4`

| 问题 | 选项 | 负责人 | 截止 |
|---|---|---|---|
| 是否加真实 /wake 集成用例 | A 不加（人工）；B 加 | 本窗口 | 已决：A |

## 附录 `serves: FR-1, FR-2, FR-3, FR-4`

- **相关文档**：interfaces.md
- **评审记录**：待确认门落章
- **变更历史**：v1.0
