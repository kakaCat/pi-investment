# t-dc66e2 实现交易日解析器（最近一个已收盘交易日）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现交易日解析器（最近一个已收盘交易日）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑：./venv/bin/python -c "from datetime import datetime;from application.services.trading_day_resolver import last_closed_trading_day as f;r=f(datetime(2026,10,4,10,18));print(r.date,r.source,r.degraded)" 看到：日期为 2026-09-30，source 为 calendar_table 或 provider，degraded=False（等于 2026-10-02/2026-09-30 之外的答案即失败）。

## 实施方案（implementation）
新增 application/services/trading_day_resolver.py。定义 TradingDayResult(date, source, degraded) 与 last_closed_trading_day(ref, *, cutoff=15:30, provider_lookback_days=30)。anchor = ref.date() 若 >=15:30 否则 ref.date()-1；结果 = 日历中 <=anchor 的最大交易日。三级解析：① quant.trading_calendar（需 max(trade_date)>=anchor 才算覆盖）；② ServiceFactory.get_data_provider_manager().get_trading_calendar(start, anchor)；③ 周一至周五回退。任一级失败不抛异常、记 warning、降级；source 取 calendar_table|provider|weekday_fallback。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-04T02:26:36.068Z，窗口 session-e4214a80-d4ad-4666-9705-9ee6f7921f01）

仓里从此有了唯一的「应有交易日」口径：休市日不再被当成交易日，探针与进程内守卫将共用它。

### 完成项

- 新增 application/services/trading_day_resolver.py，提供 last_closed_trading_day() 与 TradingDayResult。
- 语义钉死为「最近一个已收盘的交易日」：15:30 前看前一自然日，交易日历里取不超过它的最大交易日。
- 三级解析链落地：日历表（需覆盖 anchor）→ AKShare 日历（经既有 DataProviderManager）→ 周一至周五回退。
- 降级不静默：source 与 degraded 随结果带出，回退时记 warning 并附刷新提示。
- 只接受 datetime：裸 date 抛 TypeError，避免「某天」与「某天 15:30」两种语义混淆。
- 实测七组日期全对：10-04/10-02/10-08 盘中 → 2026-09-30，10-08 收盘 → 2026-10-08，中秋 09-25 与周末 → 2026-09-24。

### 改动文件

- `application/services/trading_day_resolver.py`

### 下一步

t2 写日期表驱动用例把上面七组日期与三条降级路径锁成回归。

---
