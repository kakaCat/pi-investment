---
requirement_refs: [FR-1, FR-4, FR-8, FR-13, FR-14]
---

# 数据模型：盯盘通知改版（REQ-260924104605-ad0a）

## notification_channels（已变更，无 schema 改动）（serves: FR-1）

仅 UPDATE 10 行 config.webhook：risk_stop / decision_inbox / entry_signal / exit_manage /
position_ops / watch_symbol / watch_market / market_state / rule_governance / system_ops
→ …60d879（2026-09-24 已执行并实测投递成功）。alerts/reports/trading 保持 …172829。
回滚 = 改回原值。完整 webhook 只存 DB，不进 git。

## WatchCardItem 扩展（代码内 dataclass，向后兼容）（serves: FR-4, FR-13）

新增可选字段（缺省 None/空串，模板隐藏该行，绝不臆造）：
intent(str) / stage(str) / purpose(str) / plan_full(str) / stop_loss(float) /
take_profit(float) / validity_days(int) / source(str) / rule_id 已有。
display 语义变更：「代码 名称」→「名称（代码）」；name 缺失 → 纯代码 + 「名称缺失」。

## watch_receipts（无 schema 变更）（serves: FR-8, FR-14）

列复用约定：payload_digest 仍为 per-todo 去重键（不变）；message_id 在聚合卡场景
记录**批次卡标识**（同批各行同值，格式 batch:<kind>:<yyyymmddHHMM>），
result 回执记录单卡 message_id。kind 沿用 CHECK 集（escalate/result/timeout/suppressed）。

## 名称解析数据源（serves: FR-13）

quant.stocks（symbol→name）只读联查；新端口 StockNameResolver.resolve_batch(symbols)
→ dict[symbol, name|None]。SLA 巡检每轮一次批量调用；无逐条查询、无写操作。

## watch_todos（只读，无变更）（serves: FR-13, FR-14）

回执渲染消费既有列：id/symbol/account/level/flow_state/due_at/close_reason/
next_condition/action_kind。close_reason/next_condition 由既有 close API 写入
（ignored 必填 next_condition，I4），本需求不改写入侧。

## 迁移与兼容（serves: FR-1, FR-8）

无 DDL、无数据回填。兼容：模板新旧并存由 watch_level 有无决定（既有机制）；
ReceiptService.result 未接线前 close 行为不变（receipt=None 语义保持到接线完成）。
回滚路径：配置层改回 webhook；代码层 revert 即恢复旧渲染与旧投递。
