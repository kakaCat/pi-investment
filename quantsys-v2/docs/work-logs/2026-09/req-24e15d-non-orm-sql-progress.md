# REQ-24e15d 进度：非 ORM SQL 收敛 t1/t2 完成、t3 进行中（2026-09-13，w-32314d00）

## 1. 基线与工具

新增可复跑扫描器 `tools/non_orm_sql_scan.py`（`--gate` 可接发版体检）。
**指标本身修了两轮**，否则数字不可信：

1. 第一版把注释里的反例写法也算进去 → 修完代码计数反而 +1；
2. 第二版按三引号粗暴跳过 → 把 `cursor.execute("""...""")` 的多行 SQL 字面量一起跳过，
   `cursor_execute` 从 154 漏计到 87（漏 43%）；
3. 最终改为 **AST 精确识别 docstring**（只认模块/类/函数体的首个字符串常量），SQL 字面量照常计入。

## 2. t1（P0 值位置注入）：完成

- `infrastructure/adapters/industry_data_adapter.py`：原 f-string 把 `factor_name` 与 `symbol_list` 直接拼进 SQL
  （列名 + 取值双重注入面）→ 列名过白名单 + `symbol = ANY(%s)` 绑定参数；
- `infrastructure/jobs/financial_data_update_job.py`：SET 子句列名加白名单守卫（未知列显式报错）；
- 新增 `tests/test_non_orm_sql_t1_parameterization.py`（10 passed）；活体取数验证通过。

## 3. t2（P0 裸连接）：完成

- 新增 `PooledConnection`（`infrastructure/persistence/database/engine.py`）：把池化连接包装成 psycopg2 风格
  `cursor()/commit()/rollback()/close()/closed`，调用点**零改动**即可从"裸连接长期持有"切到"借完即还"，
  `close()` 前对未提交事务显式 rollback（防 idle-in-transaction 残影）；
- 转换：`attribution_service` / `weekly_report_service` / `signal_test_log` / `signal_tracking_repository`；
- 期间发现两处**真 bug**：
  ① `attribution_service.analyze_rule_performance` 在真实数据上崩（`float += decimal.Decimal`）——已修；
  ② `utils/symbol_classifier.is_index_symbol` 走 ORM 仓储查 stocks，在 ThreadPoolExecutor 线程上开
     thread-local session 且不关闭 → 22:08 那条 `session_leak_detected`——改用池化游标，语义不变（已验）。

## 4. t3（分层下沉）：进行中

目标文件 `application/services/smart_scheduler.py`（起点 7 处裸 SQL → 现 1 处）：

- 前置核查发现**真 bug**：`AutomationRun` 模型把列映射成不存在的 `run_metadata`（真实库列名是 `metadata`），
  整个 `AutomationRunRepository` 在真实库上不可用 → 已修 + 新增契约测试
  `tests/test_automation_run_mapping_contract.py`（2 passed）；
- 新增 `find_running_run_id_by_job_id`（`metadata->>'job_id'` 查最新 running）；
- 已上收：`_update_run_status`（SELECT+UPDATE）、`_execute_task` 的 INSERT、成功/失败路径两条 UPDATE runs
  与 `automation_tasks.last_run_at`；
- 活体验证：`create_run` 探针 insert→读回→删除（无残留）、`find_running_run_id_by_job_id` 可查到刚写行；
  **注意**：第一次探针失败是"我的测试数据错"（`task_id=-1` 违反外键），不是代码错——两者结论相反，先查数据再下结论。
- **`smart_scheduler.py` 已清零（7 → 0）**：`trigger_task` 的 INSERT 也已上收；并删掉上收后残留的
  `conn = get_db_connection()`（无人使用却仍开连接）。该文件仅剩一个未使用的 import 待顺手清理。
- 下一步：`signals_async` → `session_service`（需新建 agent_session 仓储，13 处）。

## 5. t4（jobs 层）：进行中 —— 批次 B1 已完成

> 详见 `docs/work-logs/2026-09/req-24e15d-b1-jobs-layer.md`

**先修了扫描器自己的盲区**：`cursor_execute` 原口径是 `\bcursor\.execute\(`，**只认变量名恰好叫 cursor**
的调用——实测漏计 `cur.execute(...)`（kline_update_job 的 3 个自检）与 `conn.execute(...)` 等同义写法，
基线**系统性偏低约 40%**。改为"任意 `.execute` 接收者 − 非 DB 对象 − SQLAlchemy 构造器入参"，
并新增审计桶 `session_execute_var`（`session.execute(<标识符>)` 正则无法判定，本仓 43/48 是 `stmt=select(...)`）。
**口径修正后基线：cursor_execute 111 → 124**（不是改坏了，是原来没看见）。

B1 完成（6 个文件 15 处 → 0，另删死代码 3 处）：

| 文件 | 前 | 后 |
|---|---|---|
| verification_job.py | 2 | 0 |
| weekly_report_job.py | 2 | 0 |
| risk_check_job.py | 3 | 0 |
| strategy_risk_check_job.py | 2 | 0 |
| kline_update_job.py | 6 | 0 |
| kline_priority_sync.py（死代码） | 3 | 删除 |

**期间揪出两个真 bug**（详见 B1 日志）：
① **基准收益长期恒为 0.0**——三处都在读已分表的 `quant.daily_klines` 取指数价（399 族 0 行），
  指数其实在 `quant.index_daily`（`399006.SZ`，268 行）⇒ 超额收益被系统性高估；已改走仓储指数口径。
② **同步宇宙混入 4 个指数占位行**（stocks 里 `list_date IS NULL` 的 000300/399001/399006/399300）
  ⇒ 每日白请求 4 个指数、写入口刷告警，且是约束违规的历史路径；已在选股出口用
  `is_index_symbol`（与写入口同语义）剔除。
另修 `batch_insert_daily_klines` 的 upsert 会把既有 `source` 抹成 NULL（改 coalesce）。

新增：`adapters/outbound/repositories/kline_sync_repository.py`（选股 + 写入 + 3 个自检）、
ORM 模型 `IndexDaily`、仓储指数口径方法（`get_index_return` 等）。

## 6. 批次进度总表（截至 2026-09-14 B4-c3）

| 批次 | 提交 | 内容 | 站点 |
|---|---|---|---|
| 修 bug | `8d0efff8` | 6 类缺陷（TA-Lib 空数据崩溃 / 订单状态机缺 (PENDING,FILLED) / 等） | — |
| B2-a | `2ba1e85e` | jobs 层 + kline 质量 | 15 |
| B2-b | `e79a1c67` | routes + datasources | — |
| B3-a | `3345143a` | session 服务 + agent_session 两表落 ORM | — |
| B3-a2 | `b3e476ae` | daily_klines 查询收敛到仓储 | 4 |
| B3-b | `8e51a916` | 信号测试日志落 ORM + 移除私有连接访问器 | 11 |
| B4-a | `004f4a67` | stock_pool_repository 真正落 ORM | 10 |
| B4-b | `87850eb0` | 熔断状态服务落 ORM + 修 JSONB NULL 语义陷阱 | 2 |
| B4-c1 | `54830404` | portfolio_repository（trades/holdings 半区 9 处）+ 2 个静默缺陷 | 15→6 |
| B4-c2 | `9bb04e65` | 删 legacy 订单栈（A 方案）+ 修好静默失效的信号执行链 | 6→0 |
| B4-c3 | `3ec509f8` | risk + kline + chip + strategy_performance 四仓储落 ORM | 33→0 |
| 度量 | `d698dc89` | **扫描器口径修正**：`core_text_sql` 漏计 `conn.execute(text(...))`（11→39，+32 全为既有漏计） | — |
| B4-c4 | `090efa02` | **应用层（读 6 + 写 6）+ 路由层 3 文件**全部收口到仓储 | 26→0 |
| B4-c5 | `d87321ce`+`df57a042` | event_repository(12) + 仓储层 13 + 基础设施/作业/服务边缘 7 | 32→0 |

批次日志：`req-24e15d-b1-jobs-layer.md`、`-b2a-`、`-b2b-`、`-b3a-`、`-b3a2-`、
`-b3b-`、`-b4a-`、`-b4b-`、`-b4c-portfolio-repo.md`、`-b4c2-delete-legacy-order-stack.md`、
`-b4c3-repositories.md`、`-b4c4-app-routing-layers.md`。

## 6.6 B4-c4：应用层 + 路由层收口（本批）

详见 `req-24e15d-b4c4-app-routing-layers.md`。要点：

- **路由层 3 文件**：`signals_async.py`(6) / `stock_async.py`(2) / `daily_jobs_bootstrap.py`(1 计数 + **11 处扫描器漏计**) → 0；
- **应用层 12 文件**：读路径 6（notifier / strategy_rotation_engine / opportunity_to_watch_rule_service /
  weekly_report_service / attribution_service / data_pipeline_service）+ 写路径 6（risk_check_service /
  strategy_weight_adjuster / strategy_validation_service / data_quality_service / strategy_lifecycle_service /
  qlib_data_adapter）；
- **新建 3 个 ORM 模型**（`agent_log` / `trading_calendar` / `strategy_validation`）+ 3 个仓储；
- **修好一个长期静默失效的接口**：`GET /api/stocks/my-stocks` 恒返回空持仓（`ds.portfolio` 已为 None，
  `ds.portfolio.db` 必抛 AttributeError 被 `except Exception: pass` 吞掉，而 `quant.positions` 有 12 行 open）；
- **等价性全部在真实库上比结果**，且有**负对照**证明比对脚本不是恒真（变异 3 处 → 恰好检出 3 段）。

## 6.5 B4-c2：legacy 订单栈删除（`9bb04e65`，经用户裁定 A 方案）

详见 `req-24e15d-b4c2-delete-legacy-order-stack.md`。要点：

- 删 10 个 orders 方法 + `db` 裸连接属性 ⇒ **portfolio_repository.py 15 → 0，100% ORM**；
- 删 `order_service.py`(1175) + `new_order_service.py`(102) + `POST /api/signals/execute` + 8 个 legacy 测试文件；
- **修好一条静默失效的调度链**：`_batch_create_orders` 里 legacy `create_order` 必抛异常、
  被 except 吞掉 → `trade_signals` 恒空 → **PaperTradingEngine 自 2026-08-25 起一单未执行**。

## 6.7 B4-c5：仓储层 + 基础设施层（本批）

详见 `req-24e15d-b4c5-repo-infra.md`。要点：

- **32 处归零**：event_repository(12，含修 EventCalendar 模型缺 4 列) + 仓储层 13 + 基础设施/作业/服务边缘 7；
- **61 里有 9 处按设计就是 SQL**（通用异步执行器原语 / PG 函数 / `SELECT 1` 探针 / 扫描器误报），
  **本批没动**，交用户裁决"行级豁免标注"还是"常驻计数"——不单方面改验收口径；
- **一个"拒绝清零"的判断**：`public.apscheduler_jobs` 是 APScheduler 自己的表，不建 ORM 模型
  （会造第二个 owner + 让 `create_all` 去 CREATE 三方表），改用 Core `table()/column()+select()`；
- **抓到 2 个自引入偏差**：JSONB 置 None 写成字面量 `null`（应 SQL NULL）、
  `get_industry_totals(None)` 返回 int 0（应 0.0）；
- 等价性 IDENTICAL + 负对照 6 处变异全检出；失败集合与基线 **逐条 diff：新增 0 / 消失 0**。

## 7. 当前闸门状态（B4-c5 后）

```
P0 fstring_value_interp  本轮范围 0     OK
P0 raw_connect           本轮范围 0     OK
P1 cursor_execute        本轮范围 11（起点 124；B4-c4 后 13）
P1 core_text_sql         **两个尺子必须都读**（口径在 B4-c4 中途修正过）：
                           旧尺子（只认 session. 接收者）本轮范围  7
                           新尺子（任意接收者，= d698dc89 起）   本轮范围 10
P2 session_execute_var   本轮范围 72（审计桶，人工复核）
P2 fstring_sql           本轮范围 2
P2 read_sql              本轮范围 5
psql_subprocess          本轮范围 1（test_cron_parsing.py，见 §8）
unparseable（语法坏文件） 本轮范围 []
-> --gate 退出码 0
```

**剩余 29 站点里，9 处经逐条形态分析判定为"按设计就是 SQL"**（见 `-b4c5-` 日志 §0），
不再视为待迁工作；其余 20 处需要**裁决或设计**（见 §8）。

## 8. 剩余工作（按优先级）

**B4-c3 已完成**：`risk_repository`(10) / `kline_repository`(9) / `chip_repository`(7) /
`strategy_performance_repository`(7) —— 详见 `req-24e15d-b4c3-repositories.md`。
`portfolio_repository`(6) 与 `application/services/order_service.py`(5) 已随 B4-c2
（删 legacy 订单栈，用户裁定 A 方案）**整段删除**，不再是剩余工作。

**B4-c4 已完成**（本批）：应用层 12 文件 + 路由层 3 文件全部收口 ——
详见 `req-24e15d-b4c4-app-routing-layers.md`。**应用层与路由层已无裸 SQL**。

**B4-c5 已完成**（本批）：32 处归零 —— 详见 `req-24e15d-b4c5-repo-infra.md`。

**B4-c6 候选（29 站点，全部需要裁决或设计，不是机械活）**：

| 项 | 站点 | 需要什么 |
|---|---|---|
| `signal_tracking_repository.py` | 8 | 它持有**刻意的**裸连接（自愈 + 借还），且 `tests/test_signal_tracking_connection.py` 把该机制固化。改 ORM = 拆机制，须连同测试重新设计 |
| `async_base_repository.py` x5 + `dependency_check.py` x2 + `ml_model_repository.py` x1 + `portfolio_repository.py` x1 | 9 | **按设计就是 SQL**（原语 / PG 函数 / `SELECT 1` 探针 / 扫描器误报）。需裁决：加**必须写理由**的行级豁免标注，还是让它常驻计数 |
| `qlib_repository.py` | 4 | 源表 `klines` **全库不存在** → `get_features` 永远静默返回空 DataFrame。改表名 = 换数据源，需先裁决 |
| `core_plan_service` / `data_hygiene_service` / `strategy_evaluation_service` | 6 | 通用 SQL 助手，**27 个调用点**。需先设计**类型化查询端口** |
| `symbol_classifier.py` | 1 | 注释写明**故意**不用 ORM：曾致 `idle in transaction` ~337s 被 DB 强杀 |
| `test_cron_parsing.py` | 1 | 仓库根目录的**一次性运维脚本**（非测试）。建议改造成 `tests/` 下的正式 pytest |

**范围外 78**（`scripts/` / `tools/` / `live_trading/`）另行裁决。

另有两项**独立既有缺陷**建议单列（均为 HEAD 已复现，非本线引入）：
1. `signals.action_type` 模型声明 NOT NULL 无默认值 ⇒ 建表列亦无默认值 ⇒
   `NotNullViolation`（`test_heatmap_service` 10 errors + `test_heatmap_repository_events` 7 errors）。
2. **测试库 `quant_test` schema 落后于 ORM 模型**：`simulation_order` 缺
   `decision_price/decision_at/price_source/fill_price/slippage_bps` 五列 ⇒
   `test_multi_account_domain` 6 例 `UndefinedColumn`。

## 9. 运行态

服务重启后：ERROR 0 / session_leak_detected 0 / idle in transaction 0。

## 10. 口径提醒（重要，跨会话）

- 扫描器必须用 `./venv/bin/python tools/non_orm_sql_scan.py`（系统 python3.9 会在 f-string 语法上直接失败）。
- `cursor_execute` 基线**已修正过**：111（旧口径，只认变量名叫 cursor 的）→ **124**。
  **不要拿 111 当起点**，否则会算出"凭空多出来 13 处"。
- 判定"是否引入新失败"必须用 `git worktree add /tmp/wt-head HEAD` 跑同一组用例并
  **diff 失败集合**，不能只比数量、更不能看"像不像既有问题"。
- **`core_text_sql` 口径修正过两次，跨会话引用数字前先看这个文件顶部的口径说明**：
  1. `cursor_execute`：111 → 124（只认变量名叫 `cursor` → 认任意 DB-API 接收者，B1 前置）
  2. `core_text_sql`：只认 `session.` 接收者 → 认任意接收者（B4-c4 前置，`d698dc89`）。
     修正后本轮范围 11 → 39，**+32 全是既有漏计**。引用历史数字时务必注明用的是哪个尺子，
     否则会把"度量变化"算成"活干了"或反过来。
- **扫描器对语法坏文件的行为变了**（B4-c4）：原先 `SyntaxError` 时 docstring 集合返回空 ⇒
  整个文件的 docstring 被当代码扫 ⇒ 指标**向上虚高**。现在这类文件计入 `unparseable` 并**不计入任何指标**，
  报告会显式告警。**"某文件 0 命中"与"某文件没量到"是两件事**，看报告时要分清。
- **等价性验证要带负对照**：只跑"老==新"无法排除"比对脚本恒真"。做法见 B4-c4 日志 §4.1
  （把老实现定向变异 3 处，差异段必须恰好等于被变异段）。B4-c4 期间这道防线拦下 2 次假"通过"。
  **worktree 里没有 `venv`（gitignore）**，要 `ln -s` 主树 venv 进去，否则 `./venv/bin/python` 直接 No such file。
---

## 11. 独立复核（2026-09-14 13:50，w-32314d00）

用户问"没有走 ORM 的修复现在进行到哪里"，故**不引用日志、直接重跑扫描器复核**（可复跑命令同 §1）：

```
./venv/bin/python tools/non_orm_sql_scan.py --json   # 明细
./venv/bin/python tools/non_orm_sql_scan.py --gate   # 退出码 0
```

**本轮范围（非 scripts/tools/live_trading）= 101 处**，其中：

| 桶 | 处数 | 性质 |
|---|---|---|
| `session_execute_var` | **72** | **审计桶，未判定**（`session.execute(<变量>)` 静态分不清是 `select()` 还是 `text()`）——不是"确认未迁"，需人工复核 |
| `cursor_execute` | 11 | 确认未迁 |
| `core_text_sql` | 10 | 确认未迁 |
| `read_sql` | 5 | 确认未迁 |
| `fstring_sql` | 2 | 标识符插值，**非验收值** |
| `psql_subprocess` | 1 | 一次性运维脚本 |

**去掉审计桶后剩 29 处 / 11 文件**，与 §8 一致（复核确认）：

```
 8  adapters/outbound/repositories/signal_tracking_repository.py   cursor_execute
 5  infrastructure/persistence/database/async_base_repository.py   core_text_sql
 4  adapters/outbound/repositories/qlib_repository.py              fstring_sql 1 + read_sql 3
 2  application/services/core_plan_service.py                      read_sql 1 + cursor_execute 1
 2  application/services/data_hygiene_service.py                   core_text_sql 2
 2  application/services/strategy_evaluation_service.py            core_text_sql 1 + read_sql 1
 2  infrastructure/diagnostics/dependency_check.py                 fstring_sql 1 + core_text_sql 1
 1  adapters/outbound/repositories/ml_model_repository.py          cursor_execute
 1  adapters/outbound/repositories/portfolio_repository.py         core_text_sql
 1  test_cron_parsing.py                                           psql_subprocess
 1  utils/symbol_classifier.py                                     cursor_execute
```

**两处分层结论（本轮实测，用于推进看板任务状态）**：

- `adapters/inbound/`（路由层）本轮范围命中 **0** —— t3 的路由半区达成；
- `infrastructure/jobs` 与 `infrastructure/adapters` 本轮范围命中 **0** —— t4 验收项达成，任务已 done。

**口径更正**：§8 末写的"范围外 78"与实测不符 —— 现在实测 `out_of_scope` = **124**
（`fstring_value_interp` 1 / `raw_connect` 14 / `cursor_execute` 45 / `core_text_sql` 50 / `fstring_sql` 14）。
已核扫描器未误扫 `.claude/worktrees/`（该目录被 .gitignore 命中，`files` 明细里 0 条可疑路径），
故 124 是真实计数，以本节为准。

**看板同步**：`t-d4bd5b`（作业/适配器层）→ done；`t-35681e`（仓储内）→ in_progress。
`t-cd19d2`（应用/路由层）**保持 in_progress**：路由半区已 0，但应用层仍有 6 处
（core_plan 2 / data_hygiene 2 / strategy_evaluation 2，即 §8 的"通用 SQL 助手、27 个调用点"），
验收项"应用+路由层 cursor_execute 清零"**未满足**，卡在"类型化查询端口"设计，不标记完成。

