# REQ-261006163444-8e4f · 拆分计划

**需求**：数据质量告警去伪（D级计数按当日行数重复计数 + 检查域混入退市股）
**依据**：`requirement.md`（6 条 FR）+ `design/`（architecture / data-model / interfaces / test-cases / use-cases）
**目标一句话**：让三项质量告警只在**可交易域**内判定——分母真实、样本有效、掉出必亮相。

## 1. 代码层面变更盘点（对照设计）

### 新增

| 文件 | 职责 |
|---|---|
| `application/services/kline_domain.py` | 分域纯函数：`DomainSnapshot` / `classify_domain` / `build_domain_snapshot`（无 DB、可单测） |
| `tests/test_kline_domain.py` | 分域判据用例（gap 边界、无 prev、退化、不变量） |
| `tests/test_data_quality_alert_scope.py` | 告警口径用例（去重、域内阈值、掉出名单、回填门槛、审计列、降级） |
| `docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md` | 迁移/兼容/回滚清单（含旧调用方核对与配置旧值） |

### 修改

| 文件 | 精确到函数 |
|---|---|
| `adapters/outbound/repositories/kline_repository.py` | `KlineORMRepository` 新增 `list_recent_trade_dates(limit=2)`、`list_symbol_last_trade_date()` |
| `adapters/outbound/repositories/kline_quality_repository.py` | `count_by_grade_on` 改 distinct 标的语义 + 可选 `symbols` 限定 |
| `application/services/data_quality_service.py` | `check_data_quality` 增返回 `per_symbol`（全量、8 键）；循环内 grade 单点计算；`_persist_quality_audit` 修 `original_count` 取键 |
| `infrastructure/jobs/data_quality_check_job.py` | 建域快照 → 域内聚合 → `_check_quality_alerts` / `_send_quality_alerts` 新签名与判据 → 回填目标限域 → `_normalize_params` 新增四键 → `result` 新增三键 |
| `tests/test_data_quality_job_guardrails.py` | 替身 `check_data_quality`（:70）补 `per_symbol`（契约变更所致） |
| `quant.scheduler_tasks` id=232（**数据行**，非 schema） | `params.quality_threshold` 95.0 → 88.0（jsonb 合并，旧值留痕） |

### 删除

**无。** 不删键、不删函数、不删文件；`count_by_grade_on` 只改语义不改签名。

## 2. 批次与依赖

| 批次 | 卡 | 依赖 | 说明 |
|---|---|---|---|
| 1 · 契约与地基 | t1, t2, t3 | —— | 三张卡互不依赖，可并行；先把"接口/数据契约"落死，实现卡才开工 |
| 2 · 接线 | t4 | t1, t2, t3 | 唯一改动告警判据的卡；前向引用为 0 |
| 3 · 用例 | t5, t6 | t5←t1；t6←t4 | 用例与被测面成对；含 4 条反例锁 |
| 4 · 上线动作与兼容 | t7, t8 | t7←t4,t6；t8←t4 | 配置行变更 + 实跑复验；兼容/回滚清单 |

容量核算（`detailUnits = files×1 + anchors×0.5 + chars/2000`，容量 16 DU）：各卡 3.5–9.25 DU，**无超容量卡**。

## 3. 任务表

### t1 · 新增分域纯函数模块（契约先行）

- **phase / side**：implement / backend
- **depends_on**：——
- **implementation**：
  - 新建 `application/services/kline_domain.py`，按 `design/interfaces.md` §1 定死三个符号：
    `DomainSnapshot`（frozen dataclass，字段与默认值照抄）、`classify_domain(trade_dates_desc, symbol_last_dates)`、
    `build_domain_snapshot(kline_repo)`；常量 `TRADABLE_MAX_GAP=0` / `STOCK_MIN_GAP=5` / `UNKNOWN_GAP=9999`。
  - `gap = rank(mx) - 1`（名次倒序，`D_last` 名次 1；订正设计初稿笔误 `rank(D_last) - rank(mx)`）；`mx` 不在交易日集合 ⇒ `9999`。
  - `dropped_new = {s | gap == 1}`；`dropped_known = prev_trade_date is not None`；
    查询/解析异常收敛为 `degraded=True + degrade_reason`（**不抛**）。
  - `build_domain_snapshot` 调 t2 的两个仓储方法；本卡只写模块与 docstring，**不接线到作业**。
  - 验证：`./venv/bin/python -c "from application.services.kline_domain import classify_domain; print(classify_domain(['2026-09-30','2026-09-29'],[('600519','2026-09-30')]))"`
- **acceptance**：`./venv/bin/python -c` 导入成功并打印出 `tradable` 含 `600519`；
  `grep -c "import psycopg\|from adapters" application/services/kline_domain.py` 输出 **0**（纯函数，无 DB 依赖）。
- **requirement_refs**：FR-1, FR-3 ｜ **decisionRefs**：D-3, D-4
- **footprint**：`{"files": 1, "anchors": 4, "chars": 3000}`

### t2 · 仓储：分域两个只读方法 + 评级计数改 distinct

- **phase / side**：implement / backend
- **depends_on**：——
- **implementation**：
  - `adapters/outbound/repositories/kline_repository.py`：给 `KlineORMRepository` 加
    `list_recent_trade_dates(limit=2)`（`DISTINCT trade_date ORDER BY DESC LIMIT n`）与
    `list_symbol_last_trade_date()`（`GROUP BY symbol` 的 `MAX(trade_date)`），SQL 照 `design/data-model.md` §2。
  - `adapters/outbound/repositories/kline_quality_repository.py`：`count_by_grade_on(grade, day=None, symbols=None)`
    改 `count(distinct KlineDataQuality.symbol)`，`symbols` 非空时加 `in_` 过滤；保留 `_safe_rollback` 语义。
  - 验证：两条 SQL 各跑一次，比对 `psql` 独立结果。
- **acceptance**：
  ① `list_recent_trade_dates(2)` 返回 `['2026-09-30','2026-09-29']`；
  ② `len(list_symbol_last_trade_date()) == 5686`；
  ③ `count_by_grade_on('D')` == `select count(distinct symbol) from public.kline_data_quality where created_at::date=current_date and grade='D'`（今日 **404**，不再是 806）。
- **requirement_refs**：FR-1, FR-2 ｜ **decisionRefs**：D-3
- **footprint**：`{"files": 2, "anchors": 3, "chars": 2500}`

### t3 · 服务层：per_symbol 全量事实 + grade 单点计算 + 审计列取键

- **phase / side**：implement / backend
- **depends_on**：——
- **implementation**：
  - `application/services/data_quality_service.py::check_data_quality`：循环内把每只标的的
    `coverage_rate / missing_days_count / quality_score / overall_score / grade / has_duplicates /
    has_anomalies / anomaly_unknown` 收进 `per_symbol`（**唯一一次** `_calculate_grade` 调用），
    返回体新增 `per_symbol` 键（形状照 `design/data-model.md` §6）。
  - `_persist_quality_audit`：`original_count` 改取 `gap_info.get('total_trading_days', 0)`；
    `grade`/`overall_score` 改为**接收**循环内算好的值，不再在函数内重算。
  - 不改 `summary` 任何既有键（全库口径保留）。
  - 验证：小样本调用（`symbols=['600519']`）打印返回键集与 `per_symbol` 形状。
- **acceptance**：
  ① `set(res.keys()) ⊇ {'summary','stocks_with_issues','per_symbol'}`，且 `per_symbol['600519']` 恰含设计规定的 8 键；
  ② 小样本跑完写库后 `select original_count from public.kline_data_quality order by created_at desc limit 1` **> 0**；
  ③ `./venv/bin/python -m pytest tests/test_data_validator_anomaly_detection.py -q` 全过（既有消费者不受影响）。
- **requirement_refs**：FR-2, FR-5
- **footprint**：`{"files": 1, "anchors": 3, "chars": 2500}`

### t4 · 作业层接线：域内聚合 + 新告警判据 + 回填限域

- **phase / side**：implement / backend
- **depends_on**：t1, t2, t3
- **implementation**：
  - `infrastructure/jobs/data_quality_check_job.py`：
    ① `_normalize_params` 新增 `d_grade_threshold=20` / `quality_threshold` 缺省改 **88.0** /
    `coverage_info_threshold=97.0` / `backfill_fail_rate_threshold=50.0` / `backfill_min_sample=10`，
    全部进 `effective_params` 与 `param_notes`；
    ② 检查前 `build_domain_snapshot(service.kline_repo)`；
    ③ 回填候选集改为 `per_symbol` 里 `missing_days_count > 0` **且** `symbol in domain.tradable`，
    仍按缺失天数降序（**不再**用 `stocks_with_issues[:50]`）；
    ④ `_check_quality_alerts(result, domain, per_symbol, thresholds)`：按 `design/interfaces.md` §4.3 算
    `DomainStats`，判据为 域内 D级 > 20 / 评分 < 88.0 / 覆盖率仅信息项 / 回填失败率 > 50% 且 n ≥ 10 /
    `dropped_new` 非空 → warning；`result` 新增 `alert_scope` / `domain` / `domain_dropped` / `alert_thresholds`；
    ⑤ `_send_quality_alerts(alerts, stats, thresholds)` 按 `design/interfaces.md` §5 渲染正文；
    ⑥ 降级分支：`domain.degraded` 或 `per_symbol` 缺失 ⇒ error 项 `qa_scope_unavailable`，`alert_scope="degraded"`，
    **不**回退 `count_by_grade_on`。
  - **负向**：`per_symbol` 不得进入 `result` 或日志全文。
  - 验证：用桩数据（域 3 只 D / 均值 90.84 / 掉出 3 只）直接调 `_check_quality_alerts` 打印正文。
- **acceptance**：
  ① 桩数据正文含 `检查域: 可交易 … / 观察中 … / 存量 …`、`本期掉出可交易域: 3 只`，且**不含**「D级股票数量过多」「数据质量评分偏低」；
  ② `per_symbol` 缺省时产出 error 项 `qa_scope_unavailable` 且 `result['alert_scope']=='degraded'`；
  ③ `python -c "import json,infrastructure.jobs.data_quality_check_job as m"` 无导入错误；
  ④ 回填目标在桩数据下 100% 落在 `domain.tradable`。
- **requirement_refs**：FR-1, FR-2, FR-3, FR-4 ｜ **decisionRefs**：D-2, D-3, D-4
- **footprint**：`{"files": 1, "anchors": 6, "chars": 4500}`

### t5 · 分域纯函数用例（含边界与不变量）

- **phase / side**：test / backend
- **depends_on**：t1
- **implementation**：新建 `tests/test_kline_domain.py`，实现 `design/test-cases.md` §1 的 T1–T7：
 三分法、gap 4/5 边界、gap==1 ⇒ observing∩dropped_new、无 prev、空输入退化、
  `mx` 不在交易日集合的哨兵、三集合两两不相交且并集 == `gap_days`。
- **acceptance**：`./venv/bin/python -m pytest tests/test_kline_domain.py -q` 全过（≥7 条）；
  其中 T5 断言"不抛异常且 `degraded is True`"、T7 断言并集/交集不变量。
- **requirement_refs**：FR-1, FR-3, FR-6 ｜ **decisionRefs**：D-3, D-4
- **footprint**：`{"files": 1, "anchors": 7, "chars": 3500}`

### t6 · 告警口径用例（含 4 条反例锁）

- **phase / side**：test / backend
- **depends_on**：t4
- **implementation**：
  - 新建 `tests/test_data_quality_alert_scope.py`，实现 T8–T17：域内均值/D 计数、阈值双向边界（20/21、88.0/87.9）、
    掉出名单与 20 只截断、回填样本门槛（n=7 不判 / n=10 判）、回填目标限域、`original_count` 非 0、
    `count_by_grade_on` 去重、`partial` 截断标注、`per_symbol` 缺失降级。
  - 更新 `tests/test_data_quality_job_guardrails.py:70` 的替身 `check_data_quality`，补 `per_symbol`。
  - 4 条反例锁（L1–L4）在**改动前**的代码上各跑一次并保留输出到本卡汇报。
- **acceptance**：
  ① `./venv/bin/python -m pytest tests/test_data_quality_alert_scope.py tests/test_data_quality_job_guardrails.py -q` 全过；
  ② 汇报里附 L1–L4 改前红/改后绿的两次输出（缺一即视为锁无效）。
- **requirement_refs**：FR-2, FR-3, FR-4, FR-5, FR-6
- **footprint**：`{"files": 2, "anchors": 10, "chars": 4500}`

### t7 · 配置行变更 + 实跑复验（出证据）

- **phase / side**：implement / backend
- **depends_on**：t4, t6
- **implementation**：
  - `UPDATE quant.scheduler_tasks SET params = params || '{"quality_threshold": 88.0}' WHERE id = 232;`（幂等）。
  - 触发一次 task 232（手动路径），采集 `logs/api.log` 的 `data_quality_alert` 段与
    `quant.scheduler_runs` 最新 `result` 的 `domain` / `domain_dropped` / `alert_scope` / `alert_thresholds`。
  - 同时核对：回填目标是否 100% 在域内、`All data providers failed` 新增条数、`original_count > 0`。
- **acceptance**：
  ① 正文出现三段新内容（检查域计数 / 掉出名单 / 统计 N/N 只），**不含**「D级股票数量过多」「数据质量评分偏低」；
  ② `result->>'alert_scope' == 'tradable'`，`result->'domain'->>'tradable_count'` ≈ 5280；
  ③ 复验窗口内 `grep -c "All data providers failed"` **= 0**（今日基线 374）；
  ④ 新写入行 `original_count > 0`。四个输出原样贴进任务汇报。
- **requirement_refs**：FR-2, FR-4, FR-5, FR-6
- **footprint**：`{"files": 1, "anchors": 4, "chars": 2000}`

### t8 · 迁移 / 兼容 / 回滚清单

- **phase / side**：doc / doc
- **depends_on**：t4
- **implementation**：
  - 新建 `docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md`，写清：
    ① **零 schema 变更**的声明与依据；② 旧调用方核对清单（`routes/data_quality_async.py:162`、
    `tests/test_data_validator_anomaly_detection.py:212`、`tests/test_data_quality_job_guardrails.py:70` 替身）逐条结论；
    ③ 配置旧值（`quality_threshold = 95.0`）与回滚步骤（还原提交 + 改回 95.0）；
    ④ 历史 `original_count = 0` 行的阅读口径（2026-10-06 前不可用，不追改）；
    ⑤ 部分回滚的两条路径与后果。
- **acceptance**：文档内五节齐全且每节可指到具体文件/行；
  `grep -c "零 schema" docs/requirements/REQ-261006163444-8e4f/notes/migration-rollback.md` ≥ 1；
  旧调用方清单条数与 `grep -rn "check_data_quality(" --include='*.py'` 的命中数一致（9 处，含定义与同名异类）。
- **requirement_refs**：FR-5, FR-6
- **footprint**：`{"files": 1, "anchors": 3, "chars": 2000}`

## 4. 验收口径总表（可跑）

| FR | 判据 | 命令 |
|---|---|---|
| FR-1 | 三层计数 5280 / 3 / 403，合计 5686 | SQL 复算（`design/test-cases.md` §3.2） |
| FR-2 | 域内 3 只 / 90.84 → 两条告警不出现；`count_by_grade_on('D')` = 404 而非 806 | 实跑 + SQL |
| FR-3 | 掉出域 3 只时正文出现名单；存量次日不重复 | `pytest tests/test_data_quality_alert_scope.py` |
| FR-4 | 阈值 20 / 88.0 / n ≥ 10；回填目标 100% 在域内 | `pytest` + 实跑日志 |
| FR-5 | `original_count > 0` | SQL（`design/test-cases.md` §3.5） |
| FR-6 | 新增+既有用例全过；4 条反例锁改前必红 | `pytest tests/test_kline_domain.py tests/test_data_quality_alert_scope.py tests/test_data_quality_job_guardrails.py -q` |

## 5. 边界（本计划不覆盖，防范围蔓延）

1. 不补 239 只标的的 `is_delisted` / `is_suspended` 标记（后续线 1）。
2. 不改评分公式、Z-score 阈值、等级分数线。
3. 不改检查窗口（90 天钳制）、排班、`policy=holidays`。
4. 不回填历史 `original_count = 0` 的行。
5. 不动服务层 `stocks_with_issues[:50]` 截断本身。
6. 不做"整管道停摆"检测（责任方 `freshness_guard`；本计划只在正文打印最后交易日）。
