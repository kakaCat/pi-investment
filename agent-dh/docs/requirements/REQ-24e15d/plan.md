# REQ-24e15d 实施计划 · quantsys-v2 裸 SQL 全量迁 ORM

- 需求：REQ-24e15d（refactor）
- 窗口：w-32314d00（角色 investor）
- 计划日期：2026-09-13（v2：t1 完成、口径修正）

## 1. 基线（可复跑：`tools/non_orm_sql_scan.py`）

**粗指标与风险指标必须分开** —— 第一版计划把"f-string SQL 计数"当验收值，实测发现它会**奖励错误做法**：
列名/表名无法用绑定参数（只能白名单），把 `f"SELECT {column} FROM ..."` 算成缺陷会导致为了凑指标去写更差的代码。
故 v2 拆成两个指标：

```
指标（本轮范围 = 非 scripts|tools|live_trading）:
  [P0] fstring_value_interp   合计   2   本轮范围   0   ← 引号内插值=值位置注入签名，已清零
  [P0] raw_connect            合计  20   本轮范围   6   ← 裸连接，t2 目标
  [P1] cursor_execute         合计 160   本轮范围 127
  [P1] core_text_sql          合计  40   本轮范围  35
  [P2] fstring_sql（粗）       合计  28   本轮范围  11   ← 标识符插值属正当写法，**不作为验收值**
  [P2] read_sql               合计   5   本轮范围   5
  [P2] psql_subprocess        合计   1   本轮范围   1
```

判定口径：`fstring_value_interp` = SQL 行里出现 `'{...}'` / `"{...}"`（取值被拼进引号内）。
自检（证明它抓的是真注入面）：旧写法 `WHERE symbol IN ('{symbol_list}')` 命中 1；
新写法 `WHERE symbol = ANY(%s)` + 白名单列名 命中 0。

为什么值得做（同源事故实证，非理论风险）：裸连接绕过 session 管理（`session_leak_detected` 50 次、
`connection already closed` 3 起）；读操作开事务不释放 → 连接挂 idle-in-transaction 被 DB 强杀。

## 2. 范围界定（先说清不改什么）

| 类别 | 是否纳入 | 原因 |
|------|----------|------|
| `infrastructure/persistence/migrations/` | **不纳入** | DDL 与数据迁移本就该用原生 SQL |
| `tests/`、`venv/` | 不纳入 | 非生产代码 |
| `scripts/`、`tools/`、`live_trading/` | **不在本轮**（单独记账） | 诊断/运维脚本，收益低风险高 |
| 应用/路由/作业/适配器层的 SQL | **纳入** | 分层违规 |
| 仓储内 cursor/Core SQL | **纳入** | 数据层实现统一 |

## 3. 目标口径

1. **分层归位**：SQL 只允许出现在 `adapters/outbound/repositories/`。
2. **标识符白名单 + 取值绑定参数**：列名/表名进 SQL 前必须过白名单；取值一律 `%s`/`:name`/`= ANY(%s)`。
3. **连接卫生**：一律经 `get_session()`/仓储（受 `session_guard` 监管），禁止 `psycopg2.connect` 直连。
4. **验收**：`non_orm_sql_scan.py --gate` 退出码 0（P0 两项在本轮范围内清零）。

## 4. 分批

- **t1（P0 值位置注入）**：已完成 —— `infrastructure/adapters/industry_data_adapter.py` 两处（列名白名单 +
  `symbol = ANY(%s)`）+ `infrastructure/jobs/financial_data_update_job.py` 的 SET 列白名单守卫。
  本轮范围 P0 `fstring_value_interp` 2→**0**。
- **t2（P0 连接卫生）**：本轮范围 6 处裸连接 → 收口到 `get_session()`/仓储。
- **t3（应用/路由层）**：`cursor_execute` 127 中的应用层与路由层部分下沉到仓储。
- **t4（作业/适配器层）**：`infrastructure/jobs` + `infrastructure/adapters` 收口。
- **t5（仓储内）**：`adapters/outbound` 的 cursor/Core/read_sql 逐文件迁移。
- **t6（验收）**：`--gate` + 全量回归 + 接入发版体检 + 工作日志。

## 5. 风险与协调

- 另一窗口（w-a9ec14d7）在做同主题 B 系列收口（B7 = core_plan 去 subprocess psql）。执行前对齐文件边界，
  避免两窗口同改一个热点仓储文件；扫描器可作双方公共基线。
- 热点仓储（kline/portfolio/risk/stock_pool）逐文件改、逐文件回归，不一次性大改。

## 6. 任务表（落库即此表）

| key | 标题 | phase | side | depends_on | 验收 |
|-----|------|-------|------|-----------|------|
| t1 | P0：值位置注入清零（列名白名单 + 取值绑定） | implement | backend | — | 本轮范围 `fstring_value_interp`=0；行业适配器活体取数正确；新增回归测试通过 |
| t2 | P0：裸连接收口到 session/仓储 | implement | backend | t1 | 本轮范围 `raw_connect` 6→0；无新增 session_leak_detected |
| t3 | 应用/路由层 SQL 下沉到仓储 | implement | backend | t2 | 应用+路由层 cursor_execute 清零；接口行为不变 |
| t4 | 作业/适配器层 SQL 收口 | implement | backend | t2 | `infrastructure/jobs`+`adapters` 的 cursor_execute 清零 |
| t5 | 仓储内 cursor/Core 统一到 ORM | implement | backend | t4 | `adapters/outbound` 的 cursor_execute/core_text_sql/read_sql 清零；逐文件回归 |
| t6 | 验收：gate + 全量回归 + 工作日志 | test | backend | t5 | `--gate` 退出码 0；pytest 无新增失败；gate 接入发版体检 |

## 7. 附录 · t3 执行清单（2026-09-13 现场盘查，供逐文件开工）

按 cursor_execute 数量排序的本轮范围内目标，并标注**可复用的现有仓储**（决定每个文件的写法）：

| 文件 | 处数 | 触及的表 | 去向 |
|------|------|----------|------|
| `adapters/outbound/repositories/portfolio_repository.py` | 15 | 已在仓储层 | t5：仓储内统一到 ORM/Core |
| `application/services/session_service.py` | 13 | `agent_sessions` / `agent_session_events` | t3：**需新建** agent_session 仓储（现无） |
| `adapters/outbound/repositories/stock_pool_repository.py` | 10 | 已在仓储层 | t5 |
| `adapters/outbound/repositories/risk_repository.py` | 10 | 已在仓储层 | t5 |
| `application/services/signal_test_log.py` | 9 | `signal_test_log` | t3：下沉（可并到 signal 相关仓储） |
| `application/services/smart_scheduler.py` | 7 | `automation_runs` / `automation_tasks` | t3：**复用现有 `automation_repository`** |
| `adapters/outbound/repositories/strategy_performance_repository.py` | 7 | 已在仓储层 | t5 |
| `adapters/outbound/repositories/signal_tracking_repository.py` | 6 | 已在仓储层 | t5 |
| `adapters/inbound/fastapi_app/routes/signals_async.py` | 5 | `signals` / `agent_logs` | t3：`signals` 走现有 `signal_repository`；`agent_logs` 需薄仓储 |
| `infrastructure/jobs/{weekly_report,verification}_job.py` | 各 4 | — | t4 |

**开工顺序建议**：`smart_scheduler`（复用既有仓储，改动最小）→ `signals_async`（部分复用）→ `session_service`（需新建仓储，13 处一次到位）→ 其余 t4 → t5 仓储内统一。

