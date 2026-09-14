# REQ-24e15d 残余收口：死链删除 + 模型↔DDL 缺口 + 豁免基线（2026-09-15，w-2129d492）

- 需求：REQ-24e15d「quantsys-v2 裸 SQL 全量迁 ORM」（需求属窗口 w-32314d00，本窗口接手残余）
- 分支：`chore/v2-orm-residual`（worktree `.claude/worktrees/orm-residual`）
- 基线工具：`tools/non_orm_sql_scan.py`（**必须用 `./venv/bin/python`**，系统 python3.9
  会在 PEP 701 f-string 上直接 SyntaxError）

## 0. 本轮范围的两条边（别把两者混为一谈）

用户问的是"v2 项目没用 orm 的 sql"，它其实有两个**不同**的度量面，本轮两条都测了：

| 面 | 工具 | 口径 |
|---|---|---|
| **代码侧**：裸 SQL 不走 ORM | `tools/non_orm_sql_scan.py` | 本轮范围（非 scripts/tools/live_trading）命中数 |
| **schema 侧**：库里有表但无 ORM 模型 | `tools/oneoff/orm_drift_probe.py`（正查）+ 本轮新增反查 | 155 张基础表中 **82 张**无模型 |

**schema 侧 82 张的归属**（本轮只做归属判定，未动库）：agent-os 自有 `public.*` 22 张
（**不属 v2，不许动**）、v2 遗留空表/备份表、以及 3 张有数据的裸 SQL 表
（`signal_tracking` / `scheduler_watchdog_log` / `data_contracts`）。
其中 `quant.signal_tracking` 正是下面 §3 剩余 8 处的所在地。

## 1. 代码侧基线（本轮起点）

    [P0] fstring_value_interp   本轮范围  0     OK
    [P0] raw_connect            本轮范围  0     OK
    [P1] cursor_execute         本轮范围 11
    [P1] core_text_sql          本轮范围 10
    [P2] session_execute_var    本轮范围 63    （审计桶：正则判定不了，非"确认未迁移"）
    [P2] fstring_sql            本轮范围  2
    [P2] read_sql               本轮范围  5
    [P2] psql_subprocess        本轮范围  1
    → 确认未迁移 = 29 处

## 2. 已收口（29 → 14）

### 2.1 删死链 qlib（4 处：read_sql 3 + fstring_sql 1）

删 `adapters/outbound/repositories/qlib_repository.py`、
`application/services/qlib/{__init__,qlib_data_adapter}.py`、`tests/test_qlib_data_adapter.py`。

**为什么是"删"而不是"修表名"**（四条独立证据，缺一不可）：
1. **它跑不起来**：`import qlib.data` → `ModuleNotFoundError`（venv 里 qlib 包存在但
   `qlib.data` 子模块缺失）⇒ `QuantsysV2DataProvider.__init__` 必抛 ImportError；
2. **它没被任何人用**：全仓（含 agent-ts/agent-os/web-frontend，排除 worktrees）grep
   `QlibDataRepository|QuantsysV2DataProvider|qlib_data_adapter` → 除自身与该测试外 **0 命中**；
3. **它的数据契约坏了两层**：SQL 写 `FROM klines`，而全库**没有** `klines`（只有
   `quant.daily_klines` / `quant_compat.daily_klines`）；即便换对表名也没用 ——
   `quant.daily_klines.symbol` 是**裸 6 位**（实测 466 万行，带点号 0 行），
   qlib 侧传的是 `600000.SH`，`IN (...)` 恒空；
4. **它自陈残缺**：包 `__init__.py` 的 `__all__` 列了 4 个服务，
   `QlibAlpha158Service/QlibModelService/QlibBacktestService` **三个模块根本不存在**。

处置依据与 `quant.async_factors` 同型（无迁移建表、无人实例化、端口无调用方）→ 删。
**未动** `domain/quantlib/`（那是 RL 环境，被 `tests/test_rl_integration.py` 等真实使用）。

### 2.2 删仓库根一次性运维脚本（1 处：psql_subprocess）

删 `quantsys-v2/test_cron_parsing.py`：文件名叫 `test_*` 但**没有任何 test 函数**，
顶层就是 `print` + `subprocess psql` + `exit(1)`，是 2026-08 的一次性排障脚本。
`pytest.ini` 的 `testpaths = tests` 让它从未被收集（故删它不影响收集数，实测前后均 6003）。

### 2.3 `signals.action_type` 缺省值（修掉 17 个 ERROR）

**实测**（不是转述）：`tests/services/test_heatmap_service.py` +
`tests/repositories/test_heatmap_repository_events.py` 共 **17 例 ERROR**：

    psycopg2.errors.NotNullViolation: null value in column "action_type"
    of relation "signals" violates not-null constraint

根因：`quant.signals.action_type` 是 `integer NOT NULL` 且**无 server default**（生产实测），
而模型也只有 `Column(Integer, nullable=False)`；全仓只有 `signal_repository.create_signal`
**一处**会推导它（`buy→1 / sell→2`）。任何别的 ORM 写入漏传即炸。

修法（**不改 DDL**）：
- `infrastructure/persistence/orm/models/action_norm.py`：把散落的两处字面量收敛为
  `SIGNAL_ACTION_TYPE = {'BUY': 1, 'SELL': 2}` + `signal_action_type()`（唯一事实源）；
- `orm/models/signal.py`：`action_type` 加 `default=_derive_action_type`
  —— 缺省值由**同一条 INSERT 的 action** 推导，写入方不可能忘；显式传入永远优先；
- `signal_repository.py`：改调共享函数，删掉第二份字面量。

**验证**：17 ERROR → 7 例转为 PASS + 10 例转为 FAIL（见 §4，经 HEAD 基线证明是**既有**失败）。

### 2.4 模型↔DDL 缺口：补迁移（不是继续豁免）

`tests/test_orm_db_drift.py` 曾把 9 列登记进 `_ENV_ONLY_MISSING` 豁免（"测试库镜像不全，
非漂移"）。但豁免**只让门禁不报，没让测试能跑** —— 这正是 §2.3 修完后暴露的下一层：

    UndefinedColumn: column "pool_name" of relation "pool_change_log" does not exist

这 9 列都被 ORM 模型声明、生产库里也确实存在，但**没有任何 migration 创建过它们**
（历次线上手工 ALTER 未回流）。新增 `migrations/add_missing_orm_columns.sql`：
`pool_change_log.pool_name`、`event_calendar.{scope,evidence_hash,source_url,symbols}`、
`strategy_configs.{structure_status,performance_status,performance_evidence,performance_checked_at}`，
全部 `IF NOT EXISTS`（生产 no-op），类型/可空/默认值逐列照抄生产 `information_schema`。

随后把 `_ENV_ONLY_MISSING` **清空** —— 门禁收紧后仍 6 passed，证明缺口真被补上
（保留机制本身，只清空条目）。

### 2.5 扫描器：把"按设计即 SQL"变成可审计的显式基线（10 处）

`tools/non_orm_sql_scan.py` 新增 `EXEMPTIONS` 登记表。**为什么不是继续常驻计数**：
这 10 处（通用异步执行器原语 5、连通探针 2+1、PG 专有构造 1、故意不用 ORM 的历史修复 1）
**无法也不应**改成 ORM；和真债混在同一个数字里，结果是数字永远归不了零、
每个新人都把这十处重查一遍。

三条自维护硬校验（任一不满足 `--gate` 退出码 1）：
1. 理由为空 → 拒绝（"不想解释就别豁免"）；
2. **实际 > 登记** → 同文件同指标混入了**新的**未迁移 SQL；
3. **实际 < 登记** → 登记过期（多半已迁完），提醒删条目。

**故障注入实测**（三条各注入一次，全部按预期 exit 1 并给出对应文案，注入后文件已精确复原）：

| 注入 | 期望 | 实测 |
|---|---|---|
| `symbol_classifier` 登记 1→2 | 登记过期 | ✅ `实际 1 < 登记 2 —— 登记过期` |
| `async_base_repository` 登记 5→3 | 新债 | ✅ `实际 5 > 登记 3 —— 混入了新的未迁移 SQL` |
| 探针条目理由置空 | 拒绝 | ✅ `豁免理由为空（空理由不得豁免）` |

同时把 `session_execute_var`（63）**排除出"未迁移"**：正则判定不了
`session.execute(<标识符>)` 装的是 `select()` 还是裸 `text()`，单列为审计桶。

## 3. 剩余 14 处（两类设计任务，不是机械活）

      8  adapters/outbound/repositories/signal_tracking_repository.py     cursor_execute=8
      2  application/services/core_plan_service.py        cursor_execute=1, read_sql=1
      2  application/services/data_hygiene_service.py     core_text_sql=2
      2  application/services/strategy_evaluation_service.py core_text_sql=1, read_sql=1

- **`signal_tracking_repository`（8）**：`quant.signal_tracking` **无 ORM 模型**（且测试库
  整张表都没有）。改 ORM 需要：新建模型 + 迁移 + 重写仓储 + **重写
  `tests/test_signal_tracking_connection.py`**（该测试锁定了自愈连接机制）+ 处理 4 个
  注入 `db_connection` 的调用方（`signal_tracking_service` 3 处、`weekly_report_service`、
  `attribution_service`）。其中 `update_signal_performance` 现在用 f-string 拼 `SET 列名`
  —— 改成 ORM 时顺便把列名收敛成白名单（真收益）。**本轮未做**：它牵动 4 个消费方与一个
  锁定机制的测试，属"需设计"而非机械替换。
- **通用 SQL 助手（6）**：三个服务的 `query_scalar/query_rows/_query_df` 被 **27 个调用点**
  共用 → 需要先设计**类型化查询端口**，再由调用点逐个迁移。

## 4. 回归与基线对照

判定"是否引入新失败"用 HEAD 干净 worktree 跑同一组用例并**逐条 diff 失败集合**
（不能用数量、也不能看"像不像既有问题"）。

- **HEAD 基线对照（关键）**：把 HEAD 的 heatmap 夹具**只**中和掉 `action_type` 缺省问题后，
  失败集合与分支**逐条相同**（10 failed / 7 passed）⇒ §2.3 的改动**零新增失败**，
  它只是把 17 个 setup ERROR 变成 7 passed + 10 个**既有**失败。
- **测试库列差**：分支前后 `quant_investment` vs `quant_test` 的"生产有/测试库缺"由
  **10 列降为 1 列**（仅剩 `simulation_equity_snapshot.is_synthetic`，该列无 ORM 模型声明）。
- 收集数：分支 6003 ≡ HEAD 6003（删除的两个文件本就 0 收集项）。

## 5. 本轮新暴露、但**不属**本轮范围的既有缺陷（如实记录，未修）

`tests/services/test_heatmap_service.py` 的 10 例失败根因**不是本轮的改动**，经基线对照确认为既有：

    heatmap_aggregation_failed error='combine() argument 1 must be datetime.date, not MagicMock'

链路：`conftest.py:31-44` 把 `EnhancedServiceFactory.resolve` 打桩成"解析失败就返回
`MagicMock()`"；`HeatmapService.repo` 正是通过它解析 `IHeatmapRepository` → 拿到 MagicMock
→ `dates[0]` 是 MagicMock → `datetime.combine(MagicMock, time.max)` 抛错。
**这是"静默假成功"的又一个同型案例**：服务未注册被伪装成一个"能应答一切"的对象，
错误延后到几十行之外才以完全无关的形态爆出来。建议单列（修法：测试内显式注册该端口，
或让桩改为 fail-fast 而不是返回 MagicMock）。

## 6. 复跑命令

    cd quantsys-v2
    ./venv/bin/python tools/non_orm_sql_scan.py          # 看"未迁移"与豁免清单
    ./venv/bin/python tools/non_orm_sql_scan.py --gate   # 退出码 0
    ./venv/bin/python -m pytest tests/test_orm_db_drift.py -q   # 需 PGDATABASE 指向 *_test
