# 架构设计（REQ-261006190953-fc43）

**目标一句话**：把"净值序列 = 哪些日期算数"从**隐式约定**改成**显式契约**——交易日历说了算；
写入端一道闸门、读取端一处口径、缺口判断交给**持有日历的那一侧（v2）**算，消费方只读不重算。

```
                     同一个洞，三层各自的收口点
  ┌──────────────────────────┬──────────────────────────┬──────────────────────────┐
  │ ① 写入端（闸门）          │ ② 读取端（口径）          │ ③ 缺口（唯一算法）        │
  ├──────────────────────────┼──────────────────────────┼──────────────────────────┤
  │ SimulationORMRepository  │ nav_series.filter_       │ v2 在响应里算             │
  │   .upsert_equity_snapshot│   trading_days()         │   nav_coverage            │
  │   ← 唯一收口点            │ nav_series.nav_returns_  │   （交易日历在此侧）      │
  │ 复用 trading_day_gate    │   from_snapshots()       │                          │
  │   .skip_non_trading_day  │ ← 读取端兜底（双保险）    │ agent-dh 只**消费**字段   │
  │                          │                          │ 不再用 weekday 自算       │
  └──────────────────────────┴──────────────────────────┴──────────────────────────┘
         非交易日：写不进去            脏行：读不到            节假日：不算缺口
```

## 落点与依赖方向（serves: FR-1, FR-2）

**依赖方向（单向，不许反向）**：

```
  application/services/trading_day_gate.py      ← 判据（既有，本需求只复用）
            ↑
  application/services/nav_series.py           ← 口径（新建；只依赖判据 + 仓储接口）
            ↑
  application/services/*（risk_metrics_service / simulation route / daily_snapshot_service）
            ↑
  adapters/outbound/repositories/simulation_repository.py   ← 写入闸门 + 交易日过滤读取
```

三条硬约束：

1. **判据只有一处**：`application/services/trading_day_gate.py`（`should_skip` / `verdict_info` /
   `skip_non_trading_day`）。本需求**不新增**任何"是不是交易日"的实现——
   禁止 `weekday()`、禁止第二条日历查询链、禁止在 agent-dh 侧复刻日历。
2. **口径只有一处**：`nav_series`（交易日集合的读、过滤、日收益派生）都在这一个模块；
   路由与服务不得各自写 `if d in trading_days`。
3. **写入只有一处**：`SimulationORMRepository.upsert_equity_snapshot` 是**所有**净值行的唯一落库口
   （实测：`paper_trading_engine.take_daily_snapshot`、`account_trading_service` 成交路径、
   `DailySnapshotService._snapshot_one`、`DailySnapshotService.backfill_account` 四条都经它）。

## 为什么闸门设在仓储写入函数，而不是每个入口（serves: FR-2）

**现状取证**：守卫入口 `TradingDayGuard.should_write_daily()` 早已存在且语义正确
（[trading_day_guard.py:466](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/trading_day_guard.py#L466)），
但全仓**只有 1 个生产调用方**（`live_trading/simulation_trader.py:409`）——
**产脏的四条路径一条都没调它**。

| 路径 | 现状 | 结论 |
|---|---|---|
| `daily_orchestrator.tick` / `resume_from_breakpoint` | 有交易日门（入口级） | 护了入口，**没护被调函数** |
| `DailySnapshotService.snapshot_all_accounts` | 无门；`EquitySnapshotJob._has_bar` 是 2026-09-13 补的"K 线代理"判据 | 代理判据 ≠ 日历判据，且是**事后补的** |
| `PaperTradingEngine.take_daily_snapshot` | 无门 | 编排器以外的调用方（脚本/人工）直接裸奔 |
| `AccountTradingService` 成交事务内写快照 | 无门 | 休市日只要发生成交就写非交易日行 |

**所以闸门必须设在"写入函数"这一层**：入口门可以漏、可以新增，写入函数只有一个。
**这是本设计最关键的一条**——它把"记住加门"变成"绕不过去"。

## 为什么缺口判断从 agent-dh 搬到 v2（口径单调）（serves: FR-3, FR-4）

**现状**：`agent-dh` 的 `RiskMetricsTool.probeNavCoverage` 在客户端用
`new Date(...)` + `getUTCDay() != 0/6` 自己算缺口，`basis` 字段自认
「未扣法定节假日，数字可能略高估」（[RiskMetricsTool.ts:165](/Users/mac/Documents/ai/pi-investment/agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts#L165)）。
**结果**：同一个"交易日"概念在 v2（日历表）与 agent-dh（工作日近似）各有一份实现，必然漂移——
国庆 10-01~10-07 在 v2 是休市、在 agent-dh 是 7 个"缺口"，于是触发无意义补跑。

**设计裁定**：**缺口在 v2 算，agent-dh 只消费**。

- v2 持有日历与净值表，`nav_coverage` 作为 `/api/simulation/performance` 与 `/api/risk/metrics`
  响应的一部分返回（`missing_trading_days` / `missing_count` / `basis` / `trading_day_source`）；
- agent-dh 的 `probeNavCoverage` **改为读 v2 字段**；v2 字段缺失时**如实声明"未做交易日校验"**，
  **不得**回退到 weekday 自算（回退就等于把洞留着）。

**代价**：agent-dh 需一次字段消费改造（跨仓）。**收益**：交易日概念从"两处实现"收敛为"一处实现"，
从结构上消灭这类漂移。这与 D-3「三层同改」并不冲突——agent-dh 仍然要改，只是改成**消费**而非**重算**。

## 复用既有判据，不造第三套（serves: FR-1）

`trading_day_gate.py` 的降级策略**已经是本需求要的口径**（逐字引用）：

- `trading-days` → 跳过 ⇔ `is_trading_day=False` **且** `degraded=False`；
- 未知策略 → 照跑（最坏多跑一次，比静默停摆安全）并响亮留痕；
- 任何异常 → `(False, gate-error info)`，**永不抛**。

净值写入是"按日落库"，与库表调度的 `trading-days` 策略**语义完全相同**，
故写入闸门直接调 `skip_non_trading_day(day)`（等价 `should_skip('trading-days', day)`），
**不新增策略值、不新增函数**。

## 文件结构（新建 / 修改，各自职责一句话）（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8）

| 文件 | 动作 | 职责一句话 |
|---|---|---|
| `application/services/nav_series.py` | **新建** | 净值序列口径唯一实现：读交易日集合、过滤非交易日行、派生日收益、算缺口 |
| `application/services/trading_day_gate.py` | 不改 | 判据（既有）——本需求只调用 |
| `adapters/outbound/repositories/simulation_repository.py` | 改 | `upsert_equity_snapshot` 加唯一写入闸门；`get_equity_snapshots` 支持只取交易日（`days` = 交易日数）；`previous_valid_snapshot` 基准改按交易日回退 |
| `application/services/risk_metrics_service.py` | 改 | `nav_returns_from_snapshots` 收敛为对 `nav_series` 的**薄转发 shim**（保持既有导入路径不破） |
| `application/services/evolution/daily_snapshot_service.py` | 改 | `snapshot_all_accounts` / `EquitySnapshotJob.run` 返回结构化 `skipped`；`_has_bar` 收敛为"是否已收盘"辅助判据 |
| `application/trading/paper_trading_engine.py` | 改 | `take_daily_snapshot` 处理闸门返回的"未写入"，返回结构化 `skipped`（不再假设一定有 snap） |
| `adapters/inbound/fastapi_app/routes/simulation_async.py` | 改 | `/api/simulation/performance` 的 `equity_curve` 只含交易日，响应新增 `window` 与 `nav_coverage` |
| `adapters/inbound/fastapi_app/routes/analysis_async.py` | 改 | `/api/risk/metrics` 的 `days` = 交易日数，响应新增 `window` 与 `nav_coverage` |
| `infrastructure/persistence/migrations/20261006_purge_nontrading_equity_snapshots.py` | **新建** | 备份 → 删 35 行 → 重算派生字段（`--dry-run` 缺省，`--apply` 落库，带 `lock_timeout`） |
| `tools/verify_equity_snapshot_consistency.py` | **新建** | 一致性校验：逐账户比对重算后的 `daily_return`/`drawdown`/`peak_value`/`max_drawdown` |
| `agent-dh`：`RiskMetricsTool.ts` + `prompt.ts` | 改（跨仓） | `probeNavCoverage` 改为消费 v2 的 `nav_coverage`；文案与 `basis` 同步 |
| `agent-dh`：`apps/web/tests/attribution-alignment.test.ts` | 改（跨仓） | 锁"节假日不计缺口""v2 字段缺失时如实声明" |

## 降级（fail-open）与留痕（serves: FR-1, FR-8）

| 情形 | 写入闸门行为 | 留痕 |
|---|---|---|
| 日历答"交易日" | 正常写 | 无 |
| 日历答"非交易日"（周末/法定节假日/未来日） | **不写** | `skipped` + 五键注解（`day`/`is_trading_day`/`source`/`degraded`/`reason`） |
| 日历链降级（`degraded=True`，含工作日回退与异常） | **照写**（fail-open：宁可写一行可疑数据，也不静默停摆） | 判定注解里 `degraded=True` 必须随返回值带走；接口侧显式标注 |
| 判据自身异常 | 照写 + `source='gate-error'` | warning 日志；`gate-error` 是"代码 bug"而非"日历说休市" |

**为什么不 fail-closed**：净值序列断一天会连带污染波动率/IR/回撤与熔断口径，
而"日历拿不到"时把整个净值写入停掉，等于一次日历故障就造成全账户数据断档——
与本仓既有策略（`trading_day_gate` 的 fail-open）保持一致。

## 回滚路径（serves: FR-6, FR-7）

两级回滚，互不依赖：

1. **口径回滚**（代码级，不动数据）：`nav_series` 的过滤是**读时**行为，把
   `trading_days_only` 置 False 即回到今天的行为；写入闸门可临时用 `force=True` 旁路（仅运维/迁移/测试）。
2. **数据回滚**（存量清理）：`quant.bak_equity_snapshot_nontrading_w_0a409569` 整行备份，
   回插后重跑 `recompute_account_max_drawdown` + 日收益重算即可复原（见 `data-model.md` §5）。

## 不做什么（serves: FR-4, FR-6）

1. **不加"是否交易日"列**：交易日是日历的函数，落成列＝造第二个真源（见 `data-model.md` §1）。
2. **不改调度排班 / misfire 宽限**：休市日"要不要开火"归 `REQ-261006093620-a315`；
   本需求保证"开火了也写不出、读不到、算不上非交易日"。
3. **不动 `quant.trading_calendar` 的日历数据**（刷新归 `tools/refresh_trading_calendar.py`）。
4. **不修基准数据链**（D-5）：`nav_coverage` 只报"净值序列自身"的缺口，不报基准缺口。
5. **不重构 sync/async 双轨仓储**：只改 `SimulationORMRepository` 的两处行为。
6. **不做前端产物**（side=backend）。
