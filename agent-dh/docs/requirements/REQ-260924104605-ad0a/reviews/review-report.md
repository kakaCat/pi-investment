# 评审报告：盯盘通知改版（REQ-260924104605-ad0a）

> 2026-09-24 · 自评审（实施窗口）· 对照 requirement.md v2.3 验收标准逐条

## 结论

**建议通过验收。** 全部 7 任务 done，五步集成验证真实执行通过，89 例回归全绿，
两个联调发现的真实缺陷已修复并带钉案。遗留事项均为非阻断（见 §4）。

## 1. 需求条款覆盖核对

| 条款 | 落点 | 状态 |
|---|---|---|
| FR-1 专用 webhook 分群 | notification_channels 10 行盯盘频道→…60d879；drill 脚本 assert 钉死 | ✅ 实测 |
| FR-2 agent 优先+降级标注 | facade.send_watch_triggered direct 分支 send_with_fallback；metadata degraded/degraded_reason | ✅ 实测（停 :8080 演练） |
| FR-3 回执 os_channel 路由 | watch_channels→facade.send_watch_receipt 直透；timeout/P0→risk_stop | ✅ 实测 |
| FR-8 超时/升级聚合一卡 | ReceiptService.begin_group/flush_grouped；实测 3 超时→1 卡同 batch | ✅ 实测 |
| FR-10 模板显示真实规则号 | rule_id 透传进 variables；缺失显示「手工」 | ✅ 单测 |
| FR-12 频道码不外露 | 卡片正文无「频道：」；os_channel 只进 variables | ✅ 单测+实测卡 |
| FR-13 名称（代码） | StockNameResolver 批量解析；缺失标「名称缺失」不编造 | ✅ 单测+实测卡 |
| FR-14 处置结论三要素 | close_and_receipt→result 卡：结论/原因/后续意见 | ✅ 实测（待办 39） |

## 2. 联调发现的真实缺陷（已修复）

1. **ADR-002 调度旗误伤通知注册**（严重）：start-launchd.sh 的 AGENT_OS_ENABLED=false
   同时关掉 AgentChannel 注册，「agent 优先」链路自始静默失效（主渠道 None 跳过、无日志）。
   修复：拆出 agent_os_notify_enabled；主渠道未注册响亮告警 + fallback_cause 如实标注；
   facade 区分 agent_channel_unregistered / agent_os_unreachable。
   钉案：tests/notification/test_agent_channel_registration.py 4 例。
2. **回执落库标签与落点漂移**：result 回执 channel 记 'reports' 实际落盯盘群。
   修复：route_channel() 落库标签=真实路由（timeout/P0→risk_stop，其余→watch_symbol）。
   钉案：tests/watch/test_close_receipt.py 新增用例。

## 3. 测试证据

- 回归：tests/notification/ + tests/watch/ = **89 passed**（主检出，2026-09-24 14:35）
- 兼容：无 watch_level 的存量通知仍走旧渲染（test_legacy_render_compat 5 例）
- 集成五步：见 tests/test-evidence.md（投递日志 id/时间戳/巡检统计）
- 回滚演练：探针 ef464627（原群 sent）、e8a7c137（盯盘群 sent）

## 4. 遗留事项（非阻断）

- 降级直飞书落的是 FEISHU_WEBHOOK_URL 配置群（原共享群）——兜底语义本就是「不丢消息」，
  但严格说降级时盯盘消息会落原群；如需降级也落盯盘群，可把 FEISHU_WEBHOOK_URL 换成盯盘群
  webhook（运维决策，已写入 ops-note §5）。
- 存量 8 条超时待办的旧回执 channel 标签为历史值（alerts），新产生的回执已是真实路由码；
  不回刷历史行。
- watch_price_history 批量插入 CardinalityViolation 为既有缺陷（与本需求无关，另行立项）。

## 5. 风险与回滚

- 回滚路径：drill rollback 一条命令（10 行→原群），已实测；代码回滚 = revert 两个 fix
  commit + merge commit。
- 服务重启后行为已验证（触发/降级/close/聚合四链路均实测）。
