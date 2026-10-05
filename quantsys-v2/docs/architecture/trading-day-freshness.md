---
title: 应有交易日与新鲜度判定
type: architecture
tags: [trading-calendar, freshness, health-probe, data-contract]
updated: 2026-10-04
---

# 应有交易日与新鲜度判定（QuantSys V2）

**来源**：[REQ-261004102115-d3de](../requirements/REQ-261004102115-d3de/requirement.md)（2026-10-04）

## 一句话

「哪天该有数据」在本仓**只有一个口径**：`application/services/trading_day_resolver.py` 的
`last_closed_trading_day()`（语义 = 最近一个**已收盘**的交易日）；任何新鲜度判定都必须问它，
不要再自己写 `weekday()`。

## 事故与根因（2026-10-04）

外部健康探针报「K 线最新 2026-09-30 / 应有 2026-10-02，滞后 2 天」，每 5 分钟一次。
真相：A 股 10-01~10-07 国庆休市（上证公告〔2026〕22 号），**下一交易日是 10-08**，
09-30 就是当下最新的真实交易日——**数据完好，判据错了**。

根因：`daily_jobs/pipeline.py:_last_trading_day` 是「周末排除法；节假日由告警人工复核」，
国庆休市日被当成交易日；探针复用了它，进程内的 `freshness_guard` 也复用了它——
**同一根因两个出口**。

## 唯一口径（改代码前先读这段）

```
anchor = ref 时刻 >= 15:30 ? ref.date() : ref.date() - 1 天
结果   = 交易日历中 <= anchor 的最大交易日
```

三级解析，逐级降级（除入参类型外**不抛异常**）：

| 级 | 源 | 何时用 |
|---|---|---|
| ① | `quant.trading_calendar` 表 | 离线、快；**要求 `max(trade_date) >= anchor`**（表不覆盖 anchor 时它无权判断） |
| ② | `DataProviderManager.get_trading_calendar()`（AKShare） | 表不可答时；这是唯一能给出**未来交易日**的源 |
| ③ | 周一~周五回退 | 前两级都不可用——**必须把 `degraded=True` 带出去** |

**降级必须响亮**：探针 JSON 有 `expected_source` / `expected_degraded`，告警正文在降级时追加
「交易日历不可用，按工作日口径判定」；巡检 result 亦有 `expected_source`。
休市期若日历全挂，读告警的人要能一眼看出"这条判定可信度更低"——否则误报会以"看起来正常"的样子回来。

## 谁在用这个口径

| 调用方 | 位置 | 说明 |
|---|---|---|
| 外部健康探针 | `tools/health_probe.py` `expected_trading_day()` | 输出契约新增两个键（增量，既有键不变） |
| 进程内新鲜度巡检 | `adapters/inbound/fastapi_app/daily_jobs/pipeline.py` | `_last_trading_day()` 保留原名与签名（40+ 导入方），内部转发 resolver |
| 数据契约检查器 | `tools/check_data_contracts.py:compute_expected_trading_day()` | **同一语义的第三个实现，尚未合并**（它自带 `holiday_slack_weekdays` 冗余，实测未误报） |

## 运维：日历表要保鲜

`quant.trading_calendar` 由 `tools/refresh_trading_calendar.py` 灌入，真源 = **K 线 DISTINCT 日期 ∪ AKShare 官方日历**
（前者给历史深水区，后者给未来交易日；只用 K 线会让表"刚填好就过期"）：

```bash
./venv/bin/python tools/refresh_trading_calendar.py            # 幂等，可反复跑
./venv/bin/python tools/refresh_trading_calendar.py --dry-run  # 先看会写多少
```

- 主键 `(trade_date, exchange)`，只写 TRUE/FALSE、不写 NULL；
- **未加排班**（属调度层决定）：表一旦不覆盖 anchor，探针每次运行都会走一次 provider；
- 填表有一个**连带影响**：`data_pipeline_service.load_trading_calendar_from_db(exchange)` 从
  「空表 → 回退 K 线 + error 日志」变为「直接读表」——这正是该函数注释要求的方向，回退路径未改。

## 改这块代码时的硬规则

1. **不要新增第二份 `weekday()` 判定**：新需求一律调 `last_closed_trading_day()`；
2. **不要静默降级**：任何降级都要能被外部看见（字段或日志）；
3. **打桩点跟着接缝走**：测试打桩要打在**被调函数所在模块**——
   本仓已因"名字还在但不再被读"栽过四次（最近一次就是 `test_freshness_guard.py` 打在转发壳
   `pipeline._last_trading_day` 上）；
4. **休市日空跑同步另案**：`evening_pipeline` 在休市日仍会起 `kline_sync`（实测成功 0 只），
   属"休市日该不该起同步"的独立决定，未在本次范围内。

## 回归锁在哪

- `tests/test_trading_day_resolver.py`（13 条）：日期表驱动 + 三条降级路径 + 类型守卫；
- `tests/test_health_probe.py`（5 条）：探针判定与来源标注（含"降级才标注"的双向锁）；
- `tests/e2e/test_health_probe_e2e.py`（2 条）：按 launchd 的真实入口跑整条链，断言可观察终态。
