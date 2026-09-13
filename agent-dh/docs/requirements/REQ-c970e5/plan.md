# REQ-c970e5 实施计划 · 补齐 v2 六域打标并堵住新建任务不带 domain 的源头

- 需求：REQ-c970e5（bug）
- 窗口：w-a1402b8c（角色 investor）
- 计划日期：2026-09-13

## 1. 现象

双线执行看板「分类对账」v2 侧：`v2 侧 domain（六域，与业务线正交）已打标 33/40，缺 7：session-probe、equity_snapshot_daily、ingest_events_history 等`。

线上证据（`GET :13080/dashboard/api/board`，2026-09-13 19:12 拉取）：

- `taskCoverage.v2 = { total: 40, domainTagged: 33, domainMissing: 7, byValue: {monitor:3, analysis:7, trading:6, signal:7, data:7, report:3} }`
- `missingNames = [session-probe, equity_snapshot_daily, ingest_events_history, core_plan_generate, ingest_disclosure_calendar, strategy_loop_weekly, data_hygiene_probe]`
- 对照 v2 接口（`GET :5001/api/scheduler/tasks?pageSize=200`）：6 个是 **2026-09-13 当天新建**的任务（createdAt 16:38–18:16），1 个是既有决策留空。

## 2. 根因

**创建路径根本不接 domain，新建任务必然 born-NULL。**

- `adapters/outbound/repositories/scheduler_repository.py` → `add_task(name, cron_expression, command, params, description, task_type)`：签名无 domain，构造 `SchedulerTaskConfig(...)` 时也不传；`update_task` 的 `allowed` 白名单同样不含 domain。
- 创建接口 `POST /api/scheduler/tasks`（`routes/scheduler_async.py:214`）不透传 domain。

这与 2026-09-02 那批 OS 侧事故是同一类根因：`public.tasks.agent_line` 当时是 `NOT NULL DEFAULT 'profit_engine'`，而 Go `Create()` 的 INSERT 不含该列 → 09-02 之后新建任务全部静默继承默认值（见 `docs/work-logs/2026-09/scheduler-line-tagging-20260902.md` 第 74–75 行）。当时只做了数据修正，源头没堵 → 现在在 v2 侧以同样的方式复发。

历史口径（同一份工作日志）：

- 2026-09-02 加列并回填 30 个 enabled 任务，0 NULL；
- 2026-09-12 又修了 12 条 NULL（data 5 / signal 2 / monitor 2 / trading 1 / analysis 1），并**明确保留 `session-probe` 为 NULL**：「全仓无实现、disabled、溯源不明 → 宁显不藏，不猜」。所以第 7 个不是漏打，是有意留空。

## 3. 六域归属（按「同族先例 + 实现模块」，与 2026-09-02/09-12 两次打标同法）

| 任务 | 拟 domain | 依据 |
|---|---|---|
| equity_snapshot_daily | monitor | 同族先例：2026-09-02 回填把「264 权益快照」归 monitor；同为每日净值快照 |
| ingest_events_history | data | 同族：ingest_events_daily / ingest_events_policy 均为 data（事件入库，RFC 015 §3.5/§4） |
| ingest_disclosure_calendar | data | 同族：财报披露日历属数据采集（每日财报时效性检查 = data） |
| data_hygiene_probe | data | 同族：每日数据质量检查 = data；实现模块 application/services/data_hygiene_service.py |
| strategy_loop_weekly | analysis | 同族：daily-strategy-validation / 每周策略发现 / chan-knowledge-distill-weekly 均 analysis |
| core_plan_generate | trading | 同族：daily-pool-refresh / v13-risk-check / daily_trade_verify 均 trading（组合与建仓口径） |
| session-probe | **维持 NULL（不改）** | 2026-09-12 既定决策：无实现、disabled、溯源不明 → 宁显不藏 |

## 4. 任务拆分

| key | 标题 | phase | side | 依赖 | 验收 |
|---|---|---|---|---|---|
| t1 | 给 6 个新建任务补打 domain（数据修正） | implement | backend | — | `SELECT name,domain FROM quant.scheduler_tasks WHERE domain IS NULL` 只剩 session-probe 一行；改动前后值写入台账（改前备份 7 行到 /tmp） |
| t2 | 打通创建/更新路径的 domain（含六域白名单，不设 DEFAULT） | implement | backend | t1 | `add_task(..., domain='monitor')` 建的任务 domain 落库；不带 domain 建的任务为 NULL（不静默填默认）；非法 domain 被拒（400/ValueError）；`update_task(domain=...)` 可改；ports 接口签名与实现一致 |
| t3 | v2_health_check 增加 domain 缺失指标 | implement | backend | t2 | 触发 v2_health_check 后 payload 含 domain 缺失任务数与名单；无缺失时该指标为 0 且不误报 |
| t4 | 看板对账区分「有意留空」与「真缺」 | implement | frontend | t1 | `/dashboard/api/board` 的 v2 段把 session-probe 标为 known-null；对账行不再把它计入「待补录」（避免第 7 个永久刷告警） |

## 5. 验证与留痕

- 数据：psql 直查 `quant.scheduler_tasks.domain IS NULL` 的行数与名单（改前 7 → 改后 1）
- 代码：新建任务实测（带 domain / 不带 domain / 非法 domain 三种）
- 看板：`GET :13080/dashboard/api/board` 的 `taskCoverage.v2.domainMissing`（改前 7 → 改后 0 或按 known-null 口径）
- 留痕：memory_write + 需求推进 reason；按 R-013 标注来源与时点

## 6. 边界与风险

- **不碰 `session-probe` 的 NULL**：那是有据可依的留空，改它等于抹掉「宁显不藏」的信号；改为在看板上显式区分。
- **不设 DEFAULT**：默认值正是 09-02 那次静默事故的成因，宁可 NULL 被对账暴露。
- **同步风险**：`routes/scheduler_async.py` 与 `application/services/scheduler_tasks.py` 当前被另一个窗口（w-32314d00，cron 段数校验）在改 —— 本需求只加最小的 domain 透传 hunk，改完复核对方 hunk 仍在；若冲突则以对方在飞的改动为准，本需求让路重做。
- **不重启即不生效**：v2 代码改动需重启 :5001（quantsys_v2_restart）后才能实测接口行为。
