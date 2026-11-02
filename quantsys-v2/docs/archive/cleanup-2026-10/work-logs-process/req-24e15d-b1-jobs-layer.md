# REQ-24e15d 批次 B1 —— jobs 层裸 SQL 收敛（t4 前半）

- **执行窗口**：w-32314d00（investor / 投资脑）
- **日期**：2026-09-13 ~ 2026-09-14
- **批次范围**：6 个 jobs 文件，15 处 `cursor_execute`（+ 3 处死代码）
- **验收口径**：逐文件回归测试 + `tools/non_orm_sql_scan.py --gate`（P0 必须为 0）

---

## 0. 前置：修掉扫描器自身的盲区（否则"改完了"是假的）

**发现**：`cursor_execute` 的原口径是正则 `\bcursor\.execute\(` —— **只认变量名恰好叫 cursor** 的调用。
实测漏计两类真实裸 SQL：

| 漏计形态 | 实例 |
|---|---|
| `cur.execute(...)` | `kline_update_job._count_missing_amount` 等 3 个自检查询（**此前完全没被数到**） |
| `conn.execute(...)` / `c.execute(...)` | `portfolio_breaker_service`、`utils/symbol_classifier` 等 |

这意味着基线计数**系统性偏低约 40%**：验收看着绿、实际没改完——正好是扫描器文档开头警告的
"把改得多当改得好"的反面。

**处置**：把口径改为"**任意 `.execute/.executemany` 接收者**"，再剔除两类误报：
1. 非 DB 对象：`self.indicator_executor.execute(...)`（策略执行器，与数据库无关）——
   实测第一版宽化时被误数，故加接收者白名单（cursor/cur/c/conn/connection/db/cx + session/engine）；
2. SQLAlchemy 构造器入参：`execute(select()/text()/insert()/update()/delete())` 属 ORM 正常写法。

新增审计桶 `session_execute_var`（P2，人工复核用）：`session.execute(<标识符>)` 无法用正则判定
它装的是 SQL 还是 ORM 构造（本仓 43/48 是 `stmt=select(...)`，属正常）。**不隐藏、也不当作待办**。

**重定基线**（本轮范围 = 非 scripts|tools|live_trading）：

| 指标 | 修口径前 | 修口径后 | 说明 |
|---|---|---|---|
| cursor_execute | 111 | **124** | +13 处真实漏计 |
| session_execute_var | — | 48 | 新增审计桶 |

---

## 1. 改动清单

### 1.1 `infrastructure/jobs/verification_job.py`（2 → 0）

- `_get_index_return` 改走 `KlineORMRepository.get_index_return('399006', …)`。

### 1.2 `infrastructure/jobs/weekly_report_job.py`（2 → 0）

- 同源改动。`_calculate_position_returns` 在上一批已收口。

### 1.3 `infrastructure/jobs/risk_check_job.py`（3 → 0）

- `_get_index_return_since_start` → 仓储指数口径；
- `_get_losing_stocks`：裸 SQL 取现价 → `get_last_close_on_or_before`，
  **并把仓储实例提到循环外**（原先每只持仓新建一个仓储 = N 个 session，既是裸 SQL 也是泄漏源）。

### 1.4 `infrastructure/jobs/strategy_risk_check_job.py`（2 → 0）

- `_get_current_price` → 仓储方法；
- 股票名查询（`SELECT name FROM quant.stocks`，原来还套着裸 `except:`）→ 新增 `_get_stock_name`
  走 `StockORMRepository.get_by_symbol`，异常有明确语义。

### 1.5 `infrastructure/jobs/kline_update_job.py`（3 → 0，**实际 6 处**）

新口径下暴露 3 处此前不可见的自检 SQL。全部收敛到新仓储：

- 选股 4 个 scope 的 SQL → `KlineSyncRepository.select_sync_universe`；
- 写入循环的手写 INSERT → `KlineSyncRepository.upsert_fetched_klines`（内部走
  `batch_insert_daily_klines`，即 daily_klines 的**唯一写入口**）；
- 3 个写入后自检 → `count_missing_amount` / `detect_amount_scale_anomalies` /
  `detect_volume_unit_anomalies`。

作业层因此**不再持有 engine / raw_connection / cursor，也不再有 SQL 文本**。

### 1.6 新增 `adapters/outbound/repositories/kline_sync_repository.py`

承载上述查询与自检。**为什么保留 SQL 而不硬转纯 ORM**（逐处评估结论，写进模块 docstring）：

- 选股宇宙是集合式查询（CTE + UNION ALL + 陈旧度排序），展开成 ORM 会退化成多次往返 + Python 侧合并；
- 量纲自检用 `percentile_cont` 分组统计，属分析型 SQL。

红线仍然守住：SQL **只允许出现在仓储层**、取值一律具名绑定（`:name`）、标识符不参与拼接。

### 1.7 新增 ORM 模型 `IndexDaily`（`infrastructure/persistence/orm/models/stock.py`）

`quant.index_daily` 此前**没有 ORM 模型**（只有一处 `session.execute(text(...))` 硬读）。
补上后指数取价才有真正的 ORM 通道。字段/约束按 `information_schema` 实测对齐（只声明 schema，
不额外声明 Index，避免 `create_all` 建出线上不存在的索引）。

---

## 2. 期间发现的两个**真 bug**（都已修）

### 2.1 基准收益**长期恒为 0.0**（三处）

`verification_job` / `weekly_report_job` / `risk_check_job` 都在读"创业板指 399006 的区间收益"，
写法清一色是 `SELECT close FROM quant.daily_klines WHERE symbol='399006'`。

**而指数自 2026-09-11 起与个股分表**（w-f4aa1f6a）：`daily_klines` 里 399 族 **0 行**（实测），
指数在 `quant.index_daily` 且键带市场后缀（`399006.SZ`，实测 268 行）。

⇒ 三处的"基准收益"**一直返回 0.0**：验证/周报里的超额收益被系统性高估，风险检查的"跑输指数"退化成"跑输 0"。

**修法**：仓储新增指数口径方法（`get_index_return` 等），并在取数为空时显式 `logger.error`
——**不再把"没取到"静默当成"收益为 0"**。

活体验证：`get_index_return('399006','2026-08-01','2026-09-11') = +0.59%`（此前恒 0.0）。

### 2.2 同步宇宙混入 4 个指数占位行

`quant.stocks` 里有 4 行指数占位记录（`000300 沪深300` / `399001 深证成指` / `399006 创业板指` /
`399300 沪深300(深)`，全部 `list_date IS NULL`），它们能通过 `^[0-9]{6}$` 形状过滤
⇒ **每次同步都白白请求这 4 个指数**，取回的价格只能在写入口被 `filter_index_rows` 丢弃（每日刷 4 条告警）。
更危险的是：写入口那道闸门一旦被绕过，就是 `chk_daily_klines_no_indexrows` 约束违规——
正是 585f5a3f 等 5 起事件的历史路径。

**修法**：在 `select_sync_universe` 出口用 `utils.symbol_classifier.is_index_symbol` 剔除，
**与写入口同一套语义**（白名单 + stocks 表 list_date 定夺歧义码），不另写一份规则以免漂移。
实测：`all` 5277 只（原 5281）、`gem` 1347、`priority` 642、`batch` 688，指数残留 0。

### 2.3 顺带：upsert 不再把 `source` 抹成 NULL

`batch_insert_daily_klines` 的 `ON CONFLICT DO UPDATE` 原本无条件写 `source = excluded.source`；
调用方不带来源时（每日同步就是）会把既有来源**逐日抹成 NULL**。改为
`coalesce(excluded.source, source)`：有新值才覆盖。
活体验证：同步 600519/000001 后 `source` 保留（`sina`/`tencent`），未被清空。

---

## 3. 死代码裁决：删除 `kline_priority_sync.py`（3 处）

该模块 3 个函数全是裸 SQL。核查：全仓 grep **零引用**（含非 .py 文件）、
DB 侧 `quant.scheduler_tasks` 43 行 / `quant.jobs` 55 行**均无命中**、
其分层选股逻辑已被 `kline_update_job` 的 `scope='priority'/'batch'` 完整覆盖、
模块自身 docstring 也写着"保留待接线或后续评估删除"。

**裁决 = 删除而非迁移**：迁移"无任何调用方"的死代码无法被任何测试或调用验证，属"假通过"风险。
已记 `decision_audit`（DEC-20260914000436-a6779751）。
恢复路径：`git show 942ddfa8:quantsys-v2/infrastructure/jobs/kline_priority_sync.py`。

---

## 4. 验证证据

- **回归**：20 个相关测试文件 **162 passed / 0 failed**（含本批新增/改写的
  `test_kline_update_throttle`（8）+ `test_kline_update_selection`（5）+ `test_kline_amount_fix`）。
- **活体端到端**：`update_gem_klines(scope='all', symbols=['600519','000001'], days=5)`
  → `status=success, total=2, success=2, failed=0`，两条 `Successfully upserted 3 daily klines`，
  三个自检正常返回（amount_missing=1、量级异常 0、量纲异常 9）。
- **闸门**：`non_orm_sql_scan.py --gate` → **P0 = 0，退出码 0**。
- **两个"非本批"的失败已用 HEAD 干净 worktree 复现确认为既有问题**（不是我引入的）：
  `test_cninfo_disclosure`（2 failed）、`test_scheduled_jobs_account_value::test_compute_and_persist_via_factor_stage`（1 failed）。
  另：全量 `pytest tests/` 在本机会在 `tests/services/test_strategy_factor_injector.py` 处崩溃（重原生依赖），
  故本仓采用逐文件定向回归，不做全量跑。

---

## 5. 指标变化（本轮范围）

| 指标 | B1 前 | B1 后 | 变化 |
|---|---|---|---|
| P0 fstring_value_interp | 0 | 0 | — |
| P0 raw_connect | 0 | 0 | — |
| **P1 cursor_execute** | **124** | **106** | **−18** |
| P1 core_text_sql | 35 | 35 | — |
| P2 session_execute_var（审计桶） | 48 | 48 | — |
| P2 read_sql | 5 | 5 | — |

`infrastructure/jobs/` 目录由 6 个文件 15 处 → **3 个文件 7 处**（`data_quality_check_job` 2、
`financial_data_update_job` 3、`financial_timeliness_check_job` 3），全部属 **B2** 批次。

---

## 6. 下一批（B2，约 16 处）

`financial_data_update_job` / `financial_timeliness_check_job` / `data_quality_check_job` /
`sector_snapshot` / `data_quality_async`（text() + 白名单模板已备），
之后 B3 服务与路由层、B4 仓储内、B5 read_sql 单点。
