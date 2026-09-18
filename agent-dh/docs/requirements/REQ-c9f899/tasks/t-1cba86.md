# t-1cba86 按级别投递模板与路由修复

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
按级别投递模板与路由修复

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
运行 python -m pytest tests/notification/test_watch_templates.py 通过；断言四类模板首行包含「标的+现价+动作」；断言金额门与 target_agent 分支被命中

## 实施方案（implementation）
infrastructure/notification/formatters 新增四类模板；修 WatchChannelPolicy 注入 account_total；接通 target_agent；实现 P2/P3 聚合器

## 上游产出摘要（dependsSummary）
- 级别判定与账户路由纯函数

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T17:10:04.068Z，窗口 session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98）

按级别飞书模板（P0 红/P1 橙/P2 蓝/P3 汇总）+ 金额门死代码修复 + 聚合器；target_agent 经取证确认底层不支持，如实报告未假装接通（留 TODO t12）。主 agent 复核：文件范围精确、测试独立重跑通过。

### 完成项

- infrastructure/notification/formatters/watch_level_templates.py（新增）：纯函数模板层；WatchCardItem 结构化输入 → 四类卡片；resolve_level_template（未知级别兜底 P2 且显式标注）；render_watch_message 统一入口；aggregate_watch_items（账户×标的×时段，窗口/上限/级别可配）；payload 复用既有 FeishuFormatter.format_card，不重复实现卡片结构
- watch_channel_policy.py：金额门取数契约写清 + amount_threshold_yuan()（未知/非法/非正 → 门关闭、不抛错）
- notification_facade.py（仅 watch 方法）：send_watch_triggered 新增 account_total_yuan 并传入策略（修死代码）；target_agent 写入 metadata + 响应显式报告 unsupported_in_notification_channel（附原因与 TODO）
- tests/notification/test_watch_templates.py（新增 17 用例）
- 子代理变异测试 4 处均能变红（金额门不接线/ P2 首行去动作 / 聚合器忽略窗口 / 不报告 target_agent），改回后全绿——证明非烟雾测试
- 主 agent 独立复核：①文件范围精确（仅 4 个声明路径）②pytest tests/notification/test_watch_templates.py → 17 passed ③通知域既有测试 34 passed ④全量 watch → 288 passed（271+17，零新增失败）
- 主 agent 核验其「既有无关红」判断：DonchianChannelStrategy 2 例在**主工作区 HEAD 代码**同样红 → 判断属实，非本次引入
- 如实报告的未接通项（非缺陷，是底层限制）：AgentChannel 只认 os_channel；Agent OS SendRequest 无 per-agent 字段；FeishuChannel 忽略 target_agent

### 改动文件

- `quantsys-v2/infrastructure/notification/formatters/watch_level_templates.py`
- `quantsys-v2/domain/notification/policies/watch_channel_policy.py`
- `quantsys-v2/application/notification/notification_facade.py`
- `quantsys-v2/tests/notification/test_watch_templates.py`

### 下一步

留给 t12 接线（子代理已如实标注，不可视为已完成）：①notifier 调用处传 account_total_yuan（否则生产链路上金额门仍关闭）②把按级别模板注册进渠道（现在仍是可单测渲染层，FeishuChannel 走旧 formatter）③若要真接 target_agent：优先走 AgentNotificationService 的 /wake 路径，或扩展 Agent OS SendRequest

---
