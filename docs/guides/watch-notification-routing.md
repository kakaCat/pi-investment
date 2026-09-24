# 盯盘通知路由与回执指南

> REQ-260924104605-ad0a（2026-09-24 上线）· 面向开发/运维 · 与需求目录 ops-note.md（换群/回滚/排障操作）配套

## 1. 投递链一句话

WatchEngine 到 NotificationFacade（**唯一通知入口**）到 WatchChannelPolicy 定
`variables["os_channel"]` 逻辑频道码，再到 AgentChannel 到 Agent OS :8080
`POST /api/v1/notifications/send`，再到 `public.notification_channels`（code 到 webhook，
**每次发送实时读库无缓存**）到飞书群。

quantsys-v2 侧只认逻辑频道码、**不认 webhook**；换群/回滚只改 Agent OS 渠道表，
应用代码零改动。

## 2. 频道码（FR-1 分群）

| 组 | 频道码 | 目标群 |
|---|---|---|
| 盯盘 10 码 | watch_symbol / watch_market / entry_signal / exit_manage / risk_stop / position_ops / rule_governance / market_state / system_ops / decision_inbox | 盯盘专用群 |
| 原共享 3 码 | alerts / reports / trading | 原共享群（不动） |

- 触发卡：按 WatchChannelPolicy 解析（intent/scope/金额门）到盯盘码之一。
- 回执卡：timeout 或 P0 到 **risk_stop**；其余到 **watch_symbol**（`route_channel()`，
  落库 channel 标签与真实路由同码——FR-1 前的 alerts/reports 标签已废弃）。

## 3. 触发链路（FR-2）

- L1 直发：`send_with_fallback('agent','feishu')`——agent 优先，Agent OS 不可达
  降级直飞书兜底（**不丢消息**），metadata 如实标注 degraded/degraded_reason
  （agent_os_unreachable=运行时故障 / agent_channel_unregistered=配置装配问题）。
- L2 行动层：经 wake 通道投 target_agent，失败降级飞书并标注。
- **注册闸门是投递专用开关 `AGENT_OS_NOTIFY_ENABLED`**（默认 True）——
  `AGENT_OS_ENABLED` 是 ADR-002 调度权开关，与通知注册无关（2026-09-24 曾误耦合
  导致 agent 优先链路静默失效，已拆）。

## 4. 回执（FR-8 / FR-14）

- 三类：escalate（升级即回执）/ timeout（超时回执）/ result（处置后回执，FR-14
  三要素：结论/原因/后续意见）；suppressed（抑噪）即时发。
- **聚合**：SLA 巡检一轮 begin_group() 到 flush_grouped()，escalate/timeout 同
  kind 合成**一张聚合卡**（batch id `batch:<kind>:<yyyymmddHHMM>`，逐条落库同批）；
  result 必须即时（处置结论不等聚合）。
- 幂等：per-todo payload_digest 去重，同周期重复巡检不重发。
- 卡片格式：名称（代码）优先（StockNameResolver 批量解析，缺失标「名称缺失」
  不编造）；归属账户每卡必显（无账户=通用观察）；频道码等内部字段不外露（FR-12）。

## 5. 兼容与降级纪律

- 无 watch_level 的存量通知仍走旧 WatchTriggeredFormatter 渲染（七段结构），
  有级别才走四级模板——新老通知共存不互踩。
- 发送失败必须抛错：ReceiptService 据 sender 是否抛错记 sent/failed，**绝不假成功**。
- R-013：数据缺失标「缺失」并说明，禁止编造。

## 6. 运维入口

- 渠道体检/换群/回滚/探针：agent-dh/docs/requirements/REQ-260924104605-ad0a/scripts/watch-channel-drill.sh
- 操作手册（含 SQL 与排障）：同目录 ops-note.md

