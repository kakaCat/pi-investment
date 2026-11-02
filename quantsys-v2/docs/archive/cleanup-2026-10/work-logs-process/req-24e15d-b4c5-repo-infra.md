# REQ-24e15d B4-c5：仓储层 + 基础设施层 Core SQL 收口

- **需求**：REQ-24e15d「quantsys-v2 裸 SQL 全量迁 ORM」
- **窗口**：w-32314d00　**日期**：2026-09-14　**提交**：`d87321ce`（event_repository）+ `df57a042`（其余 20 处）
- **本轮范围**：22 文件 / 61 站点 → **11 文件 / 29 站点**（归零 32 处）

---

## 0. 先说清楚：61 里有 9 处**按设计就是 SQL**，不该"迁"

逐个看形态后，有 9 个站点**转换是错的**（会让代码变差，而不是变好）：

| 站点 | 为什么不该迁 |
|---|---|
| `async_base_repository.py` ×5 | 通用异步执行器**原语**（`fetch(query)/execute(query)`）。它本身就是"放 SQL 的地方"；转换等于删掉这个类。全仓调用方只有 `async_engine` / `__init__` |
| `portfolio_repository.py:818` ×1 | PG **函数**调用，无法 ORM 表达（B4-c4 已文档化） |
| `ml_model_repository.py:132` ×1 | `SELECT 1` 健康探针，不是数据访问 |
| `dependency_check.py:68` ×1 | `SELECT 1` 连通性探测，诊断用途 |
| `dependency_check.py:75` ×1 | **扫描器误报**：`f'SELECT 1 ok ({elapsed_ms}ms, …)'` 是一条**日志文案**里含 "SELECT 1"，不是 SQL 执行 |

**本批没有动它们**，并把"怎么处置"提交用户裁决 —— **不单方面改验收口径**。

---

## 1. event_repository（12 处 → 0，`d87321ce`）

### 1.1 它原来为什么用 Core SQL，以及为什么现在可以改
模块 docstring 记的理由是**导入顺序炸弹**：同一 Base 上若声明**两个**映射 `quant.event_calendar`
的类，谁先被导入谁定义 Table，后导入的会抛 `Table ... is already defined`。

该理由**只对"再声明一个同表映射类"成立**。核过：全仓 `class EventCalendar` 只有一处
（`event_calendar_repository.py:16`），且此前**无人 import**（只有文档提到它）。
改为复用它 → 只有一个类 → 炸弹前提消失。

### 1.2 顺带修掉的真缺陷：模型缺 4 列
`EventCalendar` 原先 **14 列**，线上表 **18 列** ——
`scope / symbols / source_url / evidence_hash` **只在库里、没进模型**。
任何走该模型的全列读写都会静默丢掉这 4 列（与 B4-c4 的 `StrategyConfig` 缺 3 列同一类陷阱）。
已补齐并逐列核对：**18 = 18**。

### 1.3 等价性（真实 71,916 行表，28 项检查全过）
- 22 项只读：`list` / `for_symbol` / `upcoming` / `exists_by_hash` / `is_in_default_universe` /
  `research_universe` / `default_universe` / `stats`，含不存在标的、空串、带后缀代码等边界
- 6 项写路径：同输入写两组标记行，比**写入后的行** —— insert/update/skip 计数一致、
  落库逐字段一致、**`status` 未被覆盖**（受控更新契约）
- 探针清净：`probe_rows_left = 0`

### 1.4 测试接缝变更（改注入点，断言一条没减）
契约测试原用 `FakeEngine` 按 **SQL 文本前缀**分派（`startswith('SELECT id, status')` 等），
ORM 不再产出该文本 → 打桩点失效。接缝由「注入 Engine」改为「注入 Session」。
原 14 条契约逐条保留，另补 1 条（`default=str` 兜底）+ 宏观窗口边界；
SQL 文本类断言改为在**编译后的语句/绑定参数**上断言（`@>` 与 DESC、`scope=macro` 走 params）。

---

## 2. 其余 20 处（`df57a042`）

### 2.1 仓储层 13 处
| 文件 | 站点 | 去向 |
|---|---|---|
| `watch_state_repository.py` | 6 | 新建 `models/watch_state.py`（WatchDigestState / WatchIntervention）：列投影 + `pg_insert(...).on_conflict_do_update(index_elements=[id])` + ORM 聚合 |
| 同上 :84 | 1 | `UPDATE quant.watch_rules` **不是本表** → 移到 `WatchRuleRepository.apply_intervention_ledger`（新增），与介入行**同事务**提交 |
| `competition_repository.py` | 3 | 统一用 `models/stock.py` 的 Stock；**删掉文件内重复定义的极简 Stock 类**（同表重复定义 = Table already defined 隐患） |
| `strategy_repository.py` | 3 | `sa_update().values(**白名单)` / `sa_delete()` / `StrategyValidationReport` add+flush；JSONB 保持原 `CAST(:x AS jsonb)` 形态；白名单未放宽也未收紧 |
| `watch_rule_repository.py` | 1 | `self.session` + `func.count().filter(...)`，不再自开连接 |

### 2.2 基础设施 / 作业 / 服务边缘 7 处
| 文件 | 去向 |
|---|---|
| `scheduler_tasks.py` ×2 | `get_latest_trade_date_strict()`（**新 strict 变体**：现成方法吞异常返回 None，会把"读失败"静默降级成 "stale"）+ `count_bars_by_symbol()`（LEFT JOIN 与 ON 子句语义逐字保留） |
| `market_state_provider.py` | `get_latest_index_quotes()`；**刻意不做后缀归一化**，保持 `symbol = :s` 命中集合 |
| `scheduler_repository.py` | **判断：不建 ORM 模型**，用 Core `table()/column()+select()` —— 见 §3 |
| `strategy_evolution_run_repository.py` | ORM 窗口函数 + subquery + `aliased()`；无帧子句（row_number 不吃帧） |
| `v13_use_case.py` | 新建 `audit_log_repository.py`；查证 `audit_log` **任何 schema 下都不存在**且仓内无 DDL |
| `fund_flow_update_job.py` | `get_closes_on_date()`；expanding IN 保留 `ANY(:syms)` 语义 |

---

## 3. 一个"拒绝清零"的判断（值得记下来）

`scheduler_repository.py:522` 查的是 `public.apscheduler_jobs` —— **APScheduler 自己的表**。
**选择不建 ORM 模型**，依据：

1. **归属**：该表 DDL 由 APScheduler 的 `SQLAlchemyJobStore.start()` 自己 CREATE IF NOT EXISTS；
   本仓只读它一行状态。映射进 Base = 给同一张表造**第二个 owner**。
2. **create_all 副作用**：本仓 `scripts/migrate_*.py` 会调 `Base.metadata.create_all(engine)`，
   加模型后这些脚本会按我们的猜测去 CREATE 一张**三方表**。
3. **漂移不可见**：APScheduler 大版本改 jobstore DDL（3.x = id varchar(191) / next_run_time double precision /
   job_state bytea），冻结成模型后漂移只在运行期暴露。
4. 实测 `execute(select(...))` **不会**被扫描器计入（`ORM_CONSTRUCT_ARG_RX` 明确排除），
   故该文件 `core_text_sql` 已归零。

---

## 4. 验证

| 项 | 结果 |
|---|---|
| 等价性（真实库、分两进程 dump） | **IDENTICAL**：A 主探针 13796B↔13796B + 集成探针 10176B↔10176B；B 22280B↔22280B、15 个 key 全等 |
| 非空洞断言 | 比对前断言文件非空且 payload 非空（防 `0 == 0` 假通过） |
| **负对照** | A 4 处、B 两轮 6 处定向变异 → **全部被检出**（含 `count(*)` vs `count(列)` 的 0/NULL 语义类） |
| 模型核对 | WatchDigestState 7 列 / WatchIntervention 11 列，与线上**逐列一致**，PK 一致 |
| 定向测试 | 163 + 79 + 247 passed |
| **失败集合 diff** | 与基线 worktree（`8ef46ab7`）**逐条 diff：新增 0 / 消失 0** |
| 扫描器 | in_scope `core_text_sql` 39→10、`cursor_execute` 13→11 |
| 探针清理 | `audit_log` 探针表已 DROP（`information_schema` 计数 0）；DB 各表行数回到基线 |

---

## 5. 过程中抓到并修掉的 **2 个自引入偏差**（真实数据比出来的）

1. **JSONB 置 None 被写成 jsonb 的字面量 `null`**（应为 SQL NULL）——
   `values(col=None)` 受 `none_as_null=False` 影响，落库是与原 SQL `CAST(NULL AS jsonb)` **不同**的值。
2. **`get_industry_totals(None)` 返回 `int 0`**，而旧路径是 `float 0.0`。

两个都是第一轮 old-vs-new diff 抓出来的；修完重跑 → IDENTICAL。

---

## 6. 验证脚本自身出过的错（与代码等价性分开列）

1. **/tmp 目录与并行窗口撞名**：产物被别的窗口清掉，目录里出现不是自己建的 symlink 与 6 层子目录
   —— **差点在空文件上做 diff**（B4-c4"空文件恒等"的同类坑变体）。改用窗口专属目录 +
   比对前 `[ -s a ] && [ -s b ]` 并打印字节数。
2. **`db_cursor()` 默认 `commit=False` → 探针表被静默回滚**：先打印了 PROBE CREATED，下一个连接就报表不存在
   —— 差点把"探针表不存在"误判成"新实现写不进去"。
3. **拿运行顺序当业务语义**：把按 dump 先后递增的 `total_rows` 纳入值比较 → 误报 DIFF；
   改成断言"本侧 rows_before+1 == rows_after"，不再依赖跨文件顺序。
4. **负对照被非空洞断言先炸**：变异让某 key 变空 → 断言先抛，输出里看不到 DIFF 明细（"假失败"）。
5. **老侧 SQL 是"转写的副本"而非模块代码**：以为"逐字抄 = 等价于调老实现"，实际只等价于"抄得对"——
   负对照才暴露它对该模块的变异不敏感。
6. **strict/lenient 对照探针设计错**：先调 lenient（它已回滚修复了被毒化的事务）再调 strict → 测出"不抛异常"。

---

## 7. 既有缺陷（**发现，未修**，只登记）

1. **`audit_log` 表根本不存在** → V13/V14 的"决策落库"**从未成功过一次**：每次日检只留一条
   `audit_log persist failed (non-fatal)` warning，回退分支恒为活路径。**"审计留痕"是纯装饰。**
2. **一个包里有**两个** declarative Base**：`orm/base.py`（59 张表）与 `orm/config.py`（只挂 `quant.trades`），
   而 `orm.__init__` 导出的 Base 是 **config 那个** → `from infrastructure.persistence.orm import Base;
   Base.metadata.create_all(engine)` **几乎什么都建不出来**（新建代码照抄就会静默空跑）。
3. **`get_rule_trigger_stats` 的 NULL `rule_id` 静默返回部分结果**：`int(None)` 抛 TypeError 被吞 →
   返回已累计到那一行为止的 dict（实测 25 组只剩 6 组，不报错、日志级别不提升）。
4. **同名表两份**：`public.apscheduler_jobs`（32 行，活）与 `quant.apscheduler_jobs`（0 行，疑似残留）。
5. **`WatchRule.tokens_cost` 模型声明 `Numeric(12,4)`，真实列是 `double precision`**（类型漂移）。
6. **`quant_test` 库 schema 漂移**：`strategy_configs` 缺 `structure_status / performance_status`。
7. `models/strategy_validation.py` 模块 docstring 与列注释对"是否有外键"**自相矛盾**（真实库**有** FK CASCADE）。

---

## 8. 未验证 / 不确定（诚实列）

1. **异常/降级分支没做真故障注入**（只做静态核对 + 单点探针）。
2. **新旧在异常后的 session 状态刻意不一致**：旧实现自开连接不受影响，新实现共用 scoped_session
   （已加 `_safe_rollback()`）。返回值一致，但**若调用方在同线程有未提交 ORM 事务会被一起回滚** ——
   未做并发/事务嵌套验证。
3. **探针是单线程脚本**，scoped_session 的并发语义未覆盖。
4. **站点 6 的探针表列类型是猜的**（表不存在、仓内无 DDL）：证明的是"两条路径发出同一份 SQL 与参数"，
   **不是**"这张表将来就是这个形状"。
5. **NULLS LAST 分支未被真实数据覆盖**（`evolution_strategy_runs` 每 run 的 fitness 全非 NULL）。
6. **未跑全量测试套件**（只跑相关子集）。

---

## 9. 仍未处置（待用户裁决）

| 项 | 站点 | 说明 |
|---|---|---|
| `signal_tracking_repository.py` | 8 | 持有**刻意的**裸连接（自愈 + 借还），且 `tests/test_signal_tracking_connection.py` 把该机制**固化**。改 ORM = 拆机制，需连同测试一起重新设计 |
| `async_base_repository.py` ×5 / `dependency_check.py` ×2 / `ml_model_repository.py` ×1 / `portfolio_repository.py` ×1 | 9 | 见 §0：**按设计就是 SQL**，需裁决"行级豁免标注"还是"常驻计数" |
| `qlib_repository.py` | 4 | 源表 `klines` **全库不存在** → `get_features` 永远静默返回空 DataFrame。改表名 = 换数据源 = 改行为 |
| 通用 SQL 助手（`core_plan_service` / `data_hygiene_service` / `strategy_evaluation_service`） | 6 | 需先设计**类型化查询端口**，再改 27 个调用点 —— 设计题不是机械题 |
| `symbol_classifier.py` | 1 | 注释写明**故意**不用 ORM：曾致 `idle in transaction` 约 337s 被 DB 强杀 + `session_leak_detected` |
| `test_cron_parsing.py` | 1 | 仓库根目录的**一次性运维脚本**（无 test 函数、顶层 exit()），非测试 |

---

## 10. 新增工具

`tools/non_orm_sql_lines.py` —— **按行**定位扫描器命中（复用扫描器同一套口径，不另立标准）。
本次靠它把 61 个站点拆成可执行清单：**裸 grep 会多算**
（`strategy_repository` 实际 3 处，裸 grep 出 7 处）。
⚠️ 它**未实现** `psql_subprocess` 指标 —— 逐行复核"无命中"不能单独作为归零证据（两套都要跑）。
⚠️ 期间我把它从 `_scan_lines.py` 改名为 `non_orm_sql_lines.py` 并入库；
有子代理误以为"工具被并发窗口删了"（当时它尚未进 git，改名不留痕）—— 现已纳入版本控制。
