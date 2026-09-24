---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-8, FR-13, FR-14]
---

# 架构设计：盯盘通知改版（REQ-260924104605-ad0a）

## 总体架构（serves: FR-1, FR-2, FR-3）

所有盯盘出口收敛为一条路径：WatchEngine/ReceiptService → NotificationFacade（唯一入口，
铁律不变）→ AgentChannel（os_channel=逻辑频道码）→ Agent OS 网关 → notification_channels
表按 code 取 webhook → 物理群。飞书降级（send_with_fallback 既有机制）兜底，不丢消息。
10 个盯盘逻辑频道 → 盯盘群（…60d879，FR-1 已落地）；alerts/reports/trading 原群不动。

## FR-2 方案裁定：direct 路径改走网关（方案 A）（serves: FR-2）

notification_facade.py:243 的 direct 分支由 preferred_channels=['feishu'] 改为
send_with_fallback(notification, 'agent', 'feishu')——与 L2 之外的 agent 模式同路径。
选 A 不选 B（FeishuChannel 多 webhook 化）的理由：路由知识只在 AgentChannel 一处、
配置只在渠道表一处；B 会把「频道→webhook」复制进渠道层，两处真相必漂移。
代价：L0/L1 触发多一跳 :8080 依赖——由既有 fallback 吸收，降级在 metadata 如实标注。

## 回执路由接线（serves: FR-3）

send_watch_receipt/send_watch_alert（watch_channels.py）改为经 facade 发送时在
variables 携带 os_channel=逻辑频道码：超时/P0 → risk_stop 频道（盯盘群内高优先级），
其余回执 → watch_symbol。不再经 send_card 的 urgency 兜底落 alerts/reports。

## 模板架构：意图驱动骨架按级别控密度（serves: FR-4, FR-13）

渲染仍在 infrastructure/notification/formatters/watch_level_templates.py（纯函数、
结构化输入纪律不变）。WatchCardItem 扩展可选字段（见 data-model.md）；display 改为
「名称（代码）」。render_p0/p1/p2 重写为骨架式，render_p1 判重（N=1 不重复）、
多项=首项完整+其余一行。回执侧名称由 SLA 巡检批量解析注入（FR-13，见下）。

## 回执聚合架构（serves: FR-8, FR-13）

聚合只发生在**投递层**，去重键不变（per-todo payload_digest 沿用——这是与需求
FR-8 字面「周期级聚合键」的有意识偏离，理由：若 digest=（kind,period,有序 todo 集合），
同周期晚到的新 todo 会改变 digest 导致整卡重发，反而制造重复；per-todo 去重 +
批量投递同等保证「不重不漏」且每条回执可追溯）。
实现：WatchSlaJob.run_once 收集本轮新发出的回执（escalate/timeout 分组），循环结束后
每组发一张聚合卡；delivery_status/message_id 按组回写各行；空组不发（AC-8.3）。
名称解析：run_once 开头对 overdue 集合一次联查 symbol→stocks.name（StockNameResolver
端口注入，未命中 → 「名称缺失」标注，不臆造）。

## 处置结论回执接线（serves: FR-14）

TodoService 增加可选 receipt_service 依赖（None=不发，测试进程安全）：
close() 仓储收敛成功后调 ReceiptService.result(updated_todo, terminal=...)，
updated_todo 携带 close_reason/next_condition/action_kind。render_receipt 的 result
分支重写为三要素文案（结论/原因/后续意见）。路由层 watch_todo_async.py:141 的
receipt=None 填充为真实回执结果。幂等沿用 (todo_id,'result',digest)。

## 测试策略概述（serves: FR-2, FR-4, FR-8, FR-14）

模板纯函数单测（骨架顺序/判重/名称缺失降级/无「频道：」）；路由单测（os_channel
直透、fallback 标注）；聚合单测（3 条→1 卡/幂等/空不发）；FR-14 接线单测
（close→result 触发、三要素、I4 联动）；既有 tests/notification/ 回归。详见 test-cases.md。
