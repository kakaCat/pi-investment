---
req_id: REQ-261005203907-2b8c
title: DailyJobs 交易日门——落点、依赖方向与回滚
doc: design/architecture
serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 架构设计（REQ-261005203907-2b8c）

> 接口签名见 [`interfaces.md`](interfaces.md)；数据落点见 [`data-model.md`](data-model.md)；
> 场景见 [`use-cases.md`](use-cases.md)；测试见 [`test-cases.md`](test-cases.md)。

**前提**：本需求**不改运行时架构**——不新增服务、不新增表、不新增调度宿主。
DailyJobs 宿主（`daily_jobs/`）增加一道**任务级交易日门**，判定真源复用既有
`application/services/trading_day_guard.TradingDayGuard`，本需求不发明第二个判定器。

## 落点与依赖方向（serves: FR-1, FR-2）

```
adapters/inbound/fastapi_app/daily_jobs/
    registry.py   JOBS：3 个任务声明 trading_days_only=True
    defs.py       JobDef 追加字段 trading_days_only: bool = False
    gate.py       ★新增：fail-open 取舍 + 结果注解（唯一判定消费点）
    runtime.py    _run_job：整段跳过（写 skipped 行、不发通知、早退）
    pipeline.py   _job_evening_pipeline：因子段的局部跳过
        │  inbound 层只做"取判定 + 取舍"
        ▼
application/services/trading_day_guard.py  TradingDayGuard.check() -> TradingDayVerdict
        │  （is_trading_day / source / degraded；已存在，本需求不改其语义）
        ▼
application/services/trading_day_resolver.py  日历表 → provider → 工作日回退(degraded)
```

- **依赖方向合规**：`adapters/inbound → application`，方向只许向内（库规范 `conventions.md#c-01`）。
- **判定器零改动**：`TradingDayGuard` 仍是"交易日判断唯一入口"，本需求只在**调用点**按
  `degraded` 做 fail-open 取舍；钱路任务沿用的 fail-closed 语义**保留**。
- **不新增第三方依赖**，不新增配置项（见「回滚路径」的决策）。

## 文件结构（新建 / 修改，各自职责一句话）（serves: FR-1, FR-2, FR-3, FR-4）

| 文件 | 动作 | 职责（一句话） |
|---|---|---|
| `adapters/inbound/fastapi_app/daily_jobs/gate.py` | **新建** | fail-open 取舍 + 判定注解，宿主的唯一交易日门 |
| `adapters/inbound/fastapi_app/daily_jobs/defs.py` | 修改 | `JobDef` 末尾追加 `trading_days_only: bool = False` |
| `adapters/inbound/fastapi_app/daily_jobs/registry.py` | 修改 | 给 3 个任务声明 `trading_days_only=True` |
| `adapters/inbound/fastapi_app/daily_jobs/runtime.py` | 修改 | `_run_job` 增加跳过早退分支（写 `skipped` + 不发通知） |
| `adapters/inbound/fastapi_app/daily_jobs/pipeline.py` | 修改 | `_job_evening_pipeline` 因子段按共享判定局部跳过（K 线段原样） |
| `tests/test_daily_jobs_trading_day_gate.py` | **新建** | 门真值表 + `_run_job` 留痕/静默 + 注册表范围 |
| `tests/test_evening_pipeline_holiday_gate.py` | **新建** | 因子段真值表（含"交易日绝不跳因子"回归） |

**导出清单不改**：`gate.py` 是新符号，**不**加进 `daily_jobs/__init__.py` 与
`daily_jobs_bootstrap.py` 的转发壳——那两处只为"既有导入路径不破"而存在（44 个模块在用），
包内 `pipeline.py` / `runtime.py` 直接 `from ...daily_jobs.gate import ...` 即可。

**删除**：无。**新增依赖**：无。**DDL/迁移**：无（见 [`data-model.md`](data-model.md)）。

## 为什么门不放 `is_due`（serves: FR-3, FR-5）

`is_due` 返回 `False` 时宿主**连一行台账都不写**（`runtime.py:243-247` 只在 due/catchup 时才起线程），
于是"休市日跳过"与"根本没跑"在 `quant.inprocess_job_runs` 里长得**完全一样**——
这正是 REQ-261004154902-a7cd 在修的盲区形态。另外两条飞书（`runtime.py:100` 开始、
`runtime.py:134` 完成）在 `_run_job` 内**无条件**发出，门放在 `is_due` 之外也管不到它们。

故门放在 `_run_job` 内、`_mark_running` 之后、开始通知**之前**：

```
_mark_running(job, run_date)
if job.trading_days_only and skip_non_trading_day()[0]:
        _mark_done(job, run_date, 'skipped', result={...})   # 留痕
        logger.info('inprocess_job_skipped', ...)
        return                                               # ← 通知一条都不发
_send_feishu('▶️ 每日任务开始…')
result = job.handler()
```

## 为什么 fail-open 而不 fail-closed（serves: FR-2）

`adapters/inbound/fastapi_app/orchestrator_bootstrap.py:33` 记着 2026-09-12 的审查结论：
`TradingDayGuard` 是 **fail-closed**（数据源异常 → 保守判非交易日），而那是"钱路"任务的唯一门，
接上去会让 DB 一抖就静默停掉 T+1 结转与止损。本需求的收益只是"省一次无信息量的重算"，
**绝不能换来一次静默停摆**。故取守：

| verdict | 判定 | 理由 |
|---|---|---|
| `is_trading_day=False` 且 `degraded=False` | **跳过** | 日历明确答"休市"（`trading-calendar-holiday` / `weekend` / `future`） |
| `is_trading_day=True` | 照跑 | 交易日 |
| 任意 `degraded=True`（`weekday_fallback` / `unavailable` / `compute-error`） | **照跑** | 降级不可作为"不开火"的依据；最坏退化为现状（多跑一次） |
| `gate.py` 自身抛异常 | **照跑** | 门不许成为可用性故障源 |

降级时把 `source` / `degraded` 写进任务 `result.trading_day` 并记一条 warning 日志——**不许静默**。

## 逐任务落点（serves: FR-4）

| 任务 | 是否需要当日行情 | 落点 | 休市日语义 |
|---|---|---|---|
| `pool_daily_refresh` 19:05 | 是（指数成分 × 打分） | `trading_days_only=True` | 整段跳过（refresh + sync-stock-names 都不做） |
| `chip_distribution` 21:10 | 是（当日 K 线） | `trading_days_only=True` | 整段跳过（延后补算，见下） |
| `evolution_fitness` 20:35 | 是（账户行为续采） | `trading_days_only=True` | 整段跳过（同窗口重采=幂等 upsert） |
| `evening_pipeline` 20:30 | K 线段：否；因子段：是 | **不加标志**，handler 内共享判定 | K 线段照跑（缺口修复路径）；因子段在"K 线本次无更新"时跳过 |
| `watch_rule_health` | 否（规则健康） | 不加标志 | 工作日照跑（不变） |
| `event_calendar_check` | 否（事件提醒，含周末） | 不加标志 | 每日照跑（不变） |
| `freshness_guard` | 否（基准日已交易日感知） | 不加标志 | 工作日照跑（休市日自证新鲜、安静） |
| `financial_statements` | 否（季报，周六） | 不加标志 | 不变 |
| `pool_weekly_review` | 否（周日盘点） | 不加标志 | 不变 |

**"整段跳过"为什么可证安全**（不是"反正休市没数据"的想当然）：

- `chip_distribution` 的待办**由状态驱动**：`ChipRepository.get_symbols_with_pending_klines`
  （`chip_repository.py:215-239`）判据是 `state 缺失 or ChipState.last_trade_date < max(kline.trade_date)`；
  休市日漏算的会在复市首日的运行里被 `pending` 重新选中 → **延后补算，不丢**。
- `pool_daily_refresh` 是**全量重算**（`StockPoolService.refresh_pool` 用当前模板重新打分取 top_n），
  不依赖"上次跑过"，复市首日照常换血。
- `evolution_fitness` 是 20 交易日滚动窗口续采，同窗口重采为幂等 upsert。

## 与相邻口径的关系（serves: FR-1, FR-4）

- **APScheduler 路径不在范围**：`quant.scheduler_tasks` 启用 11 条（信号/扫描/策略类）走 `APSchedulerService`，
  与 DailyJobs 宿主是两条调度路径；v13 链已由 REQ-261004154902-a7cd 在内部自守，
  其余（信号生成/扫描）是否需自守属另一条线——本需求只登记，不改（升级信号见需求文档 L3）。
- **REQ-261004102115-d3de 的交接**：该需求「不做什么」原文把"`evening_pipeline` 在休市日空跑"明确留作
  "另案处理"，本需求即那一个"案"。
- **RFC 016 §8.1 第 9 项**（"需要一个故障时降级为 weekday 而非判 False 的日级来源"）在本需求落地为
  `gate.py` 的 `degraded → 照跑` 取舍；`orchestrator_bootstrap` 的 weekday 近似**本次不动**
  （它是钱路门，改动需单独评估）。

## 回滚路径（serves: FR-1, FR-4, FR-5）

- **无 DDL、无数据迁移、无配置项**。回滚 = 撤掉 3 处 `trading_days_only=True`
  与 `_job_evening_pipeline` 内的因子段判定 → 行为**逐字回到今天**。
- 已产生的 `status='skipped'` 历史行**惰性**：`is_due` 对未知状态落 `return False`（当日不重跑）、
  `catchup_due` 只看 failed、`_reap_orphan_runs` 只看 running、`_job_failure_watch` 只看 failed
  → 不阻塞任何后续运行，也不需要回填。
- **决策：不引入 `DISABLE_*` 开关**。理由：本需求改动面是 3 行注册表 + 1 个分支，
  代码回滚比开关更简单；而本仓 `DISABLE_*` 的历史用途是"在滞后数据上避免误开火"，
  与本次语义无关（少一个开关 = 少一条没人维护的路径）。

## 不做什么（serves: FR-4）

- 不改 `TradingDayGuard` / `trading_day_resolver` 的语义与降级告警链路。
- 不改 `evening_pipeline` 的 K 线段（探活、覆盖度门槛、批大小、缺口修复、失败上抛全部保留）。
- 不改另外 5 个任务的排班与行为。
- 不碰 APScheduler 路径、不碰 `orchestrator_bootstrap` 的 weekday 近似。
- 不改任何对外 HTTP 契约（`list_today_runs()` 只是多出一种状态值）。
