---
req_id: REQ-261004102115-d3de
title: 测试策略、日期用例与验收命令
doc: design/test-cases
serves: FR-1, FR-2, FR-3, FR-4
---

# 测试用例设计（REQ-261004102115-d3de）

## 测试策略（serves: FR-1, FR-2, FR-3, FR-4）

分三层，各回答一个不同的问题：

- **纯函数层（零 IO）**：给定 `ref` 与注入的假日历，`last_closed_trading_day` 的日期与 `source` 是否正确；
- **探针层**：`probe_freshness()` 的判定与新增键是否按契约输出（**不触发任何通知**）；
- **反向验证**：判据没被改空——`--max-lag-days -1` 仍必须报警。

**两条硬约束**：① 用例不得联网、不得读生产库（全部注入假日历/provider）；
② 用例不得触发真实通知（沿用本仓 `tests/notify_guard.py` 守卫，绝不调 `send_alert`）。

## 用例清单 · 日期表驱动（serves: FR-1, FR-4）

`tests/test_trading_day_resolver.py`（注入固定日历：`2026-09-28/29/30`、`2026-10-08/09`）：

| # | `ref` | 期望 `expected` | 断言点 |
|---|---|---|---|
| 1 | `2026-10-04 10:18`（周日·国庆中） | `2026-09-30` | **本次告警的正例** |
| 2 | `2026-10-02 16:00`（周五·休市） | `2026-09-30` | 休市工作日不得被当成交易日 |
| 3 | `2026-10-08 15:29`（复市日·盘中） | `2026-09-30` | 未收盘不认今天 |
| 4 | `2026-10-08 15:30`（复市日·收盘） | `2026-10-08` | 收盘即认今天（边界含等号） |
| 5 | `2026-09-25 20:00`（中秋休市） | `2026-09-24` | 第二个节日的同类回归 |
| 6 | `2026-09-26 10:00`（周六） | `2026-09-24` | 周末语义不回归 |
| 7 | `2026-09-29 10:00`（交易日盘中） | `2026-09-28` | 既有"盘中看前一交易日"语义不回归 |

## 降级用例（serves: FR-1, FR-3）

8. 表为空 → 走 provider（注入假 provider）→ `source='provider'`、`degraded=False`，结果正确；
9. 表空且 provider 抛异常 → `source='weekday_fallback'`、`degraded=True`，**且不抛异常**；
10. provider 返回空列表 → 同上降级，记 warning（用 caplog 断言日志存在，避免"静默降级"）。

## 探针级用例（serves: FR-2, FR-4）

`tests/test_health_probe.py`（**不调 `main()`、不调 `send_alert`**）：

11. 打桩 `last_closed_trading_day` 返回 `2026-09-30/calendar`，打桩 DB 读 `kline_latest=2026-09-30`
    → `ok=True`、`lag_days=0`、`expected_source='calendar'`、`expected_degraded=False`；
12. 同上前提下把 kline_latest 换成 `2026-09-20` → `ok=False`、`lag_days=10`（证明判据仍会响）；
13. 降级态（`weekday_fallback`）→ `build_alert()` 的正文包含降级标注、且**当且仅当**降级时出现。

## 反向验证与命令（serves: FR-2, FR-4）

```bash
# 单测（回归锁 · 零 IO）
./venv/bin/python -m pytest tests/test_trading_day_resolver.py tests/test_health_probe.py -q

# 正例：本次告警必须消失（当前日期处于国庆休市窗口）
./venv/bin/python tools/health_probe.py --dry-run          # 期望 healthy=true，expected=2026-09-30，exit 0

# 负例：判据没被改空
./venv/bin/python tools/health_probe.py --dry-run --max-lag-days -1   # 期望 exit 2（仍报警）

# 口径一致性：进程内同源出口
./venv/bin/python -m pytest tests/test_daily_jobs_freshness.py -q      # 既有守卫用例不得回归
```

## 既有用例的回归面（serves: FR-3）

- `tests/test_freshness_guard.py`（若存在同名守卫用例）与任何断言 `_last_trading_day` 字符串返回值的用例：
  本设计保持其**签名与返回类型不变**，故不应需要改动；若有用例硬编码"周一至周五"语义，
  以本节为准更新，并在实施汇报里列出。
