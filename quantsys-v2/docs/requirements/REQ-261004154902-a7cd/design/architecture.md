---
req_id: REQ-261004154902-a7cd
title: V13 链路可信性——落点、依赖方向与回滚
doc: design/architecture
serves: FR-1, FR-2, FR-3, FR-7, FR-8, FR-9
---

# 架构设计（REQ-261004154902-a7cd）

> 总览与逐条证据见同目录 [`design.md`](design.md)。

**前提**：本需求**不改运行时架构**——不新增服务、不新增表、不新增调度宿主。
既有三条链（策略日检 / 挂单撮合 / 探活）的**归属不变**，只把"失败"从"局部返回值"
提升为"一等公民"，并让"判定真源"唯一。

## 目标与判定（serves: FR-1, FR-2）

**目标**：任何自动链路的一次运行，其「是否执行 / 是否成功 / 为什么没成功」三问
必须能从 `scheduler_runs.result` 与日志**直接读出**，且失败**主动外发**。

可证伪判定：
1. 注入一次调仓失败（因子返回空 / `model.predict` 抛错）→ 返回值 `ok=False` + `reason`；
2. 同一次运行的 `quant.scheduler_runs.status='failed'`（不是 `success`）；
3. 飞书侧收到一条告警；日志含「agent 通道失败 → 降级 feishu → delivered=true」。

## 三个断点与对应落点（serves: FR-1, FR-2, FR-7）

| 断点 | 现状 | 落点 |
|---|---|---|
| ① 结果契约缺失 | `run_daily_check`（`live_trading/simulation_trader.py:870`）丢弃 `rebalance()` 返回值；`rebalance` 的 `except`（:981）吞异常 | 新增 `application/observability/run_outcome.py`（`RunOutcome` + `ok` 唯一实现）；两处改为消费返回值 |
| ② 可见性出口缺失 | 失败只落日志；`agent_os_reporter.report_event` 的唯一出口是已下线的 Agent OS:8080 | 新增 `application/observability/failure_sink.py`；`report_event` 失败降级到 `NotificationFacade` |
| ③ 判定真源分裂 | 三套交易日口径（K 线启发式 / `TradingCalendarService` 工作日兜底 / `quant.trading_calendar` 无人用） | `TradingDayGuard._compute` 改走 `trading_day_resolver` 的日历链；K 线降为交叉校验 |
| ④ 批量中断 | `execute_pending_orders`（`account_trading_service.py:535`）只 catch `TradingError`，非该类异常中断整批且不留痕 | 单笔 `except Exception` → 标 `failed` + 续跑；入口加交易时段护栏 |
| ⑤ 时刻漂移与漏跑 | 库内 `30 6`、`tz=Asia/Shanghai`；`misfire` 加载器 `or 300` 抹掉 NULL 语义 | 库内 cron 回归声明值；加载器区分 NULL 与显式值 |
| ⑥ 通知渠道收窄 | `AgentChannel.supports()` 恒真 → `select_channels` 永不回退 → rebalance/risk_alert 只有 `['agent']` | 改 `select_channels` 兜底追加；补 REBALANCE/RISK_ALERT 的飞书 formatter |

## 依赖方向（serves: FR-1, FR-9）

```
live_trading/simulation_trader.py ─┐
application/services/account_trading_service.py ─┤
application/services/trading_day_guard.py ───────┼─> application/observability/{run_outcome, failure_sink}.py
tools/health_probe.py ───────────────────────────┘            │
                                                               └─> application/notification/NotificationFacade
                                                                     （既有 agent→feishu 降级链，不改通道实现）
```

- 新模块位于 **application 层**，只依赖既有端口（`NotificationFacade`）与标准库；
- `live_trading/`（策略执行）→ `application/` 是本仓既有方向（`simulation_trader` 已 import
  `application.services.trading_day_guard`），**无反向依赖、无环**；
- `tools/health_probe.py` 只新增对 `application` 层纯函数与只读查询的依赖，
  **保持"不依赖被监控进程"硬约束**（不 import FastAPI 应用、不要求 5001 存活）。

## 为什么不新增表（serves: FR-1, FR-7）

失败留痕全部落在**既有字段**上，守住需求边界 B3（不动表结构）：

| 失败类型 | 留痕位置（既有） |
|---|---|
| 策略日检失败/跳过 | `quant.scheduler_runs.result`（JSON 增 `ok/reason/error`）+ `status` |
| 挂单撮合失败/过期 | `quant.simulation_pending_orders.status/fail_reason` |
| 调度任务失败 | `quant.scheduler_runs.error`（既有） |
| 服务停摆 / 任务漏跑 | 探活告警（飞书）+ 日志（探针独立进程，不依赖 API 存活） |
| 通知发送失败 | 日志三行证据（agent 失败 → 降级 → delivered） |

## 回滚路径（serves: FR-1, FR-2, FR-4）

- 代码：按主题分 commit（结果契约 / 判定真源 / 撮合 / 通知 / 配置），**可逐主题 revert**；
- 数据：仅 `scheduler_tasks` 两处数据行（见 `data-model.md`，原值已留档）+ 存量挂单处置（人裁定）；
- 开关：`V13_CHAIN_STRICT=false` 退回"失败不判 failed"的旧行为；
- 依赖：不新增第三方库、不新增表、不改 plist（`health-probe.plist` 参数与周期保持，
  仅在探针**内部**新增一条判据）。
