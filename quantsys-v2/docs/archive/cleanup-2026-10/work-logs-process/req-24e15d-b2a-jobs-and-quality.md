# REQ-24e15d 批次 B2-a —— jobs 层收尾 + 两张"无主表"落 ORM（t4）

- **执行窗口**：w-32314d00（investor / 投资脑）
- **日期**：2026-09-14
- **批次范围**：3 个 jobs 文件、7 处裸 SQL 点
- **验收**：逐文件回归 + `non_orm_sql_scan.py --gate`

---

## 0. 结果一句话

**`infrastructure/jobs/` 目录裸 SQL 清零**（3 个文件 7 处 → 0），
其中 `core_text_sql` −5、`cursor_execute` −2、`fstring_sql` −1。

| 指标（本轮范围） | B2-a 前 | B2-a 后 |
|---|---|---|
| cursor_execute | 106 | **104** |
| core_text_sql | 35 | **30** |
| fstring_sql | 11 | **10** |
| session_execute_var（审计桶） | 48 | 49 |

`--gate` 退出码 0（P0 恒为 0）。

---

## 1. 迁移的 7 处

| 文件 | 处数 | 去向 |
|---|---|---|
| `financial_data_update_job.py` | 2（1 处还是**列名 f-string 拼接**） | `StockORMRepository` |
| `financial_timeliness_check_job.py` | 3 | `JobRunRepository` / `StockORMRepository` / `FinancialORMRepository` |
| `data_quality_check_job.py` | 2（同一 SQL 的"失败重试"两遍） | `KlineQualityRepository` |

作业层现在**不再持有 session，也不出现任何 SQL 文本**。

---

## 2. 新增（两张此前"无主"的表终于有 ORM 模型）

- **`quant.inprocess_job_runs`** → `models/job_run.py` + `JobRunRepository`
  （表结构此前只写死在 `daily_jobs_bootstrap.py` 的建表 SQL 里，
  读写散在 bootstrap 与 timeliness job 两处；本批先收口**只读**，
  写入路径的幂等语义单独评估，避免与 bootstrap 打架）
- **`public.kline_data_quality`** → `models/data_quality.py` + `KlineQualityRepository`
  ⚠️ 该表在 **public** schema（不是 quant），必须显式声明，否则 SQLAlchemy 报 UndefinedTable；
  ⚠️ 与 `data_quality_repository.py`（管 `quant.data_quality_records`）是**两张不同的表**，
  命名已刻意区分（KlineQuality vs DataQuality）。
- `StockORMRepository` 新增：`list_symbols_by_market` / `update_financial_columns` /
  `get_latest_financial_update_time`；`FinancialORMRepository` 新增 `get_latest_report_date`。

---

## 3. 三个**刻意保持语义不变**的点（迁移最容易在这里出事故）

1. **单事务语义**：`financial_data_update_job` 原来是"循环 UPDATE + 末尾一次 commit +
   异常 rollback"。故 `update_financial_columns` 默认 **commit=False**，
   由调用方在循环后用 `repo.commit() / repo.rollback()` 收口 ——
   若图省事让仓储逐行提交，就会从"全批成功才落库"退化成"半批入库"。
2. **不过滤停牌/退市**：`list_symbols_by_market` 与既有 `list_by_market` 语义**不同**，
   后者默认排除停牌/退市。财务更新的 A 股宇宙原 SQL 是 `WHERE market='A'`，不夹带过滤，
   所以没有复用 `list_by_market`（复用会静默缩小宇宙）。实测同为 5857 只。
3. **白名单双保险**：列名无法参数化，白名单是唯一正解。作业层原有
   `WRITABLE_STOCK_COLUMNS` 保留，仓储侧**再校验一次**（`allowed_columns`）——
   这条在 B1 就立过规矩，不能在收口时丢掉。

---

## 4. 顺手清掉的死代码

`data_quality_check_job._get_alert_session()`：它唯一的存在理由是"告警查询前先回滚挂起事务、
失败则丢弃重建会话"，而这个语义已由 `KlineQualityRepository.count_by_grade_on`
（失败先 `_safe_rollback` 再抛）承担。收口后它变成无人调用的死代码，
留着只会诱导后来者再写一套会话修补 —— 已删除并留注释说明去向。

---

## 5. 验证证据

- **活体验证**（真库、非 mock）：
  - `list_symbols_by_market('A')` = 5857 只（与原 SQL 一致）
  - `get_latest_financial_update_time()` = 2026-09-13 03:39:32+08
  - `get_latest_report_date('balance_sheets')` = 2026-06-30
  - `KlineQualityRepository.count_by_grade_on('D', 2026-09-11)` = 549
  - `JobRunRepository.exists('evening_pipeline')`、`list_by_date(2026-09-11)` = 7 条
  - **写路径幂等验证**：把 600519 现有 roe/gross_margin 原值写回（值不变）→ 前后一致；
    并用 `{'evil_column': 1}` 实测白名单**确实拒绝**且事务回滚干净。
- **回归**：197 passed / 3 skipped（含 B1 与 bug 批次全部相关文件，无回归）。
- **闸门**：`--gate` 退出码 0。

---

## 6. 本批发现但**未修**（已用 HEAD 干净 worktree 复现确认是既有问题）

`tests/test_stock_repository.py` 4 个用例在 HEAD 上同样失败（**非本次改动引入**）：

| 用例 | 现象 | 初步判断 |
|---|---|---|
| `test_get_by_symbol_validation` | `get_by_symbol("")` / `("1234")` 不抛 ValueError | 缺参数校验（真实缺陷） |
| `test_get_all_with_filters` | `get_all(is_st=...)` 不接受该参数 | 测试与 API 漂移（真实签名是 `include_suspended`） |
| `test_batch_get_fundamentals` | 用 `'000001.SH'` 这类**带后缀**代码查库 | 测试数据漂移（库内是裸 6 位码） |
| `test_get_index_constituents` | 期望去重后 8 只，实得 10 只（含重复） | 疑似**真缺陷**：`get_index_constituents` 未去重 |

留给下一批处理（需要先定 `get_by_symbol` 是否该抛异常，以及测试是否改用裸码）。

---

## 7. 下一步

B2-b：`adapters/inbound/fastapi_app/routes/data_quality_async.py`（2）、
`adapters/outbound/datasources/sector_snapshot.py`（3+1）、
`infrastructure/adapters/industry_data_adapter.py`（4+2，白名单模板已有）。
之后 B3（services/routes → 仓储）、B4（仓储内 cursor→ORM）、B5（read_sql 单点）。
