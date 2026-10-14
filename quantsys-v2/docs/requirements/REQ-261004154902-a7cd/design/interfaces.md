---
req_id: REQ-261004154902-a7cd
title: 接口与错误语义（RunOutcome / 日检 / 撮合 / 交易日判定 / 通知）
doc: design/interfaces
serves: FR-1, FR-2, FR-3, FR-7, FR-9
---

# 接口设计（REQ-261004154902-a7cd）

> 总览见同目录 [`design.md`](design.md)；数据落点见 [`data-model.md`](data-model.md)。

## 1. `RunOutcome`（新增值对象）（serves: FR-1, FR-2）

`application/observability/run_outcome.py`

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `executed` | bool | 是 | 是否进入执行分支（**沿用既有字段名**，兼容看板/API） |
| `ok` | bool | 派生 | `ok = executed and error is None`，**唯一**在 `run_outcome.py` 内计算 |
| `action` | str | 是 | `rebalance` / `stop_loss` / `hold` / `skipped` |
| `reason` | str | 是 | 受控枚举，见下 |
| `error` | str \| None | 否 | 异常原文，截断 ≤2000 |
| `detail` | dict | 否 | 可 JSON 序列化；如 `days_to_next` / `notify_error` |

**reason 枚举与上层映射（唯一判据表）**

| reason | 含义 | 上层 `scheduler_runs.status` |
|---|---|---|
| `ok` | 真干成 | `success` |
| `not_trading_day` / `not_due` / `market_closed` | 合理跳过 | `skipped` |
| `model_not_loaded` / `factor_empty` / `rebalance_failed` / `stop_loss_failed` / `oversell_blocked` | 环境坏 / 真失败 | `failed` |
| `pending_expired` | 挂单超期作废（告警） | `failed`（任务级） |

- 兼容契约：`to_dict()` 是既有字段的**超集**（`executed` / `reason` / `action` 不变），
  既有调用方与看板无需改动；
- 错误语义：**不抛异常给调度**（`rebalance` 内异常仍就地捕获），但**必须**变成
  `ok=False + error`，并由 `FailureSink` 外发。

## 2. `SimulationTrader.run_daily_check() -> RunOutcome`（serves: FR-1, FR-2）

- 输入：无（日期取 `datetime.now()`，账户构造注入）。
- 变更点：
  1. `res = self.rebalance(today)`；`res.ok is False` → 返回 `ok=False, action='rebalance', reason='rebalance_failed', error=res.error`；
  2. `except` 分支必须 `logger.error(..., exc_info=True)` + `FailureSink.report_failure(...)`；
  3. **把 `_send_rebalance_notification` / `_format_rebalance_content` 从
     `if __name__ == '__main__':` 块内移回类体**（现状：`hasattr(SimulationTrader, ...)` 为 False，
     调用点 `:957` 必抛 `AttributeError`）；
  4. **通知失败不得把成功调仓判成失败**：`success = trades_executed and account_saved`；
     通知异常进 `detail['notify_error']`。
- 返回样例（失败）：
  `{"executed": False, "ok": False, "action": "rebalance", "reason": "rebalance_failed", "error": "..."}`

## 3. `AccountTradingService.execute_pending_orders(now=None) -> dict`（serves: FR-7）

| 返回字段 | 类型 | 说明 |
|---|---|---|
| `executed` / `failed` | int | 既有语义不变 |
| `errored` | int | **新增**：因内部异常被标 failed（与"护栏拒绝"区分） |
| `skipped_off_hours` | int | **新增**：非交易时段跳过（**不改挂单状态**，仅留痕） |
| `expired` | int | **新增**：超 1 个交易日未成交而作废 |
| `details[]` | list | 每单 `{pending_order_id, status, reason, error?}` |

- 单笔契约：`except Exception` → 该单 `status='failed'` + `fail_reason='internal_error: <原文>'`，
  **继续处理下一单**（禁止整批静默停在同一笔上，这正是 8/24–10/02 搁浅 41 天的形态）；
- 入口护栏：先判交易时段（复用 `AccountTradingService._check_trading_window` /
  `_is_in_trading_window`，其唯一时段口径为 `MarketSessionPolicy`）：
  - **非交易时段 → 跳过**（`skipped_off_hours++`），**不得**把挂单批量标 `failed`
    （8/21 16:41 实证：两笔被"非交易时段"拒绝后永久丢弃）；
  - 交易时段内、确实违反交易规则 → 标 `failed` + `fail_reason`。
- 若 `now` 传入非交易时段，返回体必须体现 `skipped_off_hours > 0` 且 `failed == 0`（可断言）。

## 4. `TradingDayGuard.check(day, use_cache=True) -> TradingDayVerdict`（serves: FR-3）

- 签名不变；`verdict.source` 新增取值：`trading-calendar` / `trading-calendar-holiday`；
- 判定链（唯一实现）：周末 → 未来 → **`trading_day_resolver` 日历链** → 降级标注；
- 既有 `SOURCE_INTRADAY`（"近 7 日有 K 线"启发式）**从"今天"分支移除**（长假误判来源），
  K 线只作事后交叉校验（无 K 线 → `degraded=True` + 告警，判定不变）；
- 纯函数兼容：`judge_trading_day(day, *, kline_exists_on_date, latest_kline_date, today, calendar_has_day=None)`
  —— `calendar_has_day=None` 时退回旧逻辑，**既有 8 条单测不破**。

## 5. 通知渠道修复（serves: FR-9）

| 位置 | 现状 | 改成 |
|---|---|---|
| `domain/notification/policies/notification_policy.py:119-124` | `return supported if supported else available` → agent 恒真 ⇒ 飞书永不入选 | `return supported + [c for c in available if c not in supported]`（**兜底追加**） |
| `infrastructure/notification/channels/agent_channel.py:249-258` | `supports()` 恒 True（谎报能力） | 按 OS 实存性/健康态返回 |
| `infrastructure/notification/formatters/feishu_formatters.py` + `notification_factory.py:145-163` | 无 `REBALANCE` / `RISK_ALERT` formatter | 补两个 formatter（或让 `SystemAlertFormatter` 兜底渲染） |
| `application/strategies/v13_use_case.py:220-222`、`application/risk/intraday_risk_service.py:217-219` | notifier 为 None 时 `logger.debug(... skipping)` | 升 `warning` + 带 reason |
| `adapters/inbound/fastapi_app/daily_jobs/alerting.py:29-42` | `_send_feishu` 返回值 4 处调用方不看 | 消费返回值；False → `logger.error` + 落 `inprocess_job_runs.result` |
| `application/services/pool_scan_scheduler.py:78-88` | `# TODO: 实现通知逻辑` 只打日志 | 补实现或删除假通知日志 |

- `FailureSink.report_failure(source, reason, error, severity, context)`：
  `severity ∈ {normal, high}`；失败类 high、跳过类 normal（防刷屏）；
  内部先结构化日志、再经 `NotificationFacade` 外发；**自身绝不抛异常**。

## 6. 盘点器接口（serves: FR-8）

`application/services/should_have_run.py` + `tools/check_should_have_run.py`

- 输入：`now`（可注入，测试用）、`enabled_only=True`；
- 输出（表格）：`任务名 / cron（本地语义）/ 最近应跑时刻 / 实际最近 run / 判定（ok|missed|unknown）`；
- 退出码：`0` 无漏跑、`2` 有漏跑、`3` 检查器自身出错；
- **节流**：按（任务名 + 应跑时刻）去重，同一漏跑最多告警一次（防止重演探针 3 天 504 条刷屏）。
