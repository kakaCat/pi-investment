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

## 6. 批次进度总表（截至 2026-09-14 B4-c1）

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
| B4-c1 | 本批 | portfolio_repository（trades/holdings 半区 9 处）+ 2 个静默缺陷 | 15→6 |

批次日志：`req-24e15d-b1-jobs-layer.md`、`-b2a-`、`-b2b-`、`-b3a-`、`-b3a2-`、
`-b3b-`、`-b4a-`、`-b4b-`、`-b4c-portfolio-repo.md`。

## 6.5 B4-c2：legacy 订单栈删除（`9bb04e65`，经用户裁定 A 方案）

详见 `req-24e15d-b4c2-delete-legacy-order-stack.md`。要点：

- 删 10 个 orders 方法 + `db` 裸连接属性 ⇒ **portfolio_repository.py 15 → 0，100% ORM**；
- 删 `order_service.py`(1175) + `new_order_service.py`(102) + `POST /api/signals/execute` + 8 个 legacy 测试文件；
- **修好一条静默失效的调度链**：`_batch_create_orders` 里 legacy `create_order` 必抛异常、
  被 except 吞掉 → `trade_signals` 恒空 → **PaperTradingEngine 自 2026-08-25 起一单未执行**。

## 7. 当前闸门状态（B4-c2 后）

```
P0 fstring_value_interp  本轮范围 0    ✅
P0 raw_connect           本轮范围 0    ✅
P1 cursor_execute        本轮范围 51（起点 124）
P1 core_text_sql         本轮范围 25（起点 35）
P2 session_execute_var   本轮范围 53（审计桶，人工复核；本仓多为 stmt=select(...)）
P2 fstring_sql           本轮范围 6（起点 11）
P2 read_sql              本轮范围 5
→ --gate 退出码 0
```

## 8. 剩余工作（按优先级）

| 文件 | 站点 | 备注 |
|---|---|---|
| `portfolio_repository.py` | 6 | **⛔ 阻塞**：`quant.orders` 已归档（2026-08-25），见 B4-c 日志"遗留决策" |
| `risk_repository.py` | 10 | cursor_execute |
| `kline_repository.py` | 9 | core_text_sql=7 |
| `chip_repository.py` | 7 | core_text_sql=7 |
| `strategy_performance_repository.py` | 7 | cursor_execute |
| `signal_tracking_repository.py` | 6 | cursor_execute |
| `routes/signals_async.py` | 6 | cursor_execute=5 |
| `application/services/order_service.py` | 5 | **依赖上面那条阻塞决策** |

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
