# t-adb9c3 接线 direct 渠道路由与回执 os_channel、补 rule_id 传递

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
接线 direct 渠道路由与回执 os_channel、补 rule_id 传递

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
运行 pytest quantsys-v2/tests/notification/ 通过且断言：direct 分支 agent 优先、os_channel 直透 AgentChannel；Agent OS 不可达时降级飞书且 metadata 包含降级标注；回执 payload 的 os_channel 与 risk_stop/watch_symbol 一致；sender 抛错时 delivery_status 返回 failed；既有用例不红

## 实施方案（implementation）
①facade direct 分支改 fallback 链并在 metadata 标注降级；②variables 加 rule_id（从 condition/action_hint 链路取，缺失传 None）；③watch_channels 两函数 payload 加 os_channel 并经 facade 写入 variables

## 上游产出摘要（dependsSummary）
- 定契约：WatchCardItem 扩展 + StockNameResolver 端口 + render_receipt 签名

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-24T04:58:12.612Z，窗口 session-2bf7941d-3f18-4423-9c83-35f60ea4f5b9）

路由接线完成：L0/L1 direct 触发不再直飞书，统一走「agent 优先、飞书降级」——os_channel 逻辑频道码直透 AgentChannel 路由到盯盘群，Agent OS 挂了降级直飞书且 metadata 如实标 degraded；回执经 facade.send_watch_receipt 携带 os_channel（timeout/P0→risk_stop，其余→watch_symbol），正文不再外露「频道：」；rule_id 从规则一路传到模板。

### 完成项

- facade direct 分支改 send_with_fallback + 降级标注（FR-2）
- facade.send_watch_receipt + watch_channels os_channel 映射（FR-3/FR-12）
- rule_id 全链路传递（FR-10）；_deliver payload 补 level
- 路由测试 9 例（tests/notification/test_watch_receipt_routing.py）
- 96 例全绿；application/api 层失败经主检出基线对照为既有红，非本次引入

### 改动文件

- `quantsys-v2/application/notification/notification_facade.py`
- `quantsys-v2/application/services/watch_engine/watch_channels.py`
- `quantsys-v2/application/services/watch_engine/receipt_service.py`
- `quantsys-v2/application/services/watch_engine/notifier.py`
- `quantsys-v2/tests/notification/test_watch_receipt_routing.py`
- `quantsys-v2/tests/notification/test_watch_target_routing.py`
- `quantsys-v2/tests/notification/test_watch_templates.py`

### 下一步

t4 回执聚合投递 + 名称批量解析 + 时间格式修复

---
