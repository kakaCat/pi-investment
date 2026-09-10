# v2 通知链路 DDD 对接审计与修复（Agent OS 优先、飞书降级）

- 窗口：w-23c70356（investor）
- 日期：2026-09-11 00:50 ~ 01:15
- 触发：用户指出同一飞书群里两条消息观感不一致（「✅ 每日任务完成：watch_rule_health」纯文本 vs「ℹ️ 数据质量告警」卡片），并明确架构意图：**v2 通知优先调用 Agent OS，OS 不通再直接调飞书；且 DDD 通知域已建好，需检查 v2 是否真的对接**。

## 一、审计结论（证据均可复核）

**DDD 通知域确实存在且策略写对了，但「OS 优先」链路三处断裂，实际效果等同于「v2 直连飞书」。**

| 层 | 位置 | 现状（实测/代码） |
|---|---|---|
| domain | `domain/notification/policies/notification_policy.py` | 12 类通知映射 `['agent','feishu']`（OS 优先、飞书降级）；AGENT_REMINDER/AGENT_REPORT 仅 agent —— 设计正确 |
| domain | `domain/notification/services/notification_service.py::send()` | 按优先级顺序试投，失败自动降级下一渠道（降级逻辑真实存在，L129-165） |
| application | `application/notification/notification_facade.py` | 9 处方法**硬编码** `preferred_channels=['feishu']` → `select_channels()` 第一步短路，策略失效（实测：默认 `['agent','feishu']` vs 带 preferred `['feishu']`） |
| application | `notification_factory.py:172` | `AgentChannel(agent_url=settings.scheduler.agent_os_url, token=None)` |
| config | `settings.py:72` | `AGENT_OS_URL` 默认 `http://localhost:3002`；qv2 `.env` 未设置该变量；实测 3002 无监听，Agent OS 实际在 **8080** |
| infrastructure | `agent_channel.py:96` | POST `{url}/wake`（旧 wake-channel 契约）；实测 `AgentChannel.send()` → `success=False 无法连接到 Agent: http://localhost:3002` |
| 契约 | Agent OS | 真实通知入口 `POST http://localhost:8080/api/v1/notifications/send`（body channel/title/content/urgency/metadata；resp `{"log_id","success","error","message_id"}`，渠道码 alerts/reports/trading）。v2 全仓 **0 处**调用；routing 只有 2 处 POST 不存在的 `/wake` |
| legacy | `daily_jobs_bootstrap.py:331/540` | 直接 `FeishuNotificationService().send_text/send_card` → `requests.post` webhook，绕过 DDD（即用户看到的 ✅ 纯文本消息来源；作业定义见 `:678`，2026-09-10 16:30:27 跑 1s → 显示「0.0 分钟」） |
| 死代码 | `application/notification/legacy_adapters.py` | 桥接层早已写好（转门面），但全仓 0 引用 —— 迁移只做了一半 |

历史佐证：`agent-ts/.pi-invest/experience/experience-base.json`（2026-08-11）记录过同类事故「3002 端口被抢占…wake 进程启动即崩，3002 无人监听，后端唤醒全部 connection refused 静默失败」——同类链路曾静默死亡。

## 二、修复（P0 + P1 + P2，用户选定全量）

**P0 接通 OS 优先链路**
1. `infrastructure/notification/channels/agent_channel.py`：`send()` 改为 `POST {agent_os_url}/api/v1/notifications/send`，请求体含 `channel`（渠道码映射：交易类→trading；风险/系统告警或 high/critical→alerts；其余→reports；可由 `variables['os_channel']` 覆盖）、`title`、`content`、`urgency`、`metadata`（自动带 source/notification_id/notification_type，过滤不可序列化值）；healthcheck 打 `/health`；错误语义沿用（业务失败/HTTP 错误/连接失败→error；读超时→timeout「可能已送达」）。
2. `settings.py`：`agent_os_url` 默认 3002 → `http://localhost:8080`；qv2 `.env` 增补 `AGENT_OS_URL=http://localhost:8080`（.env 被 gitignore，未提交）。
3. `notification_factory.py`：token 可经 `AGENT_OS_TOKEN` 注入（OS 当前不校验，保留扩展位）；补 `import os`（**该遗漏由单测抓到：缺 import 会让门面构造 NameError，进而全量通知失效**）。

**P1 让策略真正生效**
- 移除 `notification_facade.py` 中 8 处 `preferred_channels=['feishu']`（send_stop_loss_alert / send_take_profit_alert / send_daily_report / send_weekly_report / send_ml_train_notification / send_text / send_card / send_alert）。
- **保留**两处设计性指定：`send_agent_reminder` 的 `['agent']`（策略本就是 agent-only），以及 `send_watch_triggered` direct 模式的 `['feishu']`（RFC 009 盯盘双通道：direct 直推 / agent 唤醒），二者非缺陷。

**P2 旧路径收敛 + 死代码启用**
- `daily_jobs_bootstrap._send_feishu()`：改经 `NotificationFacade.send_card`（首行作标题、其余作正文；🚨/❌ 开头按 high），作业 ▶️/✅/🚨 通知与其余系统通知观感统一为卡片。
- `_job_event_calendar_check()`：`FeishuNotificationService()` → `get_notification_facade()`。
- `application/services/feishu_service.py`：`send_text`/`send_card` 收敛为桥接层（`get_legacy_feishu_service()` → 门面），该类报表/告警方法（send_daily_report/send_weekly_report/send_alert/send_premarket_report）最终都汇聚到 send_card，故一并收敛；**删除**已无调用方的私有 `_send()`（裸 webhook POST），该类不再保留可用的直连通道。
- `legacy_adapters.py` 由此**被真正启用**（此前是 0 引用死代码）。

## 三、验证

1. **真实投递（v2→OS→飞书）**：门面 `send_card` → 日志 `通知发送成功 channel=agent delivered=True notification_id=notif_192bcdcf69a5431a`，OS 返回 `log_id=6b718dcc-6875-4216-9c89-e17701b19b2c`，渠道码 `alerts`；OS 侧落库可查：`public.notification_logs` → `alerts | sent | 【验证】v2→Agent OS→飞书 链路接通 | 2026-09-11 01:06:22`（2026-09-11 01:06，psql 实查）。
2. **降级真实生效（故障注入）**：构造 `AgentChannel(agent_url='http://127.0.0.1:59999')` + 真实 FeishuChannel 的 NotificationService → `通知发送成功 channel=feishu delivered=True`（01:06:23），即 agent 失败后自动降级飞书。
3. **渠道健康**：门面 `healthcheck()` 修复前 `{'feishu': True, 'agent': False}` → 修复后 `{'feishu': True, 'agent': True}`；`AGENT_OS_URL(effective)=http://localhost:8080`。
4. **单测**：新增 `tests/infrastructure/test_agent_channel_agent_os.py`（10 项：渠道码映射/契约/业务失败/HTTP 错误/连接失败/读超时语义/healthcheck/策略顺序/preferred 短路仍可用）+ `tests/services/test_feishu_service_facade_delegation.py`（7 项：旧服务桥接、异常不抛出、报表汇聚、门面不再强制飞书、agent_reminder 仅 agent、盯盘 direct 模式不被误伤）。连同既有 `tests/domain/notification`（31 项）共 **48 passed**。
5. **回归**：scheduler/notification/jobs 相关 + `tests/services` 全量 = **741 passed / 24 failed / 26 errors / 8 skipped**；失败项全部与被改文件无关且这些文件在工作区未被任何改动触碰（`git status` 为空）：`factor_analysis_service` 缺 `base64` import、`WatchNotifier.__init__() got multiple values for 'ws_url'`、DB fixture `signals.action_type` NOT NULL / `PendingRollbackError`、`strategy_execution_service` 缺 `SignalORMRepository` 等，均为既有问题。
6. **服务生效**：qv2 重启（pid 79598，health ok）。

## 四、残留风险与后续（本次未处理，需决策）

1. **`utils/feishu_notifier.py` 是另一条直连旁路**：`FeishuNotifier` 自行读 `FEISHU_WEBHOOK_URL` 并 POST，被 `application/strategies/v13_use_case.py`、`live_trading/simulation_trader.py` 使用 —— 属实盘/策略路径，本次未纳入（范围与验证成本都不同，建议单独立项）。
2. **读超时语义**：`ChannelResult.timeout` 记 success=True（防重复），意味着 OS 若「连通但挂起」，通知会标为「可能已送达」且**不触发飞书降级**。建议为 agent 渠道单列策略（告警类宁重复勿丢失）或在 OS 侧加超时上限。
3. **`AgentNotificationService`（`/wake` → `AGENT_API_URL=http://127.0.0.1:13080` + token）语义是「唤醒 Agent」而非「发通知」，实测该端点存在（无 token 401），**保持不动**；如需统一到 OS 需先厘清唤醒与投递的边界。
4. **OS 渠道码为 3 个固定值**（alerts/reports/trading，见 `public.notification_channels`）：v2 侧映射规则写死在 AgentChannel，如需按业务细分应改为配置。

## 五、留痕

- 决策审计：decision_audit(record，risk_control，entity task/232 之外的 v2 通知链路)
- 记忆：memory_write（namespace=experience）
- 通知：feishu_notify（R-010）
- 提交：本轮仅提交本次改动文件（见 commit）。


## 六、残留清理（第二轮：用户指令「残留 直接删除」）

原第五节列的 3 项残留，按「能删就删」处理：

1. **直连旁路已删除**（残留①）：删除 `utils/feishu_notifier.py`（自行 `requests.post` 飞书 webhook 的平行实现）与 `scripts/test_feishu_notification.py`（其唯一用途是手测裸 webhook，随实现一并作废）。调用方全部迁移到门面：
   - `application/strategies/v13_use_case.py`：`create_notifier_from_config(config)` → `get_notification_facade()`
   - `application/strategies/strategy_executor.py::_create_notifier`：不再读 config 的 feishu 段，直接返回门面（保留参数签名）
   - `application/risk/intraday_risk_service.py`：`self.feishu_notifier` → 门面（其 `send_text`/`send_risk_alert` 调用点不变）
   - `live_trading/simulation_trader.py`：删除 `if self.feishu_notifier:` 死门（该属性**全仓从未被赋值**，进入即 AttributeError；本类真正的发送对象是 `self.notification_facade`，见 156/1607 行），改由方法内部自守卫
   - `tests/test_strategy_service_unified.py`：去掉对已删除符号 `create_notifier_from_config` 的 patch（该文件另有既有的模块属性漂移失败，与本轮无关）
2. **门面补齐两个方法**（CLAUDE.md：新通知类型必须先扩门面）：`NotificationFacade.send_rebalance_notification(report_data)`（`NotificationType.REBALANCE`）与 `send_risk_alert(report_data)`（`NotificationType.RISK_ALERT`，HIGH），两者都不设 `preferred_channels` → 交给 NotificationPolicy 走 OS 优先。
3. **超时抑制已删除**（残留②）：`AgentChannel` 读超时由 `ChannelResult.timeout()`（success=True，会导致**跳过飞书降级**）改为 `ChannelResult.error()` → 如实降级下一渠道。取舍：OS 网关实测 <1s，>timeout 属病态；告警类「漏发比重复更严重」，故宁可降级可能重复。
4. **残留③（`AgentNotificationService` 的 `/wake`）保留**：其语义是「唤醒 Agent 处理事件」而有别于「投递通知」，被 7 个服务使用（watch_engine/intraday_monitor/daily_orchestrator/market_monitor_scheduler/strategy_rotation_engine/scheduler_tasks/agent_scheduler_tool），端点实测存在（无 token 401）。删除会打断盯盘唤醒链路——这不是残留，是另一条语义通道。

验证（本轮增量）：
- 单测：通知相关 **68 passed**（新增 3 项：旁路模块不可导入、rebalance 通知、risk 告警 HIGH；超时用例改为断言降级）。
- 真实 import：`v13_use_case` / `strategy_executor` / `intraday_risk_service` / `simulation_trader` / `notification_facade` 全部 IMPORT_OK；门面新方法存在性实测 True。
- 全仓 grep `utils.feishu_notifier | FeishuNotifier | create_notifier_from_config` = 仅剩注释与文档字符串，无代码引用。
- qv2 重启，health ok。

