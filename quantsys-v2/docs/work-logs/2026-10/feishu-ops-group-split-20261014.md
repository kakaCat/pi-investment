# 飞书通知分群：系统消息 ≠ 股票消息

**日期**: 2026-10-14
**触发**: 用户裁定 —— 「调度看门狗 / 每日任务完成这类消息改发到飞书 `7aa7ebdd-…` 群里，
不要把【实盘账户·保护线恢复】【盘前例程】这些股票消息混到一起」
**结论一句话**: 全部系统类消息改走**独立运维群**（新 webhook），股票类消息路由**一行未动**。

---

## 一、问题取证：为什么会混在一起

所有消息此前都汇到**同一个 webhook**（`b24be3a5-…`，即通用群），只是入口不同：

| 来源 | 入口 | 落点（改前） |
|---|---|---|
| `scripts/scheduler_watchdog.py` | 直发 webhook（`FEISHU_WEBHOOK_URL` 默认值） | 通用群 |
| v2 每日任务开始/完成/失败、失败残留、新鲜度守卫 | `daily_jobs/alerting._send_feishu` → 门面 `send_card` | Agent OS `alerts` 渠道 → 通用群 |
| v2 数据质量 / 财报时效性 / 模型新鲜度 / 探活 | 门面 `send_card` / `send_text` | 同上 |
| **股票类**：盘前例程、实盘账户·保护线 | agent-dh investor agent → `feishuWebhooks['*']` | 通用群（**同一个群**） |
| 盯盘触发/回执 | 门面 `send_watch_receipt` + `os_channel` | 盯盘群（`c990fd00-…`，本来就分开） |

实测证据：`public.notification_channels` 里 `alerts / trading / reports` 三条都指向 `b24be3a5-…`；
`public.notification_logs` 中 `alerts` 渠道已发 469 条、最近一条 2026-10-14 22:36。
即「调度消息」与「股票消息」共用同一个物理群，是**配置层面的必然**，不是偶发。

> ❌ **被否掉的方案**：把 `notification_channels.alerts` 整条指向运维群。
> 因为 `RISK_ALERT` / `SYSTEM_ALERT` 都走 `alerts`，而 `intraday_risk_service` 的
> **盘中止损止盈**正是 `send_text`（= `SYSTEM_ALERT`）——整条改道会把股票风控消息一起搬进运维群。
> 故改为**逐调用点显式改道**。

## 二、改动

**新落点**：`https://open.feishu.cn/open-apis/bot/v2/hook/7aa7ebdd-be9e-47f9-be45-ba9c772499c9`
（已用 `curl` 实测 `{"code":0,"msg":"success"}`，确认为可直发的机器人 webhook，非 chat_id）

| 文件 | 改动 |
|---|---|
| `infrastructure/notification/channels/feishu_channel.py` | `FeishuChannel(..., name=)` —— 渠道名可配（默认 `'feishu'`，行为不变）。**必须有**：`NotificationService` 用 `{get_name(): channel}` 建索引，两个飞书群同名会互相顶掉 |
| `infrastructure/config/settings.py` / `.env` | 新增 `FEISHU_WEBHOOK_OPS` |
| `application/notification/notification_factory.py` | 注册第二实例 `name='feishu_ops'`；未配 `FEISHU_WEBHOOK_OPS` 时**兜到通用群并打 warning**（显式降级、不丢告警） |
| `application/notification/notification_facade.py` | 新增 `send_ops_card` / `send_ops_text`：`preferred_channels=['feishu_ops']`，**不走 Agent OS**（OS 的 `alerts` 落通用群），渠道缺失时返回 `False`，**绝不静默改投** |
| `daily_jobs/alerting.py` | `_send_feishu` → `send_ops_card`（覆盖每日任务开始/完成/失败、失败残留、新鲜度守卫） |
| `application/jobs/model_jobs.py` | 模型新鲜度 → `send_ops_card` |
| `tools/health_probe.py` | 探活 → `send_ops_text` |
| `infrastructure/jobs/data_quality_check_job.py` | 质量告警 → `send_ops_card` |
| `infrastructure/jobs/financial_timeliness_check_job.py` | 财报时效性 → `send_ops_card` |
| `application/services/trading_day_guard.py` | 交易日降级 → `send_ops_card` |
| `scripts/scheduler_watchdog.py` | 落点改为 `WATCHDOG_FEISHU_WEBHOOK` > `FEISHU_WEBHOOK_OPS` > 内置默认值；**故意不读** `FEISHU_WEBHOOK_URL`（它指向通用群，读了就等于混群） |
| `~/Library/LaunchAgents/com.pi-investment.scheduler-watchdog.plist` | 显式设 `WATCHDOG_FEISHU_WEBHOOK`；并**首次留档**到 `deployment/launchd/`（此前只存在于 `~/Library/LaunchAgents`，仓库里查不到） |

**分群判据**：消息主体是「系统/数据链路/任务/引擎的健康与执行状态」→ 运维群；
消息主体是「个股/市场/交易/盯盘行情」→ 原群。

## 三、边界（本次**没有**做，别当成已解决）

1. **agent-os 自身的系统告警**（如 `notification_retry_worker` 的「N 条通知卡在 pending」）
   仍走 `alerts` → 通用群。要收进去得改 agent-os 的渠道配置，本次未动（用户抱怨的两个例子
   都在 v2 / 看门狗侧）。
2. **agent-dh investor agent 的股票消息**路由未动（`feishuWebhooks['*']` 仍指向通用群）——
   正是期望行为：股票消息留在原群。
3. `application/services/scheduler_tasks_models.py` 的 **ML 训练通知**未改道（走
   `send_ml_train_notification`）。它同属系统类，留给后续按需收口。

## 四、验证（实测）

- 真机装配检查：`channels = ['agent','feishu','feishu_ops']`，两个 webhook 不同；
  普通 `SYSTEM_ALERT` 选择结果 `['agent','feishu']`（**未**选中运维渠道），
  `preferred_channels=['feishu_ops']` 选择结果 `['feishu_ops']`。
- 三个投递腿各实测一次成功：原始 webhook（curl `code:0`）／门面 `send_ops_card`
  （`feishu_ops` 送达）／看门狗 `send_feishu`（`sent=True`）。
- 看门狗 plist 重新 `bootout`+`bootstrap`，`launchctl print` 确认 env 已生效；
  手工跑一轮：`v2_up=True os_up=True issues=104 new=0 resolved=0`（去重生效、无噪音）。
- v2 API `launchctl kickstart -k` 重启，`/api/health` 返回 `status: ok`。
- 回归测试：新增 `tests/notification/test_ops_channel_split.py`（8 例）、
  `scripts/tests/test_scheduler_watchdog_ops_group.py`（4 例）全绿；
  受影响面 151 例全绿。
- ⚠️ **既有失败（与本次无关，改动前即存在）**：`tests/test_freshness_guard.py` 3 例、
  `test_feishu_service_facade_delegation.py::test_watch_direct_mode_keeps_feishu`、
  `test_scheduled_jobs_account_value.py::TestHandleFactorCompute`、
  `tests/jobs/test_watch_interval_jobs.py` 2 例（fake 门面缺 `send_watch_receipt`）。
  用 `git stash` 单独回退本次全部改动复跑，**同样这 7 例失败**，确认是既有问题。
