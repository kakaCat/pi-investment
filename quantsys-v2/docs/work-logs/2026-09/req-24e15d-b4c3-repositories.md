# REQ-24e15d B4-c3：四个仓储落 ORM（2026-09-14，w-32314d00）

需求：REQ-24e15d（quantsys-v2 裸 SQL 全量迁 ORM）· 批次 B4-c3（t5 仓储内收敛）
起点 HEAD：`b4d3a547`

## 0. 一句话

四个仓储文件（risk / kline / chip / strategy_performance）共 **33 处**裸 SQL 归零，
全部走 `session`；每一处都用**真实库跑新旧两版逐值比对**验证，而不是靠"看着对"。

## 1. 结果

| 文件 | 迁移前 | 迁移后 | 行数 |
|---|---|---|---|
| `risk_repository.py` | cursor_execute **10** | **0** | 736 → 679 |
| `kline_repository.py` | core_text_sql **7** + fstring_sql **1** | **0** + **0** | 1416 → 1545 |
| `chip_repository.py` | core_text_sql **7** | **0** | 223 → 249 |
| `strategy_performance_repository.py` | cursor_execute **7** | **0**（整文件不再出现在扫描结果里） | 354 → 309 |

本轮范围合计：
`cursor_execute` **42 → 25**，`core_text_sql` **25 → 11**，`fstring_sql` **4 → 3**，
P0 两项恒为 0，`--gate` 退出码 0。

`session_execute_var`（**审计桶**，扫描器明确声明"正则无法判定装的是 SQL 还是 ORM 构造"）
53 → 60：新增的全部是 `pg_insert(...)` / `select(...)` 构造后执行的 Core 语句，
**不是**裸 SQL。这一项按设计不作为验收值。

## 2. 逐文件要点

### 2.1 risk_repository.py（10 处 cursor_execute）

- 十个方法（balance 5 + risk_metrics 4 + latest 1）全部落 ORM；
- **删掉 `db` 属性**——它用 `session.connection().connection` 掏出 psycopg2 裸连接、
  绕开 session 管理与 session_guard，是 B4-c2 在 portfolio_repository 里关掉的同一个后门；
- 两个 UPSERT 改用 `pg_insert(...).on_conflict_do_update(...)`，冲突分支**只更新本次真正提供的列**
  （旧 SQL 无条件把 9/8 列全写成 EXCLUDED）；
- 返回 dict 的键集合与 `SELECT *` 完全一致（含 `created_at`），用显式列元组固定，不依赖 `to_dict()`。

### 2.2 kline_repository.py（7 + 1）

- `get_index_daily_klines` 的 f-string 拼 SQL 改为 Core `select()`；
- 6 个全市场 CTE/窗口函数查询（breadth / turnover / returns / high-low / active-symbols /
  breadth-history）改为 Core `select()` + `func.row_number().over()` / `func.lag().over()` /
  `func.count().filter()` / 窗口帧；
- 窗口起点保持**服务端** `CURRENT_DATE`（`func.current_date() - timedelta(days=n)`），
  没有退化成客户端日期。

### 2.3 chip_repository.py（7）

- 7 处 `text()` → Core；两个 UPSERT 走 `pg_insert`；
- `get_symbols_with_pending_klines` 的 CTE 改为子查询 + `outerjoin`。

### 2.4 strategy_performance_repository.py（7）

- **新增 ORM 模型** `StrategyPerformance`（此前根本没有：文件名叫 ORM Repository，
  实现却全程 `db_cursor()` + 裸 SQL）；
- 类改为继承 `BaseORMRepository`，保留 `__init__(db_connection=None)` / `close()` /
  上下文管理器三个兼容入口；
- `get_statistics` 的 `SUM(CASE WHEN ...)` → `func.sum(case(...))`，
  `get_by_scenario_tag` 的 `scenario_tags::text LIKE %s` → `cast(jsonb, Text).like(绑定参数)`。

## 3. 验证方式（本批的重点）

**不看代码，看两版在真实库上跑出来的值。** 手法：
`git show HEAD:<file>` 取出迁移前实现 → 独立模块加载 → 与迁移后实现跑同一批调用 → **逐值比对**。

分进程 vs 同进程：risk / kline / chip 三个文件的 ORM 类与 HEAD 版**共用一个 `Base`**，
同进程加载会撞 `Table ... is already defined`，故 chip 走**分进程 dump 成 JSON 再比**；
strategy_performance 的 HEAD 版没有 ORM 类，可同进程直接比。

| 文件 | 验证覆盖 | 结果 |
|---|---|---|
| risk_repository | account_balance 真实 28 行只读等价 + 空区间 + 两个 UPSERT 的插入/冲突分支 | ALL PASS |
| kline_repository | 3 个真实指数 × fields 变体 + 6 个全市场聚合 × 正常/空窗口 | ALL PASS |
| chip_repository | 真实 5237 条 pending / 3820 根K线 / 63377 条指标 + 两个 UPSERT 分支 | ALL PASS |
| strategy_performance | 6 行合成样本覆盖盈/亏/未平仓 × 2 策略 × 2 来源 × 场景标签 + create/update_exit | ALL PASS |

**等价性验证抓到了两个我自己写出来的真 bug**（都不是"看着像对"就能发现的）：

1. `over(rows=(4, 0))` 被 SQLAlchemy 渲染成 `ROWS BETWEEN 4 FOLLOWING AND CURRENT ROW`
   → PG 直接报 `WindowingError: frame starting from following row cannot have preceding rows`。
   SQLAlchemy 的 rows 元组语义是**负=PRECEDING、0=CURRENT ROW、正=FOLLOWING**，正确写法 `(-4, 0)`。
   若没有真实库比对，这段代码会在 regime 回填（M1 市场感知）时才炸。
2. `func.nullif(x, 0)` 被 SQLAlchemy 硬编码返回类型 `Numeric()`，把除法渲染成
   `... / CAST(nullif(...) AS NUMERIC)` → numeric 除法与旧 SQL 的 double precision 除法
   **末位不一致**（`0.9767216403301303` vs `0.9767216403301268`）。
   改为在 Python 侧实现 `NULLIF` 语义，恢复 double precision 结果。

另外跑等价性时，我自己的**校验脚本**先后写错 3 处（比对时没排除按设计不同的
`id/created_at/symbol`；把 DB 默认值 0 误当 NULL；清理谓词漏掉新造的行），
每处都是脚本假设错、不是被测代码错——已逐一改正后重跑至全绿，没有把"脚本错"记成"代码对"。

## 4. 回归

- 定向：`test_risk_repository` + 5 个 kline 测试 + `test_strategy_performance_repository`
  + `test_experience_accumulator` + `test_sector_rotation` = **133 passed**；
- `test_risk_repository.py` 由 **32 passed / 3 skipped → 35 passed / 0 skipped**：
  3 个写入用例原先**从未真正执行过**（旧 raw SQL 缺可选字段即 `KeyError`，被
  `pytest.skip` 兜底成"跳过"），迁移后首次跑通。

## 5. 本批修掉的静默缺陷

1. **risk 的两个写入路径从未被执行过**：`save_balance` / `save_risk_metrics` 的 raw SQL 用
   命名参数占位符取 dict，可选字段缺键时 psycopg2 抛 `KeyError` 并被包装成"保存失败"，
   测试一律走 `pytest.skip`。ORM 版按 docstring 语义处理，写入路径第一次真正跑起来。
2. **`get_index_daily_klines` 的列序不确定**：默认列序取自 **set**（`allowed`），
   集合迭代序随进程哈希种子变化 ⇒ `fields` 不传时返回 dict 的键序每次运行都可能不同。
   已改为确定性元组序。
3. **`risk_repository.db` 裸连接后门**（见 2.1）。

## 6. 发现但**未修**的既有缺陷（留给用户裁定）

`GET /api/report/daily` **当前返回 500**：

```
$ curl -s -w '%{http_code}' http://127.0.0.1:5001/api/report/daily
HTTP 500 {"error":"symbol和metric_date至少需要提供一个"}
```

`adapters/inbound/fastapi_app/routes/report_async.py:22` 调用 `risk_repo.get_risk_metrics()`
**不传任何参数**，而该方法（及其单测 `test_get_risk_metrics_no_params`）要求
"symbol 与 metric_date 至少提供一个"。路由意图显然是"取最新一条风险指标"
（它随后用 `risk_summary.get('metric_date')` 当日期），但**没有任何方法表达这个语义**。

修法有二，需用户选一个（本轮未动，避免顺手改变被单测固化的契约）：
- (a) 加一个 `get_latest_risk_summary()`（取全表最新一行），路由改调它；
- (b) 放宽 `get_risk_metrics()` 的必填约束（会与现有单测冲突，需同步改测试）。

## 7. 下一批（B4-c4）建议

按"分层违规优先"排序（REQ §3.1 要求 SQL 只允许出现在 `adapters/outbound/repositories/`）：

| 文件 | 站点 | 层次 |
|---|---|---|
| `application/services/weekly_report_service.py` | cursor_execute 1 | **应用层违规** |
| `application/services/attribution_service.py` | cursor_execute 1 | **应用层违规** |
| `application/services/risk_check_service.py` | cursor_execute 1 | **应用层违规** |
| `application/services/data_pipeline_service.py` | cursor_execute 2 | **应用层违规** |
| `application/services/strategy_weight_adjuster.py` | cursor_execute 1 | **应用层违规** |
| `application/services/core_plan_service.py` | cursor_execute 1 + read_sql 1 | **应用层违规** |
| `application/services/strategy_validation_service.py` | core_text_sql 2 | **应用层违规** |
| `application/services/strategy_rotation_engine.py` | core_text_sql 1 | **应用层违规** |
| `application/services/data_quality_service.py` | core_text_sql 1 | **应用层违规** |
| `application/services/watch_engine/notifier.py` | core_text_sql 1 | **应用层违规** |
| `routes/signals_async.py` | cursor_execute 5 + fstring_sql 1 | **路由层违规** |
| `routes/stock_async.py` | cursor_execute 2 | **路由层违规** |
| `signals_async.daily_jobs_bootstrap` | cursor_execute 1 | 路由层违规 |
| `repositories/signal_tracking_repository.py` | cursor_execute 6 | 仓储内（**注意**：自带裸连接自愈机制，且有专门测试 `test_signal_tracking_connection.py` 固化该机制，迁移需同步处理该测试） |
| `repositories/strategy_repository.py` | core_text_sql 2 + cursor_execute 1 | 仓储内 |
| `repositories/competition_repository.py` | core_text_sql 3 | 仓储内 |
| `repositories/scheduler_repository.py` | core_text_sql 1 | 仓储内 |
| `repositories/ml_model_repository.py` | cursor_execute 1 | 仓储内 |
| `repositories/strategy_evolution_run_repository.py` | cursor_execute 1 | 仓储内 |
| `utils/symbol_classifier.py` | cursor_execute 1 | 工具层 |
| `application/services/qlib/qlib_data_adapter.py` | read_sql 3 | **应用层违规** |
| `application/services/strategy_evaluation_service.py` | read_sql 1 | **应用层违规** |

**应用层 + 路由层共 18 处**才是本轮真正的架构目标（§3.1 分层归位）；
仓储内剩下的都是 Core `text()`/cursor 的零散收尾。
