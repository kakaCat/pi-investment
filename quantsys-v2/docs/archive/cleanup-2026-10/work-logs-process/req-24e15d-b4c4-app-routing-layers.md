# REQ-24e15d B4-c4：应用层 + 路由层裸 SQL 收口

- **需求**：REQ-24e15d「quantsys-v2 裸 SQL 全量迁 ORM」（计划 §3.1：SQL 只允许出现在 `adapters/outbound/repositories/`）
- **窗口**：w-32314d00　**日期**：2026-09-14
- **批次**：B4-c4（路由层 3 文件 + 应用层 12 文件）
- **验收口径**：`tools/non_orm_sql_scan.py --gate` 退出码 0（P0 = 0）

---

## 0. 一句话结论

路由层与**应用层全量**（读路径 6 文件 + 写路径 6 文件）的裸 SQL 全部收口到仓储层，
等价性在真实库上逐值/逐字节验证（含负对照），并**顺带修好一个长期静默返回空持仓的接口**。

同时发现并修复了**两处度量缺陷**——共同特征是：**尺子比被测代码更早撒谎**。

---

## 1. 度量前置修正（单独 commit，不混进业务改动）

### 1.1 `core_text_sql` 漏计 `conn.execute(text(...))`（commit `d698dc89`）

原正则写死 `session\.execute\(\s*text\(` —— **只认接收者恰好叫 session** 的调用。

| | 修前 | 修后 |
|---|---|---|
| 本轮范围 `core_text_sql` | 11 | **39** |

**同一棵树、只换尺子**，纯度量变化新暴露 **+32**（逐文件清单见 commit message，全部是既有漏计）。

为什么这是最坏的方向：

- **改了不记功**：`daily_jobs_bootstrap.py` 一个文件就漏计 11 处真实 SQL，全改成仓储后指标**纹丝不动**；
- **验收看着绿、实际没改完**：指标为 0 不等于没有裸 SQL。

> 当日 `daily_jobs_bootstrap.py` 的 11 处**先修完再换尺子**，故不在 +32 之列；
> 若先换尺子会读到 39+11 = **50**。「度量改了」与「活干了」必须分开记账。

### 1.2 `docstring_lines` 在 SyntaxError 时返回空集 → 指标虚高

坏文件（如 docstring 里内联三引号 SQL）无法解析时，原实现 `return set()` ——
**返回空集等于断言「本文件没有 docstring」**，于是文件里所有 docstring 都被当成代码行扫，
指标**向上虚高**。你恰好在排查一个坏文件时，尺子自己先撒谎。

隔离夹具实测（`/tmp/scantest`，已清理）：

| | 旧尺子 | 新尺子 |
|---|---|---|
| `utils/broken.py`（语法坏） | `core_text_sql=1` ← **幽灵命中** | 计入 `unparseable`，**0 计数** |
| `utils/ok.py` | `cursor_execute=1` | `cursor_execute=1` |

现改为显式返回解析失败标志，`scan()` 跳过该文件并在报告里**单列**（文字 + JSON `unparseable` 字段）。
**当前树没有任何不可解析文件**，故本次不改变任何数字——修的是陷阱，不是数。

---

## 2. 路由层（3 文件）

| 文件 | 修前 | 修后 | 迁到 |
|---|---|---|---|
| `adapters/inbound/fastapi_app/routes/signals_async.py` | 6（cursor_execute 5 + fstring_sql 1） | **0** | `SignalORMRepository.get_signal_statistics`、新建 `AgentLogRepository` |
| `adapters/inbound/fastapi_app/routes/stock_async.py` | 2 | **0** | `PositionORMRepository.get_open_positions` |
| `adapters/inbound/fastapi_app/daily_jobs_bootstrap.py` | 1 计数 + **11 漏计** | **0** | `JobRunRepository`（读写）、`KlineORMRepository.get_kline_coverage`、`FactorORMRepository.get_max_factor_date`、`WatchRuleRepository` / `WatchTriggerRepository` |

### 2.1 新建 ORM 模型 `quant.agent_logs`

该表此前**没有 ORM 模型**，全仓唯一入口就是这个路由。模型的约束**不是照 DDL 抄的**，
是从 `pg_constraint` 实读的：

    agent_logs_action_type_check | CHECK (action_type = ANY (ARRAY['analysis','signal_generation','order_creation','position_update','risk_check']))
    agent_logs_status_check      | CHECK (status = ANY (ARRAY['success','failed','partial']))
    agent_logs_pkey              | PRIMARY KEY (id)

### 2.2 新建 ORM 模型 `quant.trading_calendar`
复合主键 `(trade_date, exchange)`；同一天 SSE/SZSE/ALL 各一行，故必须按 exchange 过滤。

### 2.3 建表口径收口（`_DDL` 删除）
`daily_jobs_bootstrap._ensure_table` 原先内联一份手写 DDL，而 `models/job_run.py` 里还有一份模型——
同一张表两处定义。现改为 `InProcessJobRun.__table__.create(checkfirst=True)`，模型是唯一真源。
模型补了 `server_default=now()`，否则新环境建出来的表会少这个默认值。

**逐列核对证据**（模型 vs `information_schema`）：PK 一致、列差异「（无）」、生成 DDL 与删除的 `_DDL` 逐列等价。

---

## 3. 应用层（12 文件）

### 3.1 读路径（6 文件）
| 文件 | 迁到 |
|---|---|
| `watch_engine/notifier.py` | `StockORMRepository.get_name` |
| `strategy_rotation_engine.py` | `MarketStyleORMRepository.get_recent_style_history`（按 **created_at**，不是 trade_date） |
| `opportunity_to_watch_rule_service.py` | `KlineORMRepository.get_latest_close` + `WatchRuleRepository.update_fields`（复用） |
| `weekly_report_service.py` | `SignalTrackingRepository.get_signal_stats` |
| `attribution_service.py` | `SignalTrackingRepository.list_signals_between` |
| `data_pipeline_service.py` | `TradingCalendarRepository.list_trading_days` + `KlineORMRepository.list_distinct_trade_dates_since` |

`SignalTrackingRepository` 的两个新方法**沿用**既有的 `_ensure_connection` 自愈连接 +
`_end_read` 事务收尾（本批不动该机制）；其专用回归测试 `tests/test_signal_tracking_connection.py` 5 passed。

### 3.2 写路径（6 文件）
| 文件 | 迁到 |
|---|---|
| `risk_check_service.py` | `PortfolioORMRepository.get_trades_by_date_and_symbol`（PG 函数，仓储内 text()+绑定参数） |
| `strategy_weight_adjuster.py` | `StrategyPerformanceRepository.get_market_style_aggregates` |
| `strategy_validation_service.py` | `BacktestORMRepository.get_strategy_evidence_since` + `StrategyORMRepository.has_validation_report_since` |
| `data_quality_service.py` | `KlineQualityRepository.record_check_result`（ORM insert） |
| `strategy_lifecycle_service.py` | `get_strategy_config_snapshot` + `retire_strategy_config`（同事务） |
| `qlib/qlib_data_adapter.py` | 新建 `QlibDataRepository`（绑定参数） |

---

## 4. 等价性验证（全部在真实库上，比**结果**不比 SQL 文本）

| 验证对象 | 方法 | 结果 |
|---|---|---|
| `/api/signals/statistics` | 老内联 SQL vs 新仓储，5 个区间（含 18401 行非空、必然空集） | **0 处不一致** |
| `/api/agent/logs` | **表当前 0 行 → 造 6 行探针**（取值受两条 CHECK 约束），11 个筛选/分页组合 | **0 处不一致**，探针清净 |
| `get_kline_coverage` | 5 个基准日（全新鲜 / 部分 / **全部陈旧**） | **0 处不一致** |
| `JobRunRepository` 读写 | 同输入写两组标记行，比对**写入后的行**；13 项检查 | **13/13 通过** |
| 应用层 7 段载荷 | 老实现从 `git show HEAD` 落到 /tmp 加载，两进程各 dump JSON | **逐字节相同（455,365 字节）** |

台账 13 项覆盖：UPSERT 清 `finished_at/error` 但**保留 `result`**、1500 字符 error 截断到 1000、
`result` 里 datetime 走 `default=str`、3 日窗口边界（含窗口外排除）、孤儿判死前后状态、未过宽限期不动。

### 4.1 负对照（**证明比对脚本有鉴别力，不是恒真**）
把老实现做 3 处定向变异后重比：

    变异1 v2: ORDER BY created_at DESC -> ASC
    变异2 v4: signal_date >= %s -> > %s
    变异3 v6: 日历 WHERE 追加 trade_date > '2020-01-01'

    负对照检出差异段 = ['v2', 'v4', 'v6']   <- 恰好等于被变异段
    等价性差异段     = []                    <- 老 vs 新

**这道防线本次拦下了两个真实误判**，见 §6。

---

## 5. 发现并修好的静默缺陷

### 5.1 `GET /api/stocks/my-stocks` 长期返回空持仓
修复前实测：

    $ curl -s http://127.0.0.1:5001/api/stocks/my-stocks
    {"success":true,"data":{"positions":[],"watchlist":[{"symbol":"600519","name":"贵州茅台"}]}}

同期 `quant.positions` 有 **12 行 `status='open'`**。

根因：`ds.portfolio` 恒为 `None`（DataService 已切 ORM 模式，不再暴露 `.portfolio`），
`ds.portfolio.db` 必抛 `AttributeError`，而整段被 `except Exception: pass` 吞掉。
迁移后不再依赖这个已消失的接口，静默失效随之消除（修复前证据已写进代码注释）。

**修复后实测（重启 5001 后 curl，2026-09-14）：**

    $ curl -s http://127.0.0.1:5001/api/stocks/my-stocks
    {"success":true,"data":{"positions":[{"symbol":"000999","name":"华润三九"},{"symbol":"601398","name":""},
     {"symbol":"600036","name":"招商银行"},{"symbol":"601088","name":"中国神华"},{"symbol":"601288","name":"农业银行"},
     {"symbol":"9988","name":"阿里巴巴"},{"symbol":"01810","name":"小米集团"},{"symbol":"00700","name":"腾讯控股"},
     {"symbol":"600600","name":"青岛啤酒"},{"symbol":"600900","name":"长江电力"},{"symbol":"512880","name":"证券ETF"},
     {"symbol":"000425","name":"徐工机械"}],"watchlist":[{"symbol":"600519","name":"贵州茅台"}]}}

返回 12 条 = 库里 `status=open` 的 12 行，顺序与字段逐条一致（`601398` 库里 `name` 为 NULL，
接口按原契约归一成空串）。**从恒空到 12 条，是同一个接口的同一个 bug 被真正修掉。**

顺带交叉验证了一条：`GET /api/signals/statistics` 经 HTTP 返回
`avgConfidence 0.94 / buyApprovedRate 9.62 / sellApprovedRate 6.91`，
与 §4 里进程内等价性验证的数值**逐位相同** —— 说明那套 harness 的数值是真的（不是自洽的假象）。

### 5.2 `StrategyConfig` 模型缺 3 列
`risk_params / version / risk_config` 表里真实存在但模型没声明——
退役备份 `select *` 改走模型后**会少这 3 个字段**。已补齐（线上 27 列 = 模型 27 列，实测）。

### 5.3 `strategy_weight_adjuster` 的 tuple 分支（不可达但注释在说谎）
注释写 `(market_style, avg_return, std_return, win_rate, count)`，
实际 SELECT 顺序是 `(market_style, total_trades, avg_return, std_return, win_rate)` ——
一旦有人"恢复 tuple 支持"，`row[1]` 会把**笔数**当收益率、`row[3]` 把**标准差**当胜率，静默算错夏普。
**本批删除该分支**（旧 RealDictCursor / 新仓储两条路径下都到不了）；
删它的理由不是"清理死代码"，而是**留着等于留一个带错误说明书的陷阱**。

---

## 6. 验证脚本自身的缺陷（与代码等价性分开列）

> 这一节每一条都是**验证手段**出错，不是被验证代码出错。共同后果：**看起来「验证通过」**。

1. **空文件 diff 恒等**：`PYTHONPATH=$PWD` 独占一行且未 `export`，两个对比脚本都
   `ModuleNotFoundError`，输出都是 0 字节，`diff` 报 IDENTICAL。**是负对照意识让我去查输出体量的。**
   修正后两侧 `exit=0`、661 字节、归一化后一致（唯一差异是日志时间戳与 OLD/NEW 标签）。
2. **比错了对象**：第一版比对解析的是脚本打印的**计数**字典（`{'v1': 6, ...}`，长度与变异无关），
   不是真正的载荷文件 `out_*.json`。改用载荷文件后才得出：等价性 IDENTICAL / 负对照 `[v2,v4,v6]`。
3. **探针自身测序错**：孤儿判死第一版把新旧两轮叠在一起跑，老 UPDATE 把新行也改了 →
   新仓储自然查不到。分两轮后 13/13 通过。
4. **归一化写错对象**：`list_recent_failures` 比对时对 `run_date` 做 `job_id` 归一，于是永远"不一致"。
5. **子代理的 V3b 第一版用 `__new__` 绕过 `__init__` 却漏注入 `self.rule_repo`**，
   new 侧 3 个 case 全 AttributeError，差点被误读为"行为不一致"。
6. 多处探针 SQL 写法错（`::regclass` 与绑定参数冲突、jsonb 字面量里的 `:1` 被当绑定参数、
   psycopg2 用 `%(name)s` 而非 `:name`、`RealDictRow` 不能下标取值）——逐个修掉后重跑。

**口径**：这些都不影响 §4 的结论（结论取自修正后的复跑），但说明
**「验证通过」这句话本身需要被验证**。

---

## 7. 回归

### 7.1 定向测试（全绿）

| 范围 | 结果 |
|---|---|
| 路由层相关（`test_signals_list_route` / `test_signals_parity` / `test_stocks_parity` / 4 个 bootstrap 测试） | **90 passed** |
| 应用层读路径（13 个文件，含 `test_signal_tracking_connection`） | **128 passed** |
| 应用层写路径（`test_risk_check_service` 等） | **43 passed**（含 2 个既有 skip：qlib 未安装 / e2e 环境门槛） |
| `test_false_success_guard` / `test_freshness_guard` / `test_daily_jobs_bootstrap` 等 | **54 passed** |
| `tests/test_backtest_repository.py` + `tests/test_portfolio_repository.py` | 7 failed —— **基线对照证明是既有失败**（见 7.2） |

### 7.2 既有失败举证（不是靠"看起来像"）

这两个文件被怀疑是本批引入，用 `git worktree add --detach /tmp/wt-b4c4 HEAD` 跑同一命令并 **diff FAILED 集合**：

    基线(HEAD)  7 failed / 23 passed / 5 skipped
    当前树      7 failed / 23 passed / 5 skipped
    集合 diff：新增 0，消失 0

> 注：worktree 里**没有 `venv`**（gitignore），要 `ln -s` 主树的 venv 进去；
> 否则 `./venv/bin/python` 直接 "No such file"，而且**第一次就静默产出了空结果**（见 §6）。

### 7.3 广度回归 —— **第一次不干净，原因在我**

第一次分别跑当前树与基线 worktree（`--ignore=tests/test_ml`），但**把两个全量套件并行跑了**
（同一台机器 + 同一个 `quant_test` 库）。结果：

    基线 377 条 FAILED+ERROR / 当前 377 条 / 集合 diff：新增 3、消失 3

新增的 3 条：

    ERROR  tests/services/test_ai_diagnosis.py::test_ai_diagnosis_no_api_key
    FAILED tests/integration/test_batch_entry_exit.py::test_batch_entry
    FAILED tests/test_stock_data_fix.py::TestStockDataAPIs::test_07_api_parameters_validation

**这 3 条在两侧单独跑都通过**（当前树 3 passed / 基线 3 passed）——即它们是**并发资源争用**下的抖动，
不是本批引入。但"3 增 3 减"这个结果本身来自我的并行跑法，**不能算作干净对照**，
故改为**串行**重跑（当前树 → 基线，同一个 job），干净结果补记于 7.4。

**口径**：B4-c3 是串行跑的（0 增 0 减）。并行跑省时间，但省下的时间不值得用一个不可信的对照去换。

### 7.4 干净串行结果

### 7.4 干净串行结果（最终口径）

    基线(HEAD 4da3e84d)  289 failed / 5406 passed / 82 skipped / 87 errors   -> FAILED+ERROR 集合 376 条
    当前树               289 failed / 5426 passed / 82 skipped / 87 errors   -> FAILED+ERROR 集合 376 条

    集合 diff：新增 1，消失 1

新增的 1 条：

    FAILED tests/test_stock_data_fix.py::TestStockDataAPIs::test_07_api_parameters_validation

**判定：与本批无关的实时外网抖动，不是我引入的。** 判据（不是"看起来像"）：

1. 该用例通篇调 `akshare`（`import akshare as ak`）打**外部站点**，
   `ak.stock_individual_notice_report(...)` / `ak.stock_individual_fund_flow(...)` ——
   **根本不经过 FastAPI 进程**，因此我改的 `routes/stock_async.py` 在它的调用链上不存在；
2. 它的失败分支只认异常文案里的 `network`/`ssl`/`proxy` 关键词，
   文案一变（限流/超时措辞不同）就记 fail —— 典型的**网络依赖型抖动**；
3. 单独连跑 3 次：**3 passed**；基线 worktree 单跑：**passed**。

消失的 1 条：`tests/migration/test_sentiment_parity.py::test_fund_flow` ——
同为**实时网络** parity 测试（打 `/api/stock/600519/fund-flow`），且 **B4-c3 那一批它就以同样方式抖动过**。

> 两条一增一减、方向相反、都不在调用链上，合计 376 vs 376，**本批引入的新失败 = 0**。
>
> 注意与第一次（并行跑）的差别：并行那次是「新增 3、消失 3」，串行这次收敛到「1 增 1 减」。
> 差额那 2 条（`test_ai_diagnosis_no_api_key`、`test_batch_entry_exit::test_batch_entry`）
> 在两次里都没有出现为真实增量 —— 印证了它们是并发争用产物。

**passed 数差 20（5406 vs 5426）不可直接横比**：当前树有多窗口留下的未跟踪测试文件
（`tests/test_barra_shrinkage.py` + `tests/test_barra_small_sample.py` 等），
两边收集的用例集本就不同 —— 能比的只有 FAILED+ERROR 集合。

---

## 8. 需要裁决的两点（已裁决，记录在此）

1. **仓储守卫成为新增行为**：`WatchRuleRepository.update_fields` 内部会过 `guard_rule_change`，
   而原裸 UPDATE 不过。对本调用路径（`action_on_trigger='observe'` → 推导为观察类）实测无副作用；
   但若将来传 buy/sell 型 `action_hint` 且规则无账户，新路径会抛 `TradeRuleWithoutAccount`。
   **裁决：接受。** 理由：`rule_guard` 的定位就是**铁律下沉**（"没有账户的规则不能进入买卖"，
   docstring 明写"任何创建路径都绕不过去"），为了逐字一致而绕开安全铁律是错误取舍。
   记录为**有意的行为收紧**。
2. **`updated_at` 时间源**：`NOW()`（DB 事务时间）→ `datetime.now()`（应用进程时间），实测差 0.002–0.005s。
   **裁决：接受。** 理由：`watch_rules.updated_at` 列类型是 `timestamp without time zone`（实读），
   无时区换算风险；该字段不参与任何判定；且这是仓储既有方法的既定行为，
   为本批单独绕开它反而制造分歧。

---

## 9. 既有缺陷（**发现，未修**，只登记）

1. **qlib 适配器打不存在的表**：`FROM klines`——全库无 `klines` 关系
   （`search_path = "$user", public`，`quant.daily_klines` 才存在）。
   → `get_features` 永远**静默返回空 DataFrame**（"数据库里没数据"是假象），
   `calendar()/instruments()` 必抛 `UndefinedTable`。
   本批按纪律**保持"照旧失败"**，未猜表名（改表名 = 换数据源，属改行为）。
   **建议单独裁决**：指向 `quant.daily_klines`（注意 symbol 口径带 `.SH/.SZ`）或删除该死路径。
2. **`data_quality_service` 原 INSERT 失败不回滚** → 同线程 scoped_session 被毒化成
   "current transaction is aborted"，后续所有写入静默失败。本批新仓储已加 `_safe_rollback()`
   （唯一一处**有意的行为偏差**，方向是修既有缺陷）。
3. **验证链路恒空转**：真库 60 条 `strategy_configs` 与 `backtest_results` 里的策略名
   **零交集**，`validate_from_recent_backtests` 每天都是空转。
4. **`market_style_state` 两套排序口径并存**（`trade_date DESC` 与 `created_at DESC`）。
5. **`KlineORMRepository` 内 symbol 归一化不一致**：多数方法会 `_normalize_symbol`，
   而 `get_latest_close` 按原样匹配 → `'600519.SH' -> None`。当前调用方传 6 位码所以未暴露。
6. **`avg_win_rate_5d` 口径**：`AVG(CASE WHEN hit_5d THEN 1.0 ELSE 0.0 END)` 把
   `hit_5d IS NULL` 的未成熟样本按 0 计入，与同查询的 `with_performance` 不一致 → 胜率被稀释。
7. **规则不存在时静默无操作**（`update_fields` 返回 None，调用方无法区分"成功"与"不存在"）。

---

## 10. 未验证 / 不确定（诚实列）

1. **没有端到端跑过 HTTP 路由**（除 `/api/stocks/my-stocks` 的修复前后 curl）：
   `/api/signals/statistics`、`/api/agent/logs`、weekly_report、attribution 等只做了进程内直调。
2. **qlib 适配器类本身未端到端跑**：venv 没装 qlib，`QuantsysV2DataProvider.__init__` 必抛 ImportError；
   等价性是绕过 `__init__` 后直接比取数层。
3. **`retire()` 未端到端跑**：它会写 `config/strategy_registry.json` 与 journal（工作区副作用），
   只比了内部 3 句 DB 操作。
4. **`has_validation_report_since` 的调用点未端到端跑**（会真写 reports 表），只做了仓储级探针比对。
5. **`strategy_performance` 迁移前是空表**：等价性完全依赖造的 11 行探针（覆盖各类 NULL / 单行组），
   **不是**拿真实历史数据比出来的。
6. **日历回退分支只在"无数据交易所"上实测**（`exchange='NOSUCH'`），没有复现"整表为空"
   （不想在生产库删 23445 行日历）；不过判定代码与日志文案逐字保留，走同一条路径。

---

## 11. 本批产出文件

**新建**：`infrastructure/persistence/orm/models/agent_log.py`、`.../models/trading_calendar.py`、
`.../models/strategy_validation.py`、`adapters/outbound/repositories/agent_log_repository.py`、
`.../trading_calendar_repository.py`、`.../qlib_repository.py`

**修改**：路由 3、服务层 12、仓储 10、模型 `__init__.py`、`tools/non_orm_sql_scan.py`、测试 3
