# REQ-24e15d 批次 B2-b —— 路由层 / 数据源层裸 SQL 收口（t4）

- **执行窗口**：w-32314d00（investor / 投资脑）
- **日期**：2026-09-14
- **范围**：3 个文件、6 处裸 SQL/半 ORM 点
- **验收**：逐文件回归 + `--gate`

---

## 1. 改动

| 文件 | 处数 | 去向 |
|---|---|---|
| `adapters/inbound/fastapi_app/routes/data_quality_async.py` | 2（text()） | `KlineORMRepository.get_recent_trading_days` + `FactorORMRepository.get_freshness_by_factor` |
| `adapters/outbound/datasources/sector_snapshot.py` | 3（text(f"...{_TABLE}...")） | 新增 `models/sector_snapshot.py` + `SectorSnapshotRepository` |
| `infrastructure/adapters/industry_data_adapter.py` | 4（db_cursor + f-string 列名 SQL） | `StockORMRepository`（3 个新方法） |

### 新增 ORM 模型
- **`quant.sector_snapshot`**（⚠️ **单数**，不是 snapshots）—— 该表此前无模型，
  表名只以字符串常量形式存在，被 f-string 插进三处 SQL；
  **表名写错只会被 except 吞成"无快照"**（实测这类静默失败很难被发现）。
  有了模型后表名错误会在导入期直接 UndefinedTable。

### `StockORMRepository` 新增
`list_symbols_by_sector` / `get_column_values`（列名走白名单，取值走 ORM 表达式）、
以及 B2-a 的 `list_symbols_by_market` / `update_financial_columns` / `get_latest_financial_update_time`。

---

## 2. 两个**边界语义照搬**的点

1. **`trade_date > today-120` 是严格大于**，不是闭区间。故新增专用
   `get_recent_trading_days`（用 `>`）而**没有**复用既有的 `get_trading_days`（闭区间 `>= / <=`）——
   复用会安静地多算一天，让 `stale_days` 差 1，进而可能把"刚好卡在阈值上"的因子判反。
2. **列名白名单双保险**：`industry_data_adapter` 先校验（`_validated_factor_column`），
   仓储再校验一次（`allowed_columns`）。列名无法参数化，白名单是唯一正解，收口不等于可以省掉。

---

## 3. 测试边界随之下移（不变量不变，且更强）

`tests/test_non_orm_sql_t1_parameterization.py` 原先是"注入一个假 db_cursor，断言 SQL 文本里
没有恶意取值"。适配器改用仓储后，该断言点已不存在，于是改为**监视仓储调用**：

- 恶意取值 `"000001' OR '1'='1"` 必须**原样作为数据**传给仓储（`symbols=[...]`），
  绝不进入任何 SQL 文本；
- 非白名单列名**根本到不了仓储**（更到不了 SQL）；
- 白名单对象必须一并发给仓储做二次校验。

这比原来的"看 SQL 字符串"更贴契约：边界从"SQL 文本长什么样"变成"谁能拿到什么数据"。

---

## 4. 验证证据

- **活体验证（真库）**：
  - `get_recent_trading_days(120)` = 84 个交易日（2026-05-18 ~ 2026-09-11）
  - `get_freshness_by_factor()` = 34 个因子（含 latest_date / coverage）
  - 因子新鲜度门禁整链调用：`ref_date=2026-09-11, factor_count=34, stale=[adx, cci, ma60, mfi14, volatility_20]`，
    返回结构与迁移前一致
  - 板块快照 **round-trip**：`load_snapshot()` 496 行业 / 504 概念 → `save_snapshot()` 同值写回同日（幂等 UPSERT）成功
  - 行业适配器：`get_sector('600519')='制造业'`、`get_sector_stocks('制造业')=3924`、
    `get_sector_factor_values('制造业','roe')=3865` 个值、按 symbols 查 pe 正常；
    恶意因子名被白名单拦下（返回 []，且到不了仓储）
- **回归**：197 passed / 3 skipped
- **闸门**：`--gate` 退出码 0

---

## 5. 指标变化（本轮范围）

| 指标 | B2-a 后 | B2-b 后 | 变化 |
|---|---|---|---|
| cursor_execute | 104 | **100** | −4 |
| core_text_sql | 30 | **25** | −5 |
| fstring_sql | 11 → 10（B2-a） | **7** | −3 |
| session_execute_var（审计桶） | 49 | 50 | +1（新增仓储方法） |

**`infrastructure/jobs/` 全目录清零**（B2-a 达成，本批保持）；本批 3 个文件全部 CLEAN。

---

## 6. 下一步

- **B3**：`application/services` 与 `adapters/inbound/routes` 剩余（`session_service` 13 处最重，
  需新建 agent_session 仓储；`signal_test_log` 9 处；`signals_async` 5 处；`order_service` 3+2 等）
- **B4**：仓储内部 cursor→ORM（`portfolio_repository` 15、`risk_repository` 10、`stock_pool_repository` 10 等）
- **B5**：`read_sql` 5 处单点（`qlib_data_adapter` 3、`core_plan_service` 1、`strategy_evaluation_service` 1）
- 待处理：`tests/test_stock_repository.py` 4 个既有失败（含疑似真缺陷 `get_index_constituents` 未去重）
