---
req: REQ-261004154902-a7cd
kind: design
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10
title: V13 链路可信性设计——让「声明 = 记录 = 实际 = 有人知道」
---

# V13 链路可信性设计

> **一句话**：把「失败了没人知道、没干也报成功、账本自相矛盾」这三类问题，收敛到**一个结果契约 + 一条可见性出口**上；
> 判据是「制造一次失败，它必须响亮」。

```
        ┌─────────────── 现状（三处断点） ───────────────┐
        │                                                │
 日检 ──┤ run_daily_check ──✗丢弃──> rebalance() ──✗吞──> 通知方法不存在(AttributeError)
        │        │                                    │
        │        └──> strategy_service: status='success' ✗假绿
        │
 撮合 ──┤ orchestrator.tick ──> execute_pending_orders ──✗崩在取数──> 挂单永久 pending（41 天）
        │
 停摆 ──┤ 进程死 / 任务漏跑 ──✗无人知──> 唯一失败出口 = AgentOS:8080（不可达）

        ┌─────────────── 目标形态（四个出口都指向人） ───────────────┐
 结果契约 RunOutcome(ok/reason/error) ──> scheduler_runs.result+error
                                     ──> FailureSink ──> NotificationFacade ──> 飞书（降级链）
 判定真源 trading_calendar ──> 休市不开火、复市不跳过
 进程外探活 + 「该跑没跑」盘点器 ──> 停摆/漏跑主动外发
 账本校验（累计买卖净额）──> 超卖当场拦下并留痕
```

## 0. 目标与判据（serves: FR-1, FR-2）

- **serves: FR-1, FR-2**
- 目标：任何自动链路的一次运行，其「是否执行 / 是否成功 / 为什么没成功」三问必须能从
  `scheduler_runs.result` 与运行日志中**直接读出**，且失败必须**主动外发**。
- 判据（可证伪）：注入一次失败（因子为空 / 模型抛错 / 挂单取数抛错）后，
  ①返回值 `ok=False` 且带 `reason`；②`scheduler_runs.status='failed'`（不是 success）；
  ③飞书侧收到一条告警。三条缺一即未达成。

## 1. 架构总览（serves: FR-1, FR-2, FR-9）

- **serves: FR-1, FR-2, FR-9**
- 新增一个**应用层小模块**（不新增子系统、不新增表）：
  - `application/observability/run_outcome.py`：`RunOutcome` 值对象 + `ok` 判定唯一实现；
  - `application/observability/failure_sink.py`：`report_failure(source, reason, error, severity, context)`
    → 结构化日志（loud）+ `NotificationFacade`（既有 agent→feishu 降级链）。
- 既有模块只做「接线」改造，**不改算法**：
  - `live_trading/simulation_trader.py`：`run_daily_check` / `rebalance` 返回 `RunOutcome` 语义；
    把误缩进在 `if __name__ == '__main__':` 里的 `_send_rebalance_notification` /
    `_format_rebalance_content` **移回类体**。
  - `application/services/strategy_service.py`：三态映射（success / skipped / failed）。
  - `application/services/account_trading_service.py`：撮合批量不中断 + 过期/搁浅处置。
  - `application/services/trading_day_guard.py`：判定真源换日历。
  - `infrastructure/scheduler/apscheduler_service.py` + 库内任务行：时刻口径一致。
- **为什么这样做**：三处断点的共同病因是「失败被当成局部返回值，而不是一等公民」。
  把「失败」提升为契约字段 + 唯一出口，可以一次治好 FR-1/2/7/8/9，且不需要新表（守住 B3 边界）。

## 2. 接口与数据契约（serves: FR-1, FR-2, FR-7）

- **serves: FR-1, FR-2, FR-7**

### 2.1 `RunOutcome`（新增，应用层值对象）（serves: FR-1, FR-2）

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `executed` | bool | 必填 | 是否真的进入了执行分支（**保持既有字段名**，兼容 API/看板） |
| `ok` | bool | 派生 | `ok = executed and error is None`；**唯一**由 `run_outcome.py` 计算 |
| `action` | str | 枚举 | `rebalance` / `stop_loss` / `hold` / `skipped` |
| `reason` | str | 受控枚举 | `not_trading_day` / `not_due` / `market_closed` / `model_not_loaded` / `factor_empty` / `rebalance_failed` / `stop_loss_failed` / `no_cash` / `oversell_blocked` / `pending_expired` / `ok` |
| `error` | str \| None | ≤2000 | 异常原文（截断），无错则 None |
| `detail` | dict | 可 JSON | 既有附加信息（如 `days_to_next`、`pending_order_id`） |

- `to_dict()` 输出**超集**：既有调用方读的 `executed` / `reason` / `action` 字段名不变（向后兼容）。
- 错误语义：`ok=False` 且 `reason` 属「环境坏」类（`model_not_loaded` / `factor_empty` /
  `rebalance_failed` / `oversell_blocked`）→ 上层记 `failed`；
  `reason` 属「合理跳过」类（`not_trading_day` / `not_due` / `market_closed`）→ 上层记 `skipped`，
  **不得**记 `success`。

### 2.2 `SimulationTrader.run_daily_check() -> RunOutcome`（serves: FR-1, FR-2）

- 输入：无（日期 `datetime.now()`，账户构造注入）。
- 新行为：`res = self.rebalance(today)`；`res.ok is False` → 返回 `ok=False, reason='rebalance_failed', error=res.error`。
- `rebalance()` 内 `except Exception` **保留**（保护调度），但必须：写 `self._last_error`、
  `logger.error(..., exc_info=True)`、`report_failure('strategy.rebalance', ...)`。
- **通知失败不得把成功调仓判成失败**：`success = trades_executed and account_saved`；
  通知异常单独进 `detail['notify_error']`，`ok` 不受影响（通知是副作用）。

### 2.3 `AccountTradingService.execute_pending_orders(now=None) -> dict`（serves: FR-7）

| 返回字段 | 类型 | 说明 |
|---|---|---|
| `executed` / `failed` | int | 既有 |
| `errored` | int | **新增**：因内部异常被标 failed 的单数（与"护栏拒绝"区分） |
| `skipped_off_hours` | int | **新增**：非交易时段被跳过（不改状态、留痕） |
| `expired` | int | **新增**：超期未成交而作废的挂单数 |
| `details[]` | list[dict] | 每单 `{pending_order_id, status, reason, error?}` |

- 单笔异常契约：`except Exception` → 该单 `status='failed'`、`fail_reason='internal_error: <原文>'`，
  **继续处理下一单**（批量不中断）；任何情况下不得让整批静默停在同一笔上。
- 数据契约（`quant.simulation_pending_orders`，**字段不变**）：
  `status ∈ {pending, executed, failed, expired}`（新增枚举值 `expired`，文本列，无需 DDL）；
  `fail_reason` 必填于 `failed`/`expired`。

## 3. 交易日判定：三套口径收敛到日历表（serves: FR-3）

- **serves: FR-3**
- **现状：同一件事有三套实现，语义还不同**（本次新发现，直接决定 §3 的做法）：

| # | 实现 | 谁在用 | 长假（10-05~10-07）判成 | 问题 |
|---|---|---|---|---|
| 1 | `TradingDayGuard`（K 线 + 「近 7 日有 K 线」启发式） | orchestrator（`daily_orchestrator.py:136`/`:866`）、`SimulationTrader._is_trading_day` | **交易日**（实测 True） | 休市开火；复市首日 10-08 反判 False（差 8 天 > 7） |
| 2 | `TradingCalendarService`（`application/services/trading_calendar_service.py`） | `AccountTradingService._check_trading_window`、`trade_guard_service` | **交易日**（若上游取数失败） | `get_trading_days` **先**生成"周一~周五"作兜底（:73-76），失败即静默返回工作日 → 法定节假日被当交易日（该文件 :80-84 自陈 09-10 修过一次同名 bug） |
| 3 | `quant.trading_calendar` 表（23373 行、无 `is_trading_day=false` 行 = 只存交易日） | **无人使用** | 非交易日（正确） | 权威数据躺在库里没人读 |

- **设计**：唯一真源 = `quant.trading_calendar`，且**复用已有的解析链**——
  `application/services/trading_day_resolver.py`（REQ-261004102115-d3de 于 2026-10-04 新建）已经把
  「日历表（带 `max(trade_date) >= anchor` 有效性校验）→ DataProviderManager → 周一~周五回退」
  做成逐级降级链，并把 `source` / `degraded` 一路带到调用方。**本设计不新写日历查询、不新建服务**，
  只在同一模块补一个「指定日是否交易日」的姊妹函数（与 `last_closed_trading_day` 共用取数链），
  由 `TradingDayGuard._compute` 调用。
- `TradingDayGuard` 的「今天」分支**不再使用 K 线启发式**（这正是长假误判的来源）；
  K 线只作事后交叉校验（日历说交易日、过去日却无 K 线 → 记 `degraded` + 告警，判定不变）。
- 判定顺序（唯一实现，`TradingDayGuard._compute`）：
  1. 周末 → False（`SOURCE_WEEKEND`）；
  2. 未来日期 → False（`SOURCE_FUTURE`）；
  3. 走解析链问「该日是否交易日」→ True（`SOURCE_CALENDAR`，新常量）/ False（`SOURCE_CALENDAR_HOLIDAY`）；
  4. 解析链降级（`weekday_fallback`）→ 结论照用但 `degraded=True` + 主动告警
     （**不许静默**，且不许把"日历不可用"当成"休市"）；
  5. 解析链异常 → 保守 False + `degraded=True` + `SOURCE_UNAVAILABLE`（保留现有可见性）。
- `TradingCalendarService.get_trading_days` 的"工作日兜底"一并收口：必须把 `degraded` 带出去
  （当前是静默返回工作日 → 节假日被当交易日）。
- 保留 `judge_trading_day(day, kline_exists_on_date, latest_kline_date, today, calendar_has_day=None)`
  —— 新增末位可选参数；`None` 时退回旧 K 线逻辑，**既有 8 条单测不破**。
- 实测定标（写进单测）：`check(2026-10-05|10-06|10-07) == False`、`check(2026-10-08) == True`
  （当前实现分别为 True/True/True/False，即本条证伪点）。

## 4. cron 时刻口径与漏跑宽限（serves: FR-4）

- **serves: FR-4**
- 决策：**以本地时区（Asia/Shanghai）为唯一语义**（与现行 `build_cron_trigger(tz=...)` 一致），
  库内 cron 值一律按本地时刻书写；`docs` 与 docstring 同步改正（消除「UTC cron」的旧说法）。
- 行动：`v13-simulation-trading` 的 cron 由 `30 6 * * 1-5` 改为**与声明一致的 `30 14 * * 1-5`**
  （14:30，与 `v13.yaml` / docstring / 通知文档一致；若人选盘前再单独改 yaml 声明，二者必须同改）。
- 清理：禁用行 `id=257`（`30 14 * * 1-5`，command `v13_trading` 无 handler、`last_error` 明证）
  保留为历史记录但在设计里标注为**噪声源**，本次不删（避免动无关数据）。
- 回归锁：单测断言 `build_cron_trigger('30 14 * * 1-5')` 的 `next_run_time.hour == 14`
  （防止再出现 8 小时漂移）。
- **漏跑宽限（本次新发现的口径矛盾）**：`quant.scheduler_tasks.misfire_grace_time_seconds`
  **全部行为 NULL**，而加载器写成 `task.get("misfire_grace_time_seconds") or 300`
  （`apscheduler_service.py:134`）→ 有效宽限恒为 300 秒，**"NULL = 唤醒必补跑"的文档口径在代码里根本不成立**
  （10-02 实证：进程 09:00 起、06:30 的排班直接丢失，无人知）。
  修法：加载器区分「NULL（=必补跑）」与「显式数值」，并对关键任务（v13 日检、挂单撮合）
  显式设 `NULL`；补一条断言测试锁住该语义。

## 5. 配置单源（serves: FR-5）

- **serves: FR-5**
- 决策：`live_trading/configs/strategies/v13.yaml` 为策略参数**唯一声明源**；
  `live_trading/config_simulation.yaml` 只保留执行环境参数（佣金/滑点/存储/日志）。
- `StrategyService._create_trader` 改为**全量覆盖**（不再只覆盖两项）：
  `rebalance_days`、`top_n`/`max_positions`、`single_stop_loss`、`portfolio_stop_loss`、
  `max_position`、`max_single_weight`；覆盖后**打印生效值**并与声明值逐一比对。
- 一致性检查：`tools/check_strategy_config_effective.py`（只读）输出「声明 vs 生效」三元组，
  不一致 → 退出码 2。当前实证不一致：声明 8 只 vs 生效 5 只；声明 -15% vs 另一份 -12%；
  `factors_count: 68` vs 真实 75；`v14.yaml` 75 vs 真实 78。
- 死参数：`enable_stop_loss` / `enable_rebalance` 要么接线、要么从 API/任务 params 中删除
  （当前二者全仓无读取点，属"以为能关、其实关不掉"）。

## 6. 未接线链路的显式处置（serves: FR-6）

- **serves: FR-6**
- 决策：**保留但修实、暂不接线**（接线属于新决策，留给后续需求）。
  - `application/strategies/v13_config.py` / `v14_config.py` 的 `model_path` / `factors_path`
    改为真实存在的文件（`live_trading/models/v13_model.json` / `valid_factors.json`；v14 对应文件）；
  - `xgboost_strategy.py` 的 `reference_capital` 从配置/账户注入，**删除 1,000,000 硬编码**
    （当前会让 0.17 权重 × 10 元 → 17,000 股，10 倍超买）；
  - `strategy_trading_job.strategy_execute_all` 的 `entry.get('success', True)` 改为读 `ok`；
  - `tests/regression/test_strategy_config_refactor.py:25-26` 把"不存在的路径"断言删掉，
    改为断言 `Path(V13_CONFIG.model_path).exists()`（**这条断言正是把 bug 锁死的那条**）。

## 7. 挂单撮合：不得永久搁浅（serves: FR-7）

- **serves: FR-7**
- 批量不中断（见 §2.3）。
- **撮合窗口护栏**：入口先判交易时段（复用既有 `TradingWindowGuard`）：
  - 非交易时段 → **跳过**、`skipped_off_hours++`、留痕，**不得**把挂单批量打成 `failed`
    （8/21 16:41 的实证：两笔被"非交易时段"拒绝后永久丢弃）；
  - 只有"交易时段内、且确实不满足交易规则"才标 `failed`。
- **搁浅处置（本次决策点）**：`pending` 超过 **1 个交易日**仍未成交 → 标 `expired`，
  `fail_reason='expired: pending > 1 trading day'`，并**主动外发**一条。
  理由：挂单语义是"下一个开盘执行"，隔日还挂着说明链路断了；无限重试会在错误日期以错误价格成交，
  比作废更危险。**代价**：极端情况下会丢掉一笔本来正确的委托 → 需要人确认这一点。
- 调度归属：新增任务行 `pending-orders-match`（command `pending_orders_match`，
  cron `31 9 * * 1-5`，`misfire_grace_time_seconds=NULL`），使撮合**不再只依赖 orchestrator 相位**
  且失败能落 `scheduler_runs`；orchestrator tick 内的调用保留（幂等）。
- 存量数据：两笔 8/24 的 `pending` 挂单按上述规则**会被判 `expired`** —— 是否照此执行请人在
  §14 决策点确认（另一选项是"人工确认后补成交"）。

## 8. 停摆与「该跑没跑」可见（serves: FR-8）

- **serves: FR-8**
- **现状盘点（本窗口实测）**：

| 设施 | 覆盖 | 缺口 |
|---|---|---|
| launchd `com.pi-investment.v2-api`（KeepAlive+RunAtLoad，2026-10-02 装） | 进程崩溃自愈（`runs=3`，当前 pid 37211 起于 10-02 09:00，2 天稳定） | 9/13–10/2 停摆 18 天发生在装上之前；装上后**未再验证过 kill 后是否告警** |
| 独立探活 `com.pi-investment.health-probe`（`tools/health_probe.py`，StartInterval 300，独立于 API 进程） | ① `5001/health` 端口 ② K 线数据新鲜度（10-04 起改走 `trading_day_resolver`） | **没有**「关键任务该跑没跑」判据；**没有节流**（3 天发了 **504** 条告警，节假日误报刷屏，见 §9 D-反直觉条） |
| `quant.scheduler_runs` | 每条任务执行的成败留痕 | 任务**根本没触发**时无任何行 → 只能靠人翻库发现 |

- **设计**：
  1. 探活新增第三条判据：**关键任务心跳**——对 `is_enabled=true` 的任务按当前 cron 语义推演
     「最近应跑时刻」，与 `scheduler_runs.started_at` 比对，超期未跑 → 告警；
     判定逻辑与盘点器**共用一份实现**（`application/services/should_have_run.py`，
     探活与工具都调它，避免第二个口径）。
  2. 命令入口：`tools/check_should_have_run.py`（只读，退出码 0/2/3）输出
     「任务 / cron / 最近应跑 / 实际最近 run / 判定」对照表；探活与人工共用。
  3. **必须带节流**：按（任务名 + 应跑时刻）去重，同一漏跑最多告警 1 次；
     探活整体沿用"健康→不健康"边沿触发，避免重演 504 条刷屏。
  4. 漏跑宽限与补跑：见 §4（加载器区分 NULL 与显式值；关键任务 NULL = 唤醒必补跑）。
- 判据：`kill -9` API 进程后，探活必须在 ≤ 2 个探测周期内主动外发一条「服务停摆」；
  人为把某任务 cron 改成"1 分钟前"后，盘点器必须报出该漏跑且**只报一次**。

## 9. 失败上报与通知：两条独立的丢消息路径（serves: FR-9）

- **serves: FR-9**
- **审计实证（只读，2026-10-04）**：「不发信息」不是通道坏了——飞书通道**一直可用**
  （`logs/api.log` 48 次尝试里 43 次「飞书发送成功」；独立探针 3 天里 504 次全部 `ok=true`）。
  丢的是**特定类型**，两条独立病因叠加：

| # | 位置 | 机制 | 后果 |
|---|---|---|---|
| D1 | `infrastructure/notification/channels/agent_channel.py:249-258` `supports()` **恒 True** + `domain/notification/policies/notification_policy.py:119-124` `return supported if supported else available` | agent 谎报能力 ⇒ `supported=['agent']` 非空 ⇒ **飞书永不进入候选** | `rebalance` / `risk_alert` / `trade_signal` / `verification` / `premarket_report` / `agent_reminder` / `agent_report` **7 类渠道集只有 `['agent']`** → 8080 死 = **100% 丢弃** |
| D2 | `infrastructure/notification/channels/feishu_channel.py:79-87,200-216` | `FeishuChannel` 只有 7 个 formatter（无 REBALANCE / RISK_ALERT） | 即便入选也是 `ChannelResult.error("不支持的通知类型")` |
| D3 | `.env` 曾缺 `FEISHU_WEBHOOK_URL`（10-02 08:31 才补） | 降级目标缺失 | 10-01 21:48 → 10-02 08:30 有 4 条「**所有渠道发送失败**」 |
| D4 | `application/strategies/v13_use_case.py:220-222`、`application/risk/intraday_risk_service.py:217-219` | notifier 为 None 时 `logger.debug(... skipping)` 后 return | 生产 INFO 级**看不见**，整条通知静默消失 |
| D5 | `adapters/inbound/fastapi_app/daily_jobs/alerting.py:29-42` | `_send_feishu` 返回 bool，**4 处调用方全不看返回值** | 发送失败与成功在任务流里无法区分 |
| D6 | `application/services/pool_scan_scheduler.py:78-88` | `# TODO: 实现通知逻辑` 只打日志 | 纯占位，一个字节不外发 |

- **日志佐证**：`发送通知` 事件 **48/48 全是 `system_alert`**；`rebalance` / `risk_alert` /
  `trade_signal` / `watch_triggered` 出现 **0 次**；`调仓通知已发送` **0 次**。
- **反直觉的一条（必须记下）**：用户这 3 天其实**收到约 540 条飞书消息**，但几乎全是独立探针
  的**节假日误报**（`health_probe.log` 504 次告警）→ 真实观感是「整天刷假警报、真事一条没有」。
  误报已于 10-04 由 REQ-261004102115-d3de 改走 `trading_day_resolver` 后停止（与 §3 同源）。
- **设计**：
  1. **修 D1**（一行）：`select_channels` 在 `supported` 非空时把其余 `available` 追加为**兜底**，
     即 `return supported + [c for c in available if c not in supported]`；
     同时 `AgentChannel.supports()` 不得恒真（按 OS 实存性/健康态返回）。
  2. **修 D2**：补 `REBALANCE` / `RISK_ALERT` 的飞书 formatter（或让 `SystemAlertFormatter`
     对无专用模板的类型兜底渲染）——**不修这条，10-05 之后的调仓通知照样丢**。
  3. **修 D4/D5**：`skipping` 升为 `warning` 并带 reason；`_send_feishu` 的返回值必须被消费，
     失败至少 `logger.error` + 落 `inprocess_job_runs.result`。
  4. **失败上报出口**：`agent_os_reporter.report_event` 失败后降级到 `NotificationFacade`；
     `AGENT_OS_ENABLED=false` 时直接走飞书。
  5. **日结信号**：V13 日检无论 `ok/skipped/failed` 都发一条卡片（含 `reason`/`error`/关键数字）；
     失败 high、跳过 normal（防刷屏）。
  6. `.env` 显式写 `AGENT_OS_NOTIFY_ENABLED=true`（当前靠代码默认，未来改动无人察觉）；
     核对过期键 `AGENT_API_URL=http://127.0.0.1:3002`（实测无监听，会把 agent 通知劫持到死端口，
     应为 `AGENT_API_URL_DH=http://127.0.0.1:13080`）。
- 判据：在 8080 不可达前提下触发一次 `rebalance` 与一次 `risk_alert` → 飞书均收到，
  日志留有「agent 通道失败 → 降级 feishu → delivered=true」。

## 10. 账本自洽（serves: FR-10）

- **serves: FR-10**
- 唯一真源：`simulation_trades`（`_rebuild_portfolio_from_trades` 的净额口径）。
- 卖出前硬校验：`累计买入 - 累计卖出 ≥ 本次卖出量`，否则拒绝下单 + `reason='oversell_blocked'` + 告警。
- 对账器：`tools/reconcile_sim_account.py`（只读）输出 ①逐标的买卖净额 ②现金重放
  （初始资金 + Σ成交额 - 费用）vs `simulation_account.cash_available` 的差额 ③超卖清单。
  当前实证：300045/300561/300765/300469 四只超卖，虚增现金 ≈ ¥49,425。
- **历史数据处置不在本设计内**（见 §14）。

## 11. 迁移、兼容、回滚（serves: FR-1, FR-4, FR-7）

- **serves: FR-1, FR-4, FR-7**
- **无表结构变更**（守 B3 边界）；库内仅为**数据行**改动，逐条可回滚：

| 改动对象 | 现值（记录以便回滚） | 目标值 |
|---|---|---|
| `scheduler_tasks` row 249 `cron_expression` | `30 6 * * 1-5` | `30 14 * * 1-5` |
| row 249 `misfire_grace_time_seconds` | `300`（NULL 或空） | `NULL`（唤醒必补跑） |
| `scheduler_tasks` 新增行 | 不存在 | `pending-orders-match` / `31 9 * * 1-5` |
| 两笔 8/24 `pending` 挂单 | `status='pending'` | 待 §14 决策（`expired` 或人工补成交） |

- 兼容：`RunOutcome.to_dict()` 为既有字段超集；`reason` 新枚举值只增不改；
  `pending_orders.status` 新增 `expired` 为文本列新取值，无 DDL。
- 灰度开关：`V13_CHAIN_STRICT=false` 可把「失败即 failed」退回旧行为（默认 true），
  用于上线后若告警风暴时的快速止血。
- 回滚路径：`git revert` 对应提交 + 上表右列改回左列（原值已在此留档）。

## 12. 测试策略与验收命令（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10）

- **serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10**
- **测试策略（先修"假绿灯"，再加真断言）**：
  1. `tests/test_v13_scheduler.py` 三个用例体的 `return True/False` 全部改为 `assert`
     （现状：打印「❌ Job执行失败」仍报 3 passed）；
  2. `tests/regression/test_strategy_config_refactor.py` 删掉"不存在的路径"断言；
  3. `tests/test_scheduled_jobs_account_value.py` 的 Fake 不得提供真实仓储没有的方法；
  4. 新增单测：失败传播（因子空/模型抛错 → `ok=False`）、日历 5 日期断言、
     挂单批量不中断、off-hours 不误杀、cron 小时回归锁、配置单源一致性、`oversell_blocked`。
- **验收命令**（逐条对应需求判定标准 1–10）：

```bash
# 1) 失败必须响亮（FR-1/FR-2）
venv/bin/python -m pytest tests/live_trading/ tests/test_v13_scheduler.py -v

# 2) 长假/复市判定（FR-3）——期望 False/False/False/True
venv/bin/python tools/check_trading_day_judgment.py --dates 2026-10-05,2026-10-06,2026-10-07,2026-10-08

# 3) 时刻口径与漏跑（FR-4）——对照表里不得有"应跑未跑"
venv/bin/python tools/check_should_have_run.py

# 4) 配置单源（FR-5）
venv/bin/python tools/check_strategy_config_effective.py   # 退出码 0 = 声明==生效

# 5) 未接线链路已修实（FR-6）
venv/bin/python -m pytest tests/regression/test_strategy_config_refactor.py -v

# 6) 挂单撮合不中断 + 不误杀（FR-7）
venv/bin/python -m pytest tests/services/test_pending_orders.py -v

# 7) 账本自洽（FR-10）——超卖清单必须 0 行
venv/bin/python tools/reconcile_sim_account.py --account v13_simulation
```

- 期望输出：以上均退出码 0；`reconcile_sim_account.py` 的"超卖清单"为 0 行；
  `check_should_have_run.py` 的差额列为空。
- ⚠️ 本仓知识层未生成（`reqboard_kb(kind='standard')` 返回 0 条，
  提示需先跑 `npx tsx scripts/kb-build.mts --write`），故"验收口径引用规范条目"这一步
  **当前不可得**——已如实记录，不以猜测填补。

## 13. 未定决策（需人点头，答完才可进拆分）（serves: FR-7, FR-10）

- **serves: FR-7, FR-10**
1. **搁浅挂单的处置**：`pending > 1 个交易日` 一律作废（`expired`）还是人工确认后补成交？
   本设计默认**作废 + 告警**（理由见 §7）；两笔 8/24 的存量挂单按同一规则处理。
2. **账本虚增的处置**：¥49,425 虚增现金与那 4 笔超卖成交，是回填冲正、标记为脏（统计排除）、
   还是保留不动？这决定 `v13_simulation` 的收益率还能不能当业绩看。
3. **v13 日检时刻**：确认回到 **14:30**（本设计默认，与声明一致），还是改为盘前 06:30
   （若改，`v13.yaml` 与文档必须同步改，二者恒等）。
4. **周一 06:30 的止血**：是否在本次设计批准后立即先做「暂停 row 249 + 存量挂单置为不动」
   的最小止血（不动代码），以免 10-05 休市日产生假成交。
