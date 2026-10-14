---
req_id: REQ-261004154902-a7cd
title: 数据契约（无 DDL、真源唯一、存量处置）
doc: design/data-model
serves: FR-1, FR-3, FR-4, FR-7, FR-10
---

# 数据模型与契约（REQ-261004154902-a7cd）

> 总览见同目录 [`design.md`](design.md)；接口见 [`interfaces.md`](interfaces.md)。

## 1. 结论：**本次零 DDL**（serves: FR-1, FR-7）

需求边界 B3 明示"不动数据库表结构"。所有落点都复用既有列：

| 契约定居点 | 表 / 列（既有） | 本次变化 |
|---|---|---|
| 任务成败与原因 | `quant.scheduler_runs.status` / `.error` / `.result`(jsonb) | `result` 内**新增键** `ok` / `reason` / `error`（超集，读旧键的调用方不受影响） |
| 挂单状态 | `quant.simulation_pending_orders.status` / `fail_reason` | `status` 新增取值 `expired`（text 列，无 DDL）；`fail_reason` 在 `failed`/`expired` 时必填 |
| 任务时刻与宽限 | `quant.scheduler_tasks.cron_expression` / `.misfire_grace_time_seconds` | **仅数据行**改动，见 §3 |

## 2. 交易日真源：`quant.trading_calendar`（serves: FR-3）

- **实测（2026-10-04，本窗口）**：真实表（`relkind='r'`），
  `exchange ∈ {SSE, SZSE, ALL}` 各 **7791** 行（合计 23373），覆盖 `1994-03-01` ~ `2026-12-31`；
  **只存交易日、`is_trading_day=false` 行数为 0**；正确排除国庆（`2026-10-05/06/07` **无行**）、
  正确包含 `2026-10-08`（而 `daily_klines` 最新只到 `2026-09-30`）。
- **判定语义**：某日 `(trade_date, exchange)` 有行 ⇔ 该日该交易所开市；
  查询用 `exchange='ALL'`（或按调用方语义），**不得**用"有无 K 线"替代。
- **刷新责任**：既有脚本 `tools/refresh_trading_calendar.py`（从 `daily_klines` 的
  `DISTINCT trade_date` 灌数据）。**已知缺口**：K 线天然没有未来交易日 ⇒ 只靠该脚本会让表
  "刚填好就过期"；因此本设计**沿用 `trading_day_resolver` 的降级链**
  （表 → `DataProviderManager.get_trading_calendar` → 周一~周五回退 + `degraded=True`），
  不把表当唯一来源。
- ⚠️ **文档口径需同步**：`docs/requirements/REQ-261004102115-d3de/design/architecture.md:54`
  写的"`quant.trading_calendar` **当前 0 行**"与本窗口实测（23373 行）**不符**——该表在此期间
  已被回填。本设计以**实测**为准，并把该矛盾登记为需要同步的文档项（不静默改别人的文档）。

## 3. `scheduler_tasks` 的数据行改动（serves: FR-4）

| 对象 | 现值（**留档以便回滚**） | 目标值 | 理由 |
|---|---|---|---|
| `name='v13-simulation-trading'`（id=249）`cron_expression` | `30 6 * * 1-5` | `30 14 * * 1-5` | 与 `v13.yaml schedule` / docstring / `docs/FEISHU_NOTIFICATIONS.md` 的 14:30 声明一致（现值为 06:30 盘前，历史实跑为 14:30） |
| 同上 `misfire_grace_time_seconds` | `NULL`（但加载器 `or 300` → 有效 300 秒） | `NULL` + **修加载器语义** | 本仓口径"NULL=唤醒必补跑"在代码里不成立；10-02 实证丢过一次排班 |
| 新增行 `pending-orders-match` | 不存在 | `command='pending_orders_match'`、`cron='31 9 * * 1-5'`、`misfire=NULL` | 撮合不再只依赖 orchestrator 相位，且失败能落 `scheduler_runs` |
| id=257（disabled，`command='v13_trading'` 无 handler） | 保留 | **不动** | 仅作噪声源登记，不在本次删除 |

- 存量挂单：两笔 `agent_virtual` 的 `pending`（id=7 买 688169、id=8 买 601888，
  自 `2026-08-24` 起 `updated_at == created_at`）→ 按 `expired` 规则处置（**人裁定**，见 `use-cases.md` §5）。

## 4. 账本契约（serves: FR-10）

- **唯一真源**：`quant.simulation_trades`（净额口径 = `ΣBUY - ΣSELL`）；
  `_rebuild_portfolio_from_trades` 已是该口径的实现，**保留并收紧**：
  `quant.simulation_positions` 只能由它派生，**不得**成为第二条写入路径
  （双源正是虚增现金的成因，实证：4 只标的 `ΣSELL > ΣBUY`，虚增 ≈ ¥49,425）。
- **卖出前置校验（新增）**：`ΣBUY(shares) - ΣSELL(shares) >= 本次卖出量`，否则拒绝 +
  `reason='oversell_blocked'` + 告警（判据可跑：超卖清单必须 0 行）。
- **现金重放口径**（对账器 `tools/reconcile_sim_account.py`）：
  `cash_expected = 初始资金 + Σ(SELL total_revenue) - Σ(BUY total_cost) - 其它费用`，
  与 `quant.simulation_account.cash_available` 比对，**差额必须逐项可解释**。
- **历史虚增的处置不在本设计内**（§13 决策 2）：回填冲正 / 标记为脏并从统计排除 / 保留不动，
  三选一由人定；本设计只保证"不再产生新的虚增"。

## 5. 迁移、回填与兼容（serves: FR-1, FR-4, FR-7）

- **迁移**：无 DDL、无新增表、无数据回填脚本；`status='expired'` 为 text 列新取值，
  旧版本代码读到该值不会崩（不做枚举校验）。
- **兼容**：`RunOutcome.to_dict()` 为既有键超集；`reason` 枚举只增不改；
  `scheduler_runs.result` 只加键。
- **回滚**：§3 表格右列改回左列（左列即原值，已留档）+ 对应 commit revert；
  开关 `V13_CHAIN_STRICT=false` 可即时退回旧判定。
