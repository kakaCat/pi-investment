# REQ-261006190953-fc43 · 业绩归因/风险指标窗口未按交易日取数：剔除周末与节假日的净值点

**需求ID**: REQ-261006190953-fc43
**类型**: feature
**作用域**: `quantsys-v2/`（`adapters/outbound/repositories/simulation_repository.py`、`application/services/risk_metrics_service.py`、`application/services/evolution/daily_snapshot_service.py`、`application/trading/paper_trading_engine.py`、`application/services/daily_orchestrator.py`、`adapters/inbound/fastapi_app/routes/simulation_async.py`、`adapters/inbound/fastapi_app/routes/analysis_async.py`、`infrastructure/persistence/migrations/`、`tests/`）+ 跨仓 `agent-dh/`（`packages/tools/risk/src/tools/RiskMetricsTool/`、`apps/web/tests/`）
**侧**: backend（无前端产出，不涉及原型）
**档位**: 重档（依据见文末「档位依据」；跨仓 + 改数据契约 + 需清理存量生产台账）

## TL;DR

**2026-10-06（国庆休市·周二）晚间，业绩归因报告给出的组合窗口与回撤，是拿"含周末与节假日的净值点"算出来的。**

根因一句话：**净值快照的"日期"从来没有过交易日这道门——写入端各写各的、读取端按行相邻配对、缺口探测用"工作日"算缺口。**

```
        净值序列这条链上，同一个洞漏在三层（本需求要一次补齐）
  +------------------------+  +------------------------+  +------------------------+
  | ① 写入端               |  | ② 读取端               |  | ③ 缺口探测             |
  | 谁都能写非交易日行      |  | 按"行相邻"配对成日收益 |  | 用"工作日"算缺口       |
  +------------------------+  +------------------------+  +------------------------+
  | snapshot_all_accounts  |  | nav_returns_from_      |  | agent-dh               |
  |   (仅有 _has_bar 代理) |  |   snapshots 逐行差分   |  | RiskMetricsTool        |
  | take_daily_snapshot    |  |  /api/risk/metrics     |  |  .probeNavCoverage     |
  | account_trading_service|  |  /api/simulation/      |  |  basis 原文：          |
  | tools/snapshot_daily   |  |   performance          |  |  "未扣法定节假日，     |
  |                        |  | previous_valid_snapshot|  |   数字可能略高估"      |
  |                        |  |  docstring 写"上一     |  |                        |
  |                        |  |  交易日"、实现是"上一行"|  |                        |
  +------------------------+  +------------------------+  +------------------------+
             |                          |                          |
             v  35 行脏数据落库          v  脏行参与波动率/IR/回撤  v  节假日算成缺口
  quant.simulation_equity_snapshot                    → 触发无意义的"补跑"
  （5 账户 × 7 个非交易日）
```

**本需求要做的**：把"哪些日期算数"收成**唯一口径 = 交易日历**（`TradingDayGuard` / `quant.trading_calendar`），
三层同改：非交易日**写不进去**、脏行**读不到**、节假日**不算缺口**；并清掉已落库的 35 行脏数据、重算派生链。

## L1 一句话目标 + 可证伪判定标准

**目标**：净值序列及一切由它派生的窗口收益、日收益、波动率、IR、回撤、缺口判断，**只认交易日**；
交易日历是唯一口径源；休市日的行既写不进、也读不到、也不算缺口；现有脏数据清零且派生字段重算一致。

**可证伪判定标准**（跑什么、看到什么算过，逐条对应下方 FR）：

1. **写入端单测**：休市日（`2026-10-02`/`2026-10-07`）调用 `snapshot_all_accounts`、`take_daily_snapshot`、
   成交路径快照写入 → **不产生行**且返回 `skipped` 与原因；交易日（`2026-09-30`）→ 正常写。
2. **读取端单测**：构造含周末/节假日行的净值序列 → `nav_returns_from_snapshots` 的收益条数
   `= 交易日数 - 1`，且**跨节假日的涨跌归到复市首日那一段**（不产生假日"日收益"）。
3. **接口口径**：`POST /api/risk/metrics{account_name,days=N}` 的 `navPoints` 与窗口内**交易日数**一致；
   响应带 `window.from/to/trading_days/filtered_non_trading`；`GET /api/simulation/performance`
   的 `equity_curve` **不含**非交易日。
4. **缺口探测单测（agent-dh）**：净值序列覆盖 `2026-09-30 → 2026-10-08` 且两端齐全时，
   缺口 = `0`；`2026-10-01~10-07` 整段**不得**计为缺口；返回带 `trading_day_source`。
5. **存量清理可证伪**：判定标准第 8 条的巡检 SQL 返回 `0`，且写入回归锁（非交易日行数恒为 0）。
6. **派生字段一致**：清理后受影响账户的 `daily_return` / `drawdown` / `peak_value` / `max_drawdown`
   与该账户清理后的净值序列重算结果一致（逐账户比对脚本零差异）。
7. **不破现状**：`tests/` 内风险指标、净值快照、编排器交易日门相关用例全过；
   `agent-dh` 侧 `npx vitest run apps/web/tests/attribution-alignment.test.ts` 全过。
8. **真实观察（时间型）**：`2026-10-07`（休市）当日无新增净值行；`2026-10-08`（复市首日）恢复写入成功。

## 边界

### 做什么

1. **写入端设唯一闸门（FR-1/FR-2）**：所有写 `quant.simulation_equity_snapshot` 的路径经**同一判定函数**，
   判定唯一来源 `application/services/trading_day_guard.TradingDayGuard.check(day)`；非交易日**不写**、
   留 `skipped` 与原因；日历降级（`degraded=True`）**fail-open 照写**并显式标记。
2. **门设在被调函数层（FR-2）**：护住的是"写入函数"而不是"某个入口"，使编排器 / DailyJobs 脚本 /
   成交路径全部受护；`equity_snapshot_daily` 现有的 `_has_bar`（以"K 线存在"代理交易日）
   **收敛为日历口径**，`_has_bar` 降级为"是否已收盘"的辅助判据。
3. **读取端兜底过滤（FR-4）**：`nav_returns_from_snapshots`、`/api/risk/metrics`、
   `/api/simulation/performance` 的序列只取交易日；`days` 语义 = **交易日数**（响应回显实际窗口）。
4. **日收益基准落成日历口径（FR-5）**：`previous_valid_snapshot` 的"上一交易日"真正按日历取，
   不再等于"上一行"。
5. **缺口探测改交易日口径（FR-3，跨仓 agent-dh）**：`probeNavCoverage` 的缺口 = 日历区间内应有而缺失的
   **交易日**；周末与法定节假日不计入；`basis` 不再写"未扣法定节假日"。
6. **存量清理 + 重算（FR-6/FR-7）**：备份 → 删除 35 行非交易日行 → 重算受影响账户派生字段。
7. **口径可见化（FR-8）**：接口与归因结果显式声明窗口起止、交易日数、被过滤行数与判定来源。
8. **可测**：新增日期驱动单测 + 一条可常态跑的巡检 SQL（见「判定标准（可跑）」）。

### 不做什么

1. **不修「基准滞后 / 超额不可得」**（裁定 D-5）：`quant.index_daily` 为空、基准取数链路是独立问题，
   本需求只钉"哪些日期算数"；判定标准里**不出现**"超额可用"。
2. **不改调度排班与 misfire 宽限策略**：休市日"自动排班是否开火"已由
   `REQ-261006093620-a315` 承担；本需求只保证"即使开火了，也写不出、读不到、算不上非交易日点"。
3. **不动 `quant.trading_calendar` 日历数据本身**（不由本需求刷新日历）；门的行为**依赖**该表正确。
4. **不改净值表的键与列**：`(account_name, snapshot_date)` 唯一键不变，不新增"是否交易日"列
   （口径由日历唯一决定，冗余列会造出第二个真源）。
5. **不重构 sync/async 双轨仓储**；只改写入闸门与读取过滤这两处行为。
6. **不做前端/看板产物**（side=backend，不交原型）。

### 边界理由

- **为什么三层都改**：只改写入端，历史脏行继续被读；只改读取端，脏行会继续增长且其他消费方（`evolution_fitness`
  的 `window_end` 等）继续踩；只改缺口探测，"补跑"照样会写出新的非交易日行。三层共用**同一口径源**才有闭合。
- **为什么门设在被调函数层**：本现象的历史证据显示"入口护了、被调函数没护"正是漏点
  （`daily_orchestrator.tick` 有门，`take_daily_snapshot` 没门；`_has_bar` 是 2026-09-13 才补的代理判据）。
- **为什么不做冗余列**：交易日属性是日历的函数，落成列就会与日历漂移，且读取端仍要 join 日历校验。

## 产品定义

### 一句话

把"净值序列 = 哪些日期算数"从**隐式约定**改成**显式契约**：交易日历说了算，三层同源，脏数据清零。

### 为什么现在做

`REQ-261006093620-a315` 已经把"休市日不该开火"这道门补给了库表调度，但**开火之后取数仍然没按交易日过滤**——
两道门是同一个洞的两半。用户 2026-10-06 直接指出了另一半（"里面没有把节假日过滤了"），
且现有报告里的窗口收益/回撤是**看起来正常的错数**，会被拿去改仓位与熔断判定，属误导决策而非显示问题。

### 成功长什么样

1. 归因/风险指标的窗口起止与点数都能对回交易日历（点数 = 交易日数，缺口 = 0）。
2. 休市日无论哪条路径触发，净值表**零新增行**，且台账里能看到 `skipped` 与原因（不是静默）。
3. 巡检一条 SQL 就能证明"库里没有非交易日净值行"，不靠人盯。

## 用户与角色

| 角色 | 关心什么 | 本需求给他的东西 |
|---|---|---|
| 投资人（人） | 报告数字能不能信 | 窗口/回撤/波动率只由交易日构成；报告显式写明窗口口径 |
| 投资脑（agent-dh） | 归因结论与缺口判断 | 缺口不再被节假日撑大、不触发无意义补跑；归因窗口自洽 |
| 运维/排障者 | 复发时能否一眼看出 | `skipped` 留痕 + 巡检 SQL + 接口回显过滤计数 |
| 后续开发者 | 新写入路径别再造洞 | 唯一闸门函数 + 回归锁（非交易日行数恒 0） |

## 功能点（G2 条款）

- **FR-1: 净值写入唯一闸门——非交易日不写**
  所有写入 `quant.simulation_equity_snapshot` 的代码路径必须经同一判定（写入函数内的单一闸门），
  判定唯一来源 `TradingDayGuard.check(day)`；非交易日不发 INSERT/UPDATE，返回
  `{'skipped': True, 'reason': ..., 'trading_day_source': ...}`；日历降级（`degraded=True`）时 fail-open 照写并标记。
  禁止任何调用方另写 `weekday()` / 第二条日历查询链。

- **FR-2: 闸门设在被调函数层，入口门不作数**
  闸门位于写入函数（`DailySnapshotService._snapshot_one`、`PaperTradingEngine.take_daily_snapshot`、
  `AccountTradingService` 的快照写入、`SimulationRepository.upsert_equity_snapshot` 三者之一或共用的前置函数），
  使编排器、DailyJobs、`tools/` 脚本、成交路径**全部**受护；
  `EquitySnapshotJob._has_bar` 由"交易日代理判据"收敛为"是否已收盘"的辅助判据，交易日判定走日历。

- **FR-3: 缺口探测改交易日口径（agent-dh）**
  `RiskMetricsTool.probeNavCoverage` 的缺口集合 = `[from, to]` 区间内**日历判定为交易日**且序列缺失的日期；
  周末与法定节假日不计入；返回字段含 `missing_trading_days`、`trading_day_source`、`missing_count`（新口径）；
  `basis` 文案不再出现"未扣法定节假日"。日历不可达时如实声明"未做交易日校验"（不得静默按工作日算）。

- **FR-4: 窗口读取按交易日取数（读取端兜底）**
  `nav_returns_from_snapshots` 只按交易日序列生成日收益；`/api/risk/metrics`（`account_name` 口径）与
  `GET /api/simulation/performance` 的 `equity_curve` 只含交易日行；`days` 语义明确为**交易日数**；
  响应回显实际窗口（`from`/`to`/`trading_days`/`filtered_non_trading`）。即使库里存在脏行，也不参与计算。

- **FR-5: 日收益基准取"上一交易日"而非"上一行"**
  `previous_valid_snapshot` / `calculate_daily_return` 的基准快照按**交易日历**回退到上一个交易日
  （沿用现有"残缺快照跳过"判据）；跨节假日的涨跌累积归到复市首日那一段，不产生假日"日收益"。

- **FR-6: 存量非交易日行清理 + 派生链重算**
  先备份（`quant.bak_equity_snapshot_nontrading_w-0a409569`）再删除 35 行（5 账户 × 7 天）；
  随后重算受影响账户的 `daily_return`、快照 `drawdown`、`simulation_account.peak_value` 与
  `max_drawdown`；清理与重算须可复跑（幂等）。

- **FR-7: 清理结果可证伪，且常态可巡检**
  落地一条判定 SQL（非交易日行数）与一条重算一致性比对，二者常态返回 0；判定 SQL 进回归锁
  （新增测试断言"非交易日行数 = 0"），避免后续写入路径再把洞打开。

- **FR-8: 口径可见化，不再静默出数**
  归因/风险指标返回与报告文案显式给出窗口起止、交易日数、被过滤的非交易日数与判定来源；
  日历降级时显式标注 `degraded`；缺数据时给"不可用"而不是给一个看起来正常的数。

## 现状取证（2026-10-06 实测）

| 编号 | 结论 | 证据（可复现） |
|---|---|---|
| E1 | 净值表含 **35 行非交易日**行：5 账户各 7 天（08-08/08-15/08-29/09-05 周六、09-06 周日、09-12 周六、**10-02 国庆休市**） | `quant.simulation_equity_snapshot` ⋈ `quant.trading_calendar(exchange='ALL')`，`is_trading_day` 非真者 35 行 |
| E2 | 脏行**直接喂进归因窗口** | `POST /api/risk/metrics{account_name:agent_virtual,days:60}` → `navPoints=60`、`returnsSource=account_nav`，恰等于该账户表内 60 行；`GET /api/simulation/performance` 的 `equity_curve` 末段可见 `09-05/09-06/09-12/10-02` |
| E3 | 读取端按**行相邻**配对 | [risk_metrics_service.py:27](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/risk_metrics_service.py#L27) `nav_returns_from_snapshots` 升序逐行 `(v[i]/v[i-1]-1)`；[analysis_async.py:865](/Users/mac/Documents/ai/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/analysis_async.py#L865) `get_equity_snapshots(limit=days)` |
| E4 | 日收益基准自称"上一交易日"、实为"上一行" | [simulation_repository.py:524](/Users/mac/Documents/ai/pi-investment/quantsys-v2/adapters/outbound/repositories/simulation_repository.py#L524) docstring「取 before 之前最近一条估值完整的快照」——无日历参与 |
| E5 | 缺口探测用工作日口径（自认） | [RiskMetricsTool.ts:165](/Users/mac/Documents/ai/pi-investment/agent-dh/packages/tools/risk/src/tools/RiskMetricsTool/RiskMetricsTool.ts#L165) `basis: '按相邻快照间隔识别缺失工作日（未扣法定节假日，数字可能略高估）'` |
| E6 | 写入端门不齐：`_has_bar` 2026-09-13 才加，且 10-02 的 5 行**不是库表调度写的** | [daily_snapshot_service.py:269](/Users/mac/Documents/ai/pi-investment/quantsys-v2/application/services/evolution/daily_snapshot_service.py#L269)；`quant.scheduler_runs` 在 `2026-10-02 15:00–16:00` **0 行**，而 5 行 `created_at` 均为 `2026-10-02 15:30:2x` |
| E7 | 同族残留：休市日被当作窗口端点 | `quant.inprocess_job_runs`：`evolution_fitness` 在 `2026-10-02`/`2026-10-05` 台账 `window_end` 即休市日当天 |

### 反向证据（必须一并记录，避免为迎合而罗列）

- **R1**：`TradingDayGuard` 本身是好的——实测 `2026-10-02/10-05/10-06` 均判 `is_trading_day=False`
  （`source='trading-calendar-holiday'`）。所以本需求**不是**"日历不准"，而是"下游没用它"。
- **R2**：写入端**已有部分门**（`daily_orchestrator.tick`/`resume_from_breakpoint` 的交易日门、`_has_bar`、
  `tools/snapshot_daily.py` 的 K 线门）。问题不是"完全没门"，而是**门不齐、口径不一、且不在被调函数层**。
- **R3**：`/api/simulation/performance` 的 `max_drawdown` 取自 `simulation_account.max_drawdown`，
  而该字段由 `recompute_account_max_drawdown` 按**全序列**推导（含脏行）——清理后必须一并重算，否则半修。

## 接口与数据契约

| 接口/对象 | 现状 | 本需求后 | 兼容性 |
|---|---|---|---|
| `POST /api/risk/metrics`（`account_name` 口径） | `days` = 取快照行数上限；`navPoints` = 行数 | `days` = **交易日数**；`navPoints` = 交易日数；新增 `window{from,to,trading_days,filtered_non_trading,trading_day_source}` | 入参名不变；`days` 语义收紧（窗口变短、更准确）；老调用方无需改 |
| `GET /api/simulation/performance` | `equity_curve` = 全行（`limit=365`） | `equity_curve` 只含交易日；新增同形 `window` 字段 | 响应只减不加（字段新增，不改既有键） |
| `quant.simulation_equity_snapshot` | 任意日期可写 | **仅交易日**可写（写入闸门保证） | 键 `(account_name, snapshot_date)` 不变；不新增列 |
| `RiskMetricsTool.probeNavCoverage`（agent-dh） | `missing_weekdays`（工作日口径） | `missing_trading_days` + `trading_day_source`；`missing_count` 用新口径 | 消费方（归因文案）同步改口径；旧字段名保留一个版本以免打断读取 |
| `RiskMetricsTool` 的 `window_note` | 「[缺口] 净值序列缺 N 个工作日」 | 缺口按交易日计；无缺口时不出现该段 | 文案变更，无接口破坏 |

**迁移与回滚**：清理属**不可逆删除**，故先落 `quant.bak_equity_snapshot_nontrading_w-0a409569`
（原行整行拷贝 + `deleted_reason` + 时间戳），回滚 = 从备份表按 `(account_name, snapshot_date)` 回插再重算；
迁移脚本须带 `lock_timeout`（沿用本仓测试库 DDL 的既有要求）。

## 判定标准（可跑）

```bash
# 1) 写入端：休市日不写（四条写入路径都要过）
#    交易日 2026-09-30 正常写；休市日 2026-09-05(周六) / 2026-10-02(国庆) 拒写且零新增行
pytest tests/test_equity_snapshot_trading_day_gate.py -q

# 2) 读取端：日收益条数 = 交易日数 - 1（构造含周末/节假日行的序列）
pytest tests/test_nav_series.py tests/test_equity_snapshot_daily_return.py -q

# 3) 接口口径：navPoints = 窗口内交易日数，且回显 window
curl -s -X POST http://127.0.0.1:5001/api/risk/metrics \
  -H 'Content-Type: application/json' \
  -d '{"account_name":"agent_virtual","days":20}' | python3 -m json.tool

# 4) 缺口探测（agent-dh）：节假日不计缺口
cd ../agent-dh && npx vitest run apps/web/tests/attribution-alignment.test.ts

# 5) 存量清理可证伪：非交易日净值行数 = 0（本需求的核心判据）
#    注意：判据用 is not true（更严——要求每行都在日历里且为交易日）；
#    删除只用 is_trading_day = false（防"日历缺行"导致误删），见 design/data-model.md §3
psql -h 127.0.0.1 -U mac -d quant_investment -c "
select count(*) as nontrading_rows
from quant.simulation_equity_snapshot s
left join quant.trading_calendar c
  on c.trade_date = s.snapshot_date and c.exchange = 'ALL'
where c.is_trading_day is not true;"          # 期望 0

# 6) 派生字段一致性：逐账户比对重算结果（脚本零差异）
python tools/verify_equity_snapshot_consistency.py --accounts agent_virtual,user_main_simulation,v13_simulation,v14_simulation,v15_simulation

# 7) 不破现状
pytest tests/ -k "risk_metrics or equity_snapshot or orchestrator" -v

# 8) 真实观察（时间型）：2026-10-07 无新增行；2026-10-08 复市首日写入 success
psql -h 127.0.0.1 -U mac -d quant_investment -c "
select snapshot_date, count(*) from quant.simulation_equity_snapshot
where snapshot_date in ('2026-10-07','2026-10-08') group by 1 order by 1;"
```

> 判据 8 是**时间型条件**（需等真实休市日/复市首日），2026-10-07 与 10-08 分别是下一个休市日与复市首日；
> 在该窗口到来前，1~7 条即可判定代码侧完成，第 8 条作为上线后回执。

## 档位依据与升级信号

**重档**，三条独立依据：

1. **跨仓**：改动同时落在 `quantsys-v2`（写入闸门 + 读取过滤 + 存量清理）与 `agent-dh`
   （缺口探测口径 + 其测试），需要两侧口径同步，任何一侧单独上线都是半修。
2. **改数据契约**：`days` 的语义、`equity_curve` 的构成、`probeNavCoverage` 的返回字段都变，
   消费方（归因文案、熔断/仓位判定链）会读到不同的窗口。
3. **动生产台账**：删除 35 行净值行并重算派生字段，属不可逆数据操作，需备份与一致性校验。

**升级信号（预先登记，供后续引用）**：若实施中发现非交易日净值行**已进入过**仓位/熔断判定并影响了
实际下单（而不只是报告数字），则本需求应升级为含"决策回放与影响评估"的独立需求——本需求不预先纳入。

## 讨论与裁定记录（D-x）

| 编号 | 原话来源 | 裁定 | 影响 FR | 判据 |
|---|---|---|---|---|
| D-1 | 本窗口用户消息（2026-10-06 19:0x）：「【业绩归因】超额不可得（基准滞后）｜组合窗口 +3.99%，回撤 −0.36%｜缺口已补跑」＋「里面没有把节假日过滤了」 | 本现象立项；定性为**"交易日口径缺门"在净值链上的残留**（与 `REQ-261006093620-a315` 是同一洞的两半） | FR-1~FR-8（全部） | `reqboard_status` 显示本窗口绑定 `REQ-261006190953-fc43`；E1~E7 为现象取证 |
| D-2 | 立项弹框作答（本窗口，2026-10-06 19:09）：名称「业绩归因/风险指标窗口未按交易日取数：剔除周末与节假日的净值点」/ 类型 feature / 难度 expert / 文档位置 `docs/requirements/<REQ>/` | 本工作立项为 **feature**，难度 `expert`，文档落 `docs/requirements/REQ-261006190953-fc43/` | FR-1~FR-8 | 本文件存在且经 `reqboard_submit(kind=requirement)` 登记 |
| D-3 | 本窗口弹框作答（范围）：「全部都要修：写入端 + 读取端 + 缺口探测统一走交易日口径（推荐）」 | 范围含**三层**：写入闸门、读取过滤、缺口探测；跨仓到 `agent-dh` | FR-1、FR-2、FR-3、FR-4 | 「不做什么」第 5/6 条排除仓储双轨重构与前端；判定标准 1/2/4 逐层给可跑判据 |
| D-4 | 本窗口弹框作答（存量脏行）：「删掉这 35 行，并重算受影响的日收益/回撤链（推荐）」 | 存量 35 行**删除**（先备份），并重算 `daily_return`/`drawdown`/`peak_value`/`max_drawdown` | FR-6、FR-7 | 判定标准 5/6：非交易日行数 = 0 且重算零差异 |
| D-5 | 本窗口弹框作答（基准是否入范围）：「不入范围：只修节假日/交易日口径，基准滞后单独立项（推荐）」 | 「基准滞后 / 超额不可得」**不进本需求**，单独立项 | FR-8（口径可见化：基准不可用时如实声明，不去修基准数据） | 「成功长什么样」与判定标准均不含"超额可用"这一表述；「不做什么」第 1 条为排除项 |
| D-6 | 本窗口弹框作答（实施期 2026-10-06 20:0x，实施中实测触发）：「改谓词：日历覆盖范围内 + 不在日历清单里 → 删（白名单语义）」 | 删除谓词改用**白名单语义**：非交易日 = 覆盖范围内 **且** 不在交易日清单里；"防误删"改由**覆盖范围**承担（`min~max(trade_date)` 之外一律不动）。推翻 `design/data-model.md` §3 原谓词 | FR-6、FR-7 | 实测生产日历 23373 行 `is_trading_day` 全为 true（无一条 false），旧谓词匹配 0 行；改后生产 dry-run 命中 **35 行**且库内零改动 |

> **D-6 的确认戳说明（如实记账）**：本条裁定发生在 **implementing 阶段**，而 `reqboard_submit(kind=requirement)`
> 只在 brainstorming 阶段可用（其后报 `REQBOARD_BAD_STATUS`），**无法**经 `change_note` 纳入原确认戳。
> 故本条按内容落账于此，并在 `notes/requirement-doc-revision-20261006.md` 留痕；归档时应并入正式 D-x 一并复核。

## 下一步

下一步：design —— 用 `reqboard_ask_confirm(target=artifact, kind=requirement)` 交棒；未获批准不得进入设计/实施。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | ✅ 已接收 | t-8c7962、t-0ae23e |
| FR-2 | ✅ 已接收 | t-8c7962、t-0ae23e |
| FR-3 | ✅ 已接收 | t-1974b4 |
| FR-4 | ✅ 已接收 | t-7c5daa、t-8c7962、t-39a044 |
| FR-5 | ✅ 已接收 | t-7c5daa、t-8c7962 |
| FR-6 | ✅ 已接收 | t-5c9a67 |
| FR-7 | ✅ 已接收 | t-7c5daa、t-39a044、t-5c9a67、t-6f1c29 |
| FR-8 | ✅ 已接收 | t-0ae23e、t-39a044、t-6f1c29、t-1974b4 |

> 无未接收条款（8 条全部有落点）。

<!-- reqboard:marks:end -->
