---
title: qs_watch 项目说明书（L1）
status: living
updated: 2026-10-22
owners: [qs_watch]
tags: [manual]
---

# qs_watch 项目说明书（L1）

> 金字塔 L1：把各需求归档时沉淀的认知收在一处，agent/新人先读这里，再按需下钻 L2 领域篇与 L3 需求档案。

## 项目定位

qs_watch 是盘中守门员：盯盘规则、触发判定、分级通知、待办闭环、复盘回填。
它**不执行交易**——执行由 WatchEngine 的规则触发 + agent 终判下单完成。

## 包边界

- 只依赖 kernel/market_data/notification/trading/ops/agenthub；
- 不直连 broker、不产生订单；
- 计划层（qs_plan）在它之上：计划编译成规则，watch 执行。

## 交易计划与反思闭环

2026-10-22 归档（REQ-261021222905-6dff）新增 `qs_plan` 独立包，把「交易计划」立为一等实体：

- **计划 → 规则**：PlanCompiler 把 spec 幂等编译成带 `plan_id` 的 watch_rules（role=entry/stop_loss/reduce）；
  持仓真值直写 `position_state`，执行仍归 WatchEngine。
- **成交回写**：`execute_trade` 成交后发 FillEvent（带 plan_id）→ FillSync 收敛待办 → 计划状态推进
  （清仓→closed、部分成交→续持）；事件失败不反噬成交。
- **反思闭环**：盘后/周六定时任务组四输入材料包（计划修改历史/错过机会/盈利/亏损），
  agent 按五问作答落库；提案经「预览→确认→apply」改计划并重编译。
- **三层分离**：计划（操作）/反思（认知）/进化（沉淀）；进化层只写 agent_knowledge，不碰在跑计划。
- **双端工具**：agent-dh（投资脑）与 agent-ts 通过 `trading_plan` 工具调用，不手敲 REST。
- **闭环接线（2026-10-22 补齐）**：盘后反思经既有 `notify_agent → /wake` 真正叫醒 agent；
  减仓部分成交按累计比例逐批退役规则并写 `kind=fill` 事件（重放幂等、无匹配降级）；
  持仓消息 critical 命中走既有 `NewsTodoBridge` 建 P1 待办并唤醒 owner；
  `GET /api/watch/metrics` 暴露 `news_todos_today` / `reflection_woken_today` 两个当日读数
  （缺数为 null）。

详细用法见 `docs/guides/trading-plan.md`；原始材料见 `docs/requirements/REQ-261021222905-6dff/`。

## 盯盘引擎 V2（持仓驱动 · 2026-10-23）

V2 是在 V1 之外并存的第二套盯盘主流程，**持仓驱动**：统一取价前置 → 按持仓状态分
`position_engine`（持仓四操作）/ `unpositioned_engine`（买入/观察）两模块判定 →
失效判定全票覆盖 → 触发按 10 次循环路由 → 发 agent / 发飞书两独立通道。

**新增认知（与 V1 的关键差异）**
- **取价前置**：所有激活票每拍都取价，失效/到期/持仓都是对比维度而非取价前过滤器
  （V1 的持仓门在取价前，导致未持仓票没有作废范围）
- **持仓是对比输入而非过滤器**：先取价再分类，未持仓票同样过失效判定
- **触发 10 次循环**（per-rule 独立）：循环首发发 agent 判断 → 2~9 不处理 →
  第 10 次直通盯盘群并归零；每日 16:35 定时任务全部清零（次日首发仍 agent）
- **文案两独立文件**：`agent_prompts`（提示词）/ `feishu_templates`（模板），
  按「持仓状态 × 判定类型」组织，两文件互不 import
- **通道两独立文件**：`notify_agent` / `notify_feishu` 互不 import（单测断言）
- **止损豁免失效判定**：保护线穿越是触发不是失效；但止损不豁免循环节奏

**开关**：`WATCH_V2_ENABLED`（默认关，V1 行为不变）；回滚即置 false。

**数据**：watch_rules 新增 trigger_channel / process_state / cycle_count / engine；
watch_triggers 新增 engine（影子期双写对账）。

详细用法见 `docs/guides/watch-v2-engine.md`；原始材料见
`docs/requirements/REQ-261022235419-2299/`。

## 关键约束

- 盯盘引擎唯一宿主 = FastAPI 5001 lifespan；
- 业务定时任务归 v2 调度（ADR-004）；
- 任何规则修改必须留痕（watch_rule_changes），agent 变更必须带 decision_audit_id。
