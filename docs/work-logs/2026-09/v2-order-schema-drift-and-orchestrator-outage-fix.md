---
title: v2 订单 schema 漂移 + orchestrator 停摆修复
date: 2026-09-14
window: w-2129d492
status: 已修复并上线验证
---

# v2 订单 schema 漂移 + orchestrator 停摆修复

## 一、两条独立故障（同日发现）

### 1. ORM ↔ 数据库 schema 漂移（M5 提交 cedfb4ed 引入）

**现象**：交易时段内任何立即买卖单在 INSERT 阶段 500；盘前挂单同样不可用。

**根因**：M5 给订单加 5 列（decision_price / decision_at / price_source / fill_price /
slippage_bps）时，DDL 落在 `quant.simulation_pending_orders`，ORM 却把 5 列定义在
**错误的类** `SimulationOrder` 上 → 两侧都错位：

| 路径 | 模型 | 数据库 | 后果 |
|---|---|---|---|
| 立即单 | 有 5 列 | 无 | ORM flush 带全列 → `UndefinedColumn` → 500（实测 09-14 09:45，601857，事务已回滚） |
| 盘前挂单 | 无 | 有 | `create_pending_order` 构造即 `TypeError: 'decision_price' is an invalid keyword argument` |

**更深的结构原因**：本仓**没有迁移框架**（无 alembic / 无 schema 版本表），
`quantsys-v2/migrations/` 只有人工 SQL——模型与 DDL 是两份人工产物，没有任何一致性校验，
错误只在运行时以 `column ... does not exist` 暴露。

**顺带扫出同类漂移**：`quant.signal_executions` 模型声明 4 列（executed_at /
error_message / execution_amount / execution_volume）表里没有（当前 0 行、无写入方，未爆）。

**修复**：
- `simulation.py`：5 列从 `SimulationOrder` 移到 `SimulationPendingOrder`（埋点所在的那张表）；
- `migrations/add_execution_quality_columns.sql`（新增，幂等）：两张订单表口径对齐 +
  `signal_executions` 补 4 列；
- `tests/test_orm_db_drift.py`（新增门禁）：全模型 ORM↔DB 列比对 + 订单表 5 列锚点 +
  方向断言，堵住"改了模型不写迁移"这条路。

### 2. orchestrator 全天停摆（B3 重构 b3e476ae 引入）

**现象**：09-14 03:54:55 起 tick 线程不再启动，连续 263 次
`orchestrator/monitor tick error`，当日 9:31 盘前撮合与 T1 结算**全天未执行**（无 `market_open` 事件）。

**根因**：`trading_day_guard._kline_stats` 改为仓储取数后，
`KlineORMRepository.get_latest_trade_date()` 返回 `'YYYY-MM-DD'` 字符串（裸 SQL 时代经
psycopg2 直接返回 `date`），而 `judge_trading_day` 要做 `(today - latest_kline_date).days`
→ `TypeError`。异常沿 `resume_from_breakpoint` → `start_orchestrator` 上抛，
把 tick 线程打死。**保护性判定变成了可用性故障。**

**修复**（`trading_day_guard.py`）：
- `_kline_stats` 用既有 `_normalize()` 把取数结果归一到 `date`（取数层回 date/datetime/字符串都成立）；
- `check()` 兜底：`_compute` 任何异常 → 降级为 `SOURCE_UNAVAILABLE` + 留痕，绝不击穿调用方。

## 二、证据

| 项 | 证据 |
|---|---|
| 立即单 500 | `logs/launchd-stdout.log` 09:45:24-09:45:28 四条 `trade_transaction_failed_rollback`，错误体含 `column "decision_price" of relation "simulation_order" does not exist` |
| 挂单构造失败 | 运行时 `SimulationPendingOrder(decision_price=...)` → TypeError；测试库/生产复盘一致 |
| orchestrator 停摆 | 同日 263 次 tick error；今天无任何 `market_open` 事件 |
| 修复后（生产库） | `_kline_stats` → `(False, datetime.date(2026, 9, 11))`、`is_trading_day(today)=True`；重启后 orchestrator 完成 PRE_MARKET → MARKET_OPEN，`market_open: t1_settled`（agent_brain 1 笔）|
| 修复后（双路） | 立即单 ORM flush OK（事务回滚验证）、挂单构造+flush OK（含 decision_price） |
| 回归 | 相关测试 **94 passed**（门禁 + 交易日守卫 + 交易链路 + 动作契约 + 交易时段策略）；全套跑到 43% 会卡在网络类用例，另有 2 个失败在 main 基线同样失败（`test_get_balance`：`Balance` 缺 `total_value`；`test_trade_cash_race`：fixture `get_account` 为 None）|

### 新增测试的"标定"（用修复前源码验证新测试确实会红）

把修复前的 `simulation.py` / `trading_day_guard.py` 与新增测试放进同一个 worktree 跑：

| 新测试 | 在修复前源码上的结果 |
|---|---|
| `test_decision_quality_columns_live_on_pending_order_model_only` | ❌ `SimulationOrder（立即单）不该声明 decision_price` |
| `test_kline_stats_coerces_string_latest_date_to_date` | ❌ `assert isinstance('2026-09-11', date)` |
| `test_today_intraday_heuristic_works_with_string_repo_date` | ❌ TypeError 复现（事故原样：`unsupported operand type(s) for -: 'datetime.date' and 'str'`）|
| `test_check_tolerates_string_from_stats_even_if_coercion_is_lost` | ❌ 同上 TypeError |

两点重要说明：
1. `test_orm_columns_all_exist_in_database`（全模型 ORM↔DB 比对）在**修复前源码**上居然是通过的——
   因为它跑之前先把迁移应用到了测试库，`simulation_order` 已有那 5 列。
   **真正能挡住本次复现的是那条方向断言**（"立即单模型不许声明这 5 列"），两者互补，缺一不可。
2. 兜底降级（`trading_day_guard_compute_failed`）自 12:18 修复上线以来**从未触发**，
   说明真实路径是靠类型归一修好的，不是靠吞异常"看起来正常"。

## 三、上线

- 生产 DDL：`psql -d quant_investment -f migrations/add_execution_quality_columns.sql`（幂等，已执行）
- 服务重启：`launchctl kickstart -k gui/$(id -u)/com.pi-investment.v2-api`（12:18），health 200

## 四、遗留

- 本仓仍无迁移框架/CI 门禁，漂移检测目前只有 `tests/test_orm_db_drift.py` 一道；
  建议后续把"模型改了必须配迁移"做成提交前检查。
- `signal_executions` 补列是"防患"而非常用路径，启用该表前需补集成测试。
- 立即单表虽已补 5 列，但 ORM 侧不声明、埋点也不写——M5 原意（挂单全生命周期可追溯）
  只在挂单路径生效；若要覆盖立即单需另行设计。

---

## 五、独立审查（w-0f022172）与逐条处置

审查方式：fresh-context subagent，实际读文件 + git 历史 + 跑测试/建 scratch 库做伪证。
提 1 BLOCKER + 4 MAJOR + 5 MINOR。**B1/M1/M2/M3 我均独立复现后确认属实**（不是照单执行）。

| 编号 | 问题 | 处置 |
|---|---|---|
| **B1** BLOCKER | 迁移整文件一个 BEGIN…COMMIT：段 1 打 `quant.simulation_order`，而**本仓没有任何 SQL 建过这张表** → 新库 42P01 → 整文件回滚 → 连必需的挂单 5 列一起丢（新环境比修复前更差） | **已修**：每段独立事务 + `DO` 块 `to_regclass` 缺表即跳过；实证：新建空库按序应用全部迁移 → 挂单表 5 列**全部在位**（原版同场景 0/5）；生产重复应用仍幂等 |
| **M1** MAJOR | 门禁比对集取决于 import 历史：全套跑（import 73 个仓储）metadata 40→79 张表 → 假红；隔离跑绿 | **已修**：按"声明该表的 mapped class 是否属于 models 包"过滤；实测污染场景下恒为 40 张、3 passed |
| **M2** MAJOR | 库不可达时静默全绿（`1 passed, 2 skipped`），唯一挡复现的用例等于不存在 | **已修**：未配置/连不上/无迁移目录一律 fail；仅 `DSH_ALLOW_MISSING_TEST_DB=1` 可 skip |
| **M3** MAJOR | fixture 会对 `QUANT_DATABASE_URL` 指向的任意库重放 migrations 的 DDL（可能打到生产） | **已修**：库名必须以 `_test` 结尾，否则 fail（本仓首个会写 DDL 的测试，自设闸门） |
| **M4** MAJOR | 兜底降级把"代码 bug"伪装成"今天不是交易日"，而 orchestrator 用 `is_trading_day()` 丢掉了 degraded | **部分修**：降级结论的 reason 写明是判定异常；畸形日期入参也走降级（`check('')`/`check('garbage')` 原本仍抛 ValueError，实测已改为降级返回）。**orchestrator 改调 `check()` 保留 degraded 未做**——见"遗留" |
| m1 MINOR | `_normalize` 在 try 之外，脏日期仍击穿 | **已修**（见 M4 处置） |
| m2 MINOR | signal_executions 段属 scope creep 且放大 B1 | **已修**（分段独立事务后不再是放大器） |
| m3 MINOR | 立即单 5 列无写入方，门禁却为死状态背书 | 保留列 + 断言，迁移注释写明"供后续立即单执行质量设计使用"，避免误读为在用 |
| m4 MINOR | `to_dict()` 不暴露执行质量字段，`/pending-orders` 口径不一致 | **已修**：5 字段入 to_dict（Numeric→float，与既有字段同款） |
| m5 MINOR | `decision_at=datetime.now() if decision_price else None`，0.0 被 falsy 吞 | **已修**：改 `is not None` |

**审查确认"无问题"的部分**（可免重复劳动）：全仓这 5 列无漏改调用点；`update_pending_order_status` 确实消费 fill_price/slippage_bps；
迁移列类型与 ORM 一致（TIMESTAMPTZ / NUMERIC(10,2) / TEXT）；门禁在"模型加列不写迁移"时确实会红（伪证实验：加 zz_probe_col → FAILED）。

**审查顺带发现（不在本次 diff，未处置，建议另开需求）**：
`adapters/outbound/repositories/p2_async_repositories.py:248-258` 用 `extend_existing=True` 重复定义 `quant.automation_tasks`
（enabled/last_run/schedule），与 `automation_repository.py` 的 is_enabled/last_run_at/schedule_config **并存** → metadata 多出
3 个两库都不存在的列；该表生产有 3 行且被 `smart_scheduler` 使用 → 任何 ORM 读写都会踩 09-14 同类 500。
`market_style_state` / `risk_metrics` 同类。

## 六、遗留（更新）

- **orchestrator 侧未做**（M4 后半）：`daily_orchestrator.py` 正被另一会话的"编排器账户通用化"重构
  （main 44b469c0，-329 行），此时改会造成三方冲突；正确做法是给 tick/启动外层加 try/except（任何异常都不许打死
  tick 线程）+ degraded 时告警，而不是让"交易日判定"这一层独自承担可用性。
- 本仓仍无迁移框架/CI 门禁；`tests/test_orm_db_drift.py` 是事后闸门，**挡不住**"模型改了、迁移没写、直接重启上线"。
- 真实下单端到端（DSH `portfolio_trade` → HTTP → service → DB）与 9:31 盘前撮合链仍未实测。
- `p2_async_repositories` 重复定义 `quant.automation_tasks`（详见上）——同类漂移，未修。
