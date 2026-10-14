# REQ-261006130750-0654 · 设计：架构

**作用域**：`quantsys-v2/`（backend，无前端）
**需求**：[../requirement.md](../requirement.md)
**本设计的一句话说清**：给 v2 剩下的第 ④ 条日级判据路径（编排 tick + 盘中监控）
接上**既有唯一真源**交易日门；门 fail-open，钱路内层 fail-closed 一行不改。

## 1. 现状：两条常驻线程的日级判据是"周几"（serves: FR-1, FR-2）

```
adapters/inbound/fastapi_app/orchestrator_bootstrap.py::_monitor_loop   （60s 一轮）
  │
  ├─ if _in_orchestrator_window(now):        # :41  now.weekday() < 5 and 8 <= hour <= 17
  │      monitor_jobs.daily_orchestrator_tick()
  │           └─ daily_orchestrator.tick()   # :133 内层 TradingDayGuard.is_trading_day()（fail-closed）
  │                                            → 休市日：外层放行 + 内层早退 = 每分钟一次**空调**
  │
  └─ if _in_intraday_window(now):            # :44  分钟 ∈ {0,30} + phase_for(is_trading_day=weekday<5)
         monitor_jobs.intraday_monitor_check()
              └─ IntradayMonitor.check()      # :58  只判时段；:138 把 is_trading_day **硬编码为 True**
                                                 → 休市日：**真跑**（读持仓、按冻结收盘价判止损/止盈、写持仓市值）
```

两条路径的症状不同，但根因同一：**日级判据由"周几"承担**（E1/E2），而真实日历就在手边（E6）。

## 2. 两层门的分工（serves: FR-1, FR-2, FR-3, FR-6）

本设计把"日级门"放在**两个位置**，各有明确职责，**判据同一份**：

| 层 | 位置 | 职责 | 性质 |
|---|---|---|---|
| **A. 循环层预过滤** | `_monitor_loop` 两个分支前 | 休市日**连调用都不发生**（编排 tick 的空调就此消失） | 便宜、可去噪、非权威 |
| **B. 被调用方权威判定** | `IntradayMonitor.check()` 首部 | 旁路调用（补跑脚本 / 其它窗口 / 新服务）也拦得住 | 权威、含副作用路径的唯一闸门 |

- **编排 tick 只需要 A**：它的内层（`tick()` / `resume_from_breakpoint()`）本来就有日级门，
  本需求的净效果是"把每分钟的空调换成零调用"，**不动内层**（见 §3）。
- **盘中监控需要 A + B**：A 省掉调用与噪音，B 承担权威判定——因为 `check()`
  是"会写钱路状态"的入口（E3），且**本仓已有同款先例**：
  `WatchEngine.tick()` 在 2026-09-11 之所以把时段守卫从 `run_forever` **搬进 `tick()`**，
  理由原文是"任何旁路调用（补跑脚本/新服务/其他窗口）都会在盘后照样判定并推送通知"
  （`application/services/watch_engine/engine.py:318-322`）。盘中监控与它同型，照此办理。
- **A 与 B 判据同源**：都调 `application/services/trading_day_gate.should_skip('trading-days', now)`；
  任一层都**不允许**出现 `now.weekday()` 或新写的日历查询（FR-3 的静态对账）。

## 3. 与内层 fail-closed 的共存（本设计最要紧的一处）（serves: FR-3, FR-4）

**内层 `daily_orchestrator` 的 fail-closed 是钱路要的语义，本需求一行不改。**

- 内层：`TradingDayGuard.is_trading_day()` → 日历不可用 ⇒ **保守判非交易日 ⇒ 不做**
  （宁可一天不结转，也不在未知行情上动钱）。这条语义是 2026-09-11 事故后定下的，**保持**。
- 外层 A：`should_skip('trading-days')` → **只有"日历明确答该跳过"才跳过**，
  任何降级（`weekday_fallback` / `unavailable` / `compute-error` / `gate-error`）**一律照跑**。
- 为什么外层必须 fail-open，而不是复用内层语义：外层唯一的收益是"省一次无信息量的重算"
  （`trading_day_gate.py:27-34` 的原话），**绝不能换成一次静默停摆**。
- **净效果可证**：外层只可能在"内层也会早退"的日子里少调用（休市日）；
  在交易日与降级日，外层一律放行 → **钱路的执行次数不变**（R1）。

**因此明确不做**：不把日级判定下沉进 `daily_orchestrator.tick()` 的既有守卫，
也不改 `resume_from_breakpoint()` 的守卫——那是"用 fail-open 覆盖 fail-closed"，
会重演 `orchestrator_bootstrap.py:33-39` 注释里记的那起"日历一抖、T+1 静默停摆"。

## 4. 依赖方向与唯一真源（serves: FR-3）

```
adapters/inbound/fastapi_app/orchestrator_bootstrap.py ─┐
                                                        ├─→ application/services/trading_day_gate.py
application/services/intraday_monitor.py ───────────────┘        （should_skip / verdict_info）
                                                                        │
                                                                        └─→ application/services/trading_day_guard.py
                                                                                 （TradingDayGuard.check，判据实现）
```

- 两处调用方都在 `application`/`adapters` 侧，方向合法（本仓既有形态）；
  **`trading_day_gate.py` 本需求零改动**——它已经是 ②③ 的唯一真源，本需求只是**多一个调用方**。
- `infrastructure/` 不参与本需求（不新增任务、不碰 jobstore）。
- **打桩点**（本仓 CLAUDE.md 规则）：桩必须打在 **`application.services.trading_day_gate`**；
  打在 `orchestrator_bootstrap` / `intraday_monitor` 的同名符号上**静默失效**（E7）。

## 5. 留痕与去噪（serves: FR-6）

- **跳过时的留痕**：一条 info 日志，字段 `path`（`orchestrator_tick` / `intraday_monitor`）+
  五键注解 `day / is_trading_day / source / degraded / reason`。
- **去噪**：编排 tick 在休市日会命中 600 次/天（8:00–17:59 每分钟），盘中监控 10 次/天
  （`:00/:30`）——**不得**逐次刷屏。规则：模块级 `_LAST_SKIP_LOG: dict[path, day]`，
  同一 `path + day` **只留第一条**；跨日自动重置（key 少、无清理负担）。
- **不打扰**：跳过**不发任何通知**、不写 `quant.*` 新状态、不加开关（FR-6）。
- **降级时的响亮留痕**：沿用 `TradingDayGuard` 既有通道（`_log_degraded_loud` /
  `_alert_degraded`，按【日+来源】限流）——本设计**不重复造告警**。
- 与 ②③ 的差别：② 的跳过写 `quant.scheduler_runs.status='skipped'`（有台账表）；
  ④ 这条线程**没有运行台账表**，故本需求只写日志，**零 DDL**（见 data-model.md）。

## 6. 文件结构（新建 / 修改 / 删除，各自职责一句话）（serves: FR-1, FR-2, FR-3, FR-4, FR-6）

| 动作 | 文件 | 职责一句话 |
|---|---|---|
| **修改** | `adapters/inbound/fastapi_app/orchestrator_bootstrap.py` | 新增模块级 helper `_should_run_today(now, *, path)`（内部只调 `should_skip`）+ 跳过日志去噪；`_monitor_loop` 两个分支前各插一次判定 |
| **修改** | `application/services/intraday_monitor.py` | `check()` 首部加权威日级门（跳过即早退，**不构造** `PaperTradingEngine`、不读持仓/价格）；新增常量 `SKIP_REASON_NON_TRADING_DAY`；`check()` 增加可选入参 `now`（缺省 `datetime.now()`，向后兼容，供确定性单测） |
| **不改** | `application/services/trading_day_gate.py` | 唯一真源，本需求只调用（零改动） |
| **不改** | `application/services/trading_day_guard.py` | fail-closed 语义保持（钱路） |
| **不改** | `application/services/daily_orchestrator.py` | 内层门与阶段机保持 |
| **不改** | `infrastructure/jobs/monitor_jobs.py` | 两个薄转发函数签名不变 |
| **不改** | `tests/test_market_session_policy.py` | 实测其端点用例只调 `_is_trading_time`（`check()` 无既有调用方），故无需改动；若实施中发现需要注入时间，属**最小改动**且不得弱化原意 |
| **新建** | `tests/api/test_orchestrator_trading_day_gate.py` | 日期驱动 + 降级 + 反例锁 + 去噪 + 打桩点证伪（用例矩阵见 test-cases.md） |
| **删除** | —— | 无（本需求不删代码、不删任务、不删表） |

**窗口函数**（`_in_orchestrator_window` / `_in_intraday_window`）**签名与语义不动**（FR-4）。

## 7. 范围与裁定引用（serves: FR-1, FR-2）

- **D-2（用户裁定 A）**：只收口 v2 侧 ④ 路径。因此本设计**不**触碰
  agent-ts 的 `*/15 9-11,13-14 * * 1-5`，也**不**修今日 `00:01–00:04` 的
  `data_validator` 报错（登记于 requirement.md「后续线」）。
- **D-1**：「27 次空跑」口径未复现（E8），本设计**不**以该数字为依据扩大范围；
  若报告来源方给出新的统计口径，属需求变更，须回需求阶段改边界。
- **历法覆盖度**（E9：`quant.trading_calendar` 覆盖到 `2026-12-31`）**不在本设计范围**：
  本设计只保证"门在日历答不了时照跑且响亮"，不新增补刷任务。

## 8. 回滚路径（serves: FR-1, FR-2, FR-3）

- **零迁移、零开关**：回滚 = 还原改动文件（`orchestrator_bootstrap.py` /
  `intraday_monitor.py` / 用例）。还原后行为与门装之前**逐字一致**（外层回到周几近似）。
- **不需要**数据回填、不需要重启数据库、不需要 reload jobstore；进程重启即生效
  （两条线程随 FastAPI lifespan 启动，`orchestrator_bootstrap.start_orchestrator`）。
- **部分回滚**也可行且互相独立：只还原 A 层（循环）→ 回到"每分钟空调 + 内层早退"；
  只还原 B 层（`check()`）→ 回到"休市日真跑"。故 A/B 的用例分别独立（test-cases.md T1–T3 / T6）。

## 9. 不做什么（serves: FR-4）

1. 不改窗口函数的时段语义与签名；不改 `test_orchestrator_bootstrap.py` 的既有断言。
2. 不改 `TradingDayGuard` / `should_skip` 的判定语义与三值策略。
3. 不改内层 `daily_orchestrator` 的 fail-closed 守卫与阶段机。
4. 不新增表/列/迁移/开关；不在 `quant.*` 写新状态。
5. 不引入新的日历实现、不新增第三方依赖。
6. 不做 agent-ts 侧、不做日历自动补刷、不修 `data_validator` 报错（后续线）。
