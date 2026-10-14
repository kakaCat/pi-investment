---
title: 净值序列的交易日口径（哪些日期算数）
type: architecture
tags: [trading-calendar, equity-snapshot, nav-series, attribution, risk-metrics, data-contract]
updated: 2026-10-06
---

# 净值序列的交易日口径（QuantSys V2）

**来源**：[REQ-261006190953-fc43](../requirements/REQ-261006190953-fc43/requirement.md)（2026-10-06）
**上游口径页**：交易日历白名单与新鲜度见 [trading-day-freshness.md](trading-day-freshness.md)；调度侧的门见 [REQ-261006093620-a315](../requirements/REQ-261006093620-a315/requirement.md)

## 一句话

`quant.simulation_equity_snapshot`（账户净值序列）**只认交易日**：休市日的行写不进去、读不到、也不算缺口；判据的唯一来源是交易日历。

## 事故与根因（2026-10-06）

休市日的净值与归因数字"看着正常，其实没有统计意义"：

| 现象 | 实测证据 |
|---|---|
| 净值表里有**非交易日行** | 35 行 = 5 账户 × 7 天（2026-08-08/08-15/08-29/09-05/09-06/09-12 周末 + 10-02 国庆） |
| 这些行**直接进了归因窗口** | `POST /api/risk/metrics{days:60}` 返回 `navPoints=60`，恰等于表里含周末的 60 行 |
| 缺口判断**自己也偏爱节假日** | agent-dh 侧按"相邻快照间隔 + 跳过周末"自算，报出 **21 个"缺失工作日"**（含 10-01/10-02 国庆）→ 触发无意义补跑 |
| 一条**把未实现缓解写成既成事实**的注释 | `trading_day_guard.py` 曾称那批脏行"已标记并从统计口径排除"——**该列与引用都不存在** |

**根因一句话**：净值快照的"日期"从来没有过交易日这道门——写入端各写各的、读取端按行相邻配对、
缺口探测用"工作日"近似。

## 唯一口径（改这块代码前先读）

1. **判据唯一来源**：`application/services/trading_day_gate.py`（`skip_non_trading_day` /
   `verdict_info`，fail-open 且永不抛）。**禁止**第二套 `weekday()` / `isoweekday()` / JS 的 UTC 星期判定。
2. **写入端唯一闸门**：`SimulationORMRepository.upsert_equity_snapshot` —— 非交易日不落库、返回 `None`、
   留 `skip_daily_write_non_trading_day` 日志；`force=True` 是显式旁路（仅迁移/回滚/测试）。
   **门设在"写入函数"这一层**，因为守卫 `should_write_daily()` 早已存在却只有 1 处调用——
   产脏的四条路径（编排器 / DailyJobs 快照任务 / tools 脚本 / 成交事务）一条都没调它。
3. **读取端口径唯一实现**：`application/services/nav_series.py`（`filter_trading_days` /
   `nav_returns_from_snapshots` / `nav_coverage`）。**它是纯口径模块，不做任何 IO**；
   交易日集合由调用方注入（`adapters/outbound/repositories/trading_calendar_repository.trading_day_set()`）。
4. **不可得 ≠ 空集**：日历读失败/空表一律返回 `None`，调用方按"未校验"处理并在返回体里如实声明；
   用空集表达失败会把整个净值序列清空、让指标**静默退化**——这是最危险的退化方式。
5. **缺口只在交易日上算**：区间内"应有而缺失的交易日"才是缺口；周末与法定节假日不计入。
6. **缺口判断由 v2 算**（它持有日历），agent-dh **只消费**、不重算；v2 没给字段时如实声明
   "未做交易日校验"，**禁止**回退到自算。

## 交易日历是**白名单**（这条最容易读错）

`quant.trading_calendar` 只列交易日：实测生产 **23373 行 `is_trading_day` 全是 true，一条 false 都没有**。
因此：

> **非交易日 = 覆盖范围内（`min(trade_date) ~ max(trade_date)`）且不在清单里**

"**防误删/防误判**"由**覆盖范围**承担：范围之外的日期一律不动（日历没铺到的地方不猜）。
按 `is_trading_day = false` 写判据会匹配 **0 行**——本需求的设计初稿正是这么写的，
实施期被 dry-run 当场证伪（见需求 D-6），迁移、巡检、设计文档三处已同步改为白名单语义。

## 谁在用这个口径

- **写入**：`DailySnapshotService.snapshot_all_accounts` / `EquitySnapshotJob.run` /
  `PaperTradingEngine.take_daily_snapshot` / `AccountTradingService`（成交事务内）/ `backfill_account`
- **读取**：`POST /api/risk/metrics`（`days` = **交易日数**，返回 `window` 与 `nav_coverage`）、
  `GET /api/simulation/performance`（`equity_curve` 只含交易日，返回同样两块）
- **消费**：agent-dh 的 `RiskMetricsTool`（业绩归因/风险指标）
- **运维**：`infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py`（清理存量）

## 运维：清存量与常态巡检

```bash
# 1) 先看差异（缺省 dry-run：走 apply 同一条路径后 ROLLBACK，库内零改动）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py
# 2) 落库（先备份到 quant.bak_equity_snapshot_nontrading_w_0a409569，再删、再逐账户全序列重放重算）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py --apply
# 3) 事后核对（逐账户独立复算，diff=0 才算干净）
./venv/bin/python tools/verify_equity_snapshot_consistency.py --accounts agent_virtual,user_main_simulation,v13_simulation,v14_simulation,v15_simulation
# 4) 常态巡检：退出码 0=零违规 / 2=有违规 / 3=判不了（日历空表）
PYTHONPATH=. ./venv/bin/python tools/check_nontrading_equity_snapshots.py
```

**为什么删除必须配"全序列重放"**：删一个中间行会改变其后每一行的 `peak`（前缀最大值）与 `daily_return`
基准，只补局部必然留下不一致。

## 改这块代码时的硬规则

1. **不要新增第二份交易日判定**：一律调 `trading_day_gate`；日历集合取 `trading_day_set()`（读表的那一层）。
2. **不要在读取端"信任库里的行"**：过滤要在读取端兜底（库里可能还有历史脏行/回滚回来的行）。
3. **不要用空集表达"日历不可得"**：返回 `None`，并让 `verified=False` 对外可见。
4. **不要把新字段只加在一半**：`POST /api/risk/metrics` 的**显式 `returns` 口径**下没有净值序列，
   新字段必须显式缺省——本需求在这里踩过一次 `UnboundLocalError` → 端点 500。
5. **跨仓改动不要在消费侧"顺手重算"**：agent-dh 从 v2 拿不到口径时要**如实声明**，不要自己猜。

## 回归锁在哪

- `tests/test_nav_series.py`（14 条）：口径三锁（不可得≠空集 / 未校验不过滤 / 缺口只算交易日）+ 跨节假日归段
- `tests/test_equity_snapshot_trading_day_gate.py`（11 条）：写入闸门（周末/周日/法定节假日拒写、降级照写、
  `force` 旁路、`limit`=交易日数、基准回退、残缺行跳过、闸门以目标日被调用）
- `tests/test_equity_snapshot_daily_return.py`（+2 条）：`calculate_daily_return` 把日历集合透传给基准
- `tests/test_daily_jobs_trading_day_gate.py`（+6 条）：`EquitySnapshotJob` 先问门再问收盘、两段文案可区分
- `tests/test_risk_metrics_nav_window.py`（12 条）：两个接口的 `window` / `nav_coverage` 契约与既有键回归
- `tests/test_migration_purge_nontrading_snapshots.py`（8 条）：迁移 dry-run 零副作用 / 白名单删除 + 范围外不动 /
  行数不符中止 / 备份不足中止 / 判据归零 / 幂等 / 回滚
- `tests/test_check_nontrading_equity_snapshots.py`（6 条）：巡检器三态 + 造脏行活性
- **跨仓**：`agent-dh` → `apps/web/tests/attribution-alignment.test.ts`（15 条）
