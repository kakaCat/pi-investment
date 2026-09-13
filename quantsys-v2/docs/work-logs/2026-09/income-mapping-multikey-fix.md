# 利润表映射缺口修复：中文键 provider + 带后缀代码（2026-09-13，w-32314d00）

上一轮（`financial-overdue-auto-remediation.md`）遗留的真缺口，本轮修掉。

## 1. 缺口一：`_map_income_rows` 只认英文键，中文键的行被整行丢弃

**实测证据**：对同一批标的分别走两条 provider 链路，返回的键完全不同——

- eastmoney_direct / tushare 等：`revenue` / `total_revenue` / `total_cost` / `net_profit` / `basic_eps` / `report_date`
- sina_web / akshare-financial：`营业总收入` / `营业收入` / `营业成本` / `营业利润` / `利润总额` / `净利润` /
  `归属于母公司所有者的净利润` / `基本每股收益` / `稀释每股收益` / `报告日`

原实现第一步就是 `rd = row.get('report_date')` —— **中文键的行在这里直接 continue**，
于是那些标的被记成 `no_data`（实测对 5 只样本跑，`updated=0, no_data=5`，而 provider 明明返回了 100+ 期）。

**修复**（`infrastructure/jobs/financial_statement_update_job.py`）：

1. 新增别名表 `INCOME_KEY_ALIASES` + `_pick(row, field)`：中英文键统一按优先级取值；
2. 报告日支持 `report_date` / `报告日` / `报告期`，`20260630` → `2026-06-30`；
3. 补上 `operating_revenue` / `eps_diluted` 两个此前未落库的字段；
4. 毛利率口径（诚实声明）：provider 给了就用；否则**仅在营业收入与营业成本都存在**时
   按 `(营业收入-营业成本)/营业收入×100` 推导；不与营业总收入混算，缺一留 NULL。

## 2. 缺口二：扫描宇宙里 24/367 的代码带交易所后缀

`_resolve_universe()` 的沪深300成分来自 `StockORMRepository.get_index_constituents`，
形态是 `000999.SZ` / `688981.SH`。这类代码：

- 传给 provider 取不到数据（新浪/东财按 6 位裸码索引）；
- 即使拿到数，落库也会撞 FK（`income_statements.symbol → quant.stocks(symbol)` 是裸码）。

→ 新增 `_normalize_symbol()` 并在 `_dedup_universe()` 里统一归一为裸 6 位码。

**量化**：扫描宇宙 367 只，其中 **32 只完全没有利润表**（含上述 24 只带后缀的）；
利润表总覆盖 364 / 全市场 5857。修复后这两类缺口都会随下次全量跑而收敛。

## 3. 验证

```console
$ ./venv/bin/python -m pytest tests/test_income_mapping_multikey.py -q
8 passed

$ ./venv/bin/python -m pytest tests/test_income_mapping_multikey.py tests/test_financial_auto_rerun.py \
    tests/test_false_success_guard.py tests/test_financial_timeliness_alert.py -q
46 passed
```

用例覆盖：中文键映射全字段、毛利率推导口径、英文键回归不被改坏、缺报告日/缺营收行丢弃、
年报期间类型、缺营业收入时不推导、后缀归一与去重（`000999.SZ`→`000999`）。

中文键名取自本机对 provider 的真实返回（`financial_data_service_adapter` 抓 600519 的实测行），
测试文件里已注明来源。

## 3.1 回归中踩到并修正的一处契约冲突

首次改法把「毛利」限定为「必须同时有营业收入与营业成本才计算」——结果打断了既有契约：
`tests/services/scoring/test_financial_statement_job.py::TestMapIncomeRows::test_quarter_and_year_split`
断言 `gross_profit == revenue - total_cost`（英文键 provider 只给 total_revenue）。

已改为**收入口径回退**：优先用营业收入，缺失时回退营收总额——
既保住旧契约（英文键路径行为不变），又让中文键（金融股营业总收入≠营业收入）按营业收入口径算毛利。
新增用例锁两个方向：缺营业收入时回退推导、两者都存在时营业收入优先。

## 3.2 修完映射后暴露的第二个坑：收入表 upsert 键不齐 → 整批静默丢数据

映射修好后首跑，日志出现：

```console
Error upserting income statements: INSERT value for column income_statements.eps_diluted
is explicitly rendered as a boundparameter in the VALUES clause; a Python-side value or SQL expression is required
```

原因与上一轮 balance 表同源：`upsert_income_statements` 用「非空才放键」构造每行（`{k: r.get(k) for k in cols if ... is not None}`），
而 SQLAlchemy 多行 `INSERT ... VALUES` **要求每行键集合一致**——键一不齐整批失败，函数只 `return 0` + 打 ERROR。

后果是**静默丢数据**：job 看到 `n=0`，却仍把该标的计入 `updated`（首跑实测 `updated: 1, rows: 0`——
又一次"计数假成功"）。已在两处同时修掉：

1. `upsert_income_statements` 键补齐为整齐集合（与 `upsert_balance_sheets` 一致）；
2. `execute()` 改为**只有真的写进去才算 updated**（`n > 0`），否则进 `failed_symbols`。

## 3.3 实盘复测（provider 恢复后，真实输出）

provider 限流约 1 小时后恢复，随即定向补跑「宇宙内没有利润表」的标的：

```console
$ ./venv/bin/python -m infrastructure.jobs.financial_statement_update_job --symbols 300777 600038 600862 ... --periods 4
{'success': True, 'universe': 13, 'updated': 13, 'no_data': 0, 'failed': 0,
 'rows': 759, 'balance_rows': 739, 'balance_updated': 13, 'elapsed_s': 23}

$ # 覆盖与数值（真实数据）
这 13 只现在有利润表的数量: 13
('688032', '2026-06-30', 1780291822.33, 18.0506, -163994466.4, -1.34)
利润表总覆盖: 364 → 377

$ # 扫描宇宙缺口
宇宙规模: 349  仍无利润表: 0        ← 修复前：367 只里 32 只无利润表（含 24 只带后缀）
```

结论：中文键 provider 的标的**此前被整行丢弃、现在能正确落库**（13 只全部一次通过），
带后缀代码归一后不再撞 FK；扫描宇宙内利润表缺口清零。

## 4. 遗留

1. **实盘复测待 provider 恢复**：本轮修复期间的实测显示 provider 已进入限流/封禁状态——
   `get_sina_statements failed: Expecting value: line 1 column 1`（返回非 JSON）、
   `stock_profit_sheet_by_report_em failed: 'NoneType' object is not subscriptable`（东财侧），
   成因为前面全量跑（约 600 标的 × 多源）触发限流。已排期冷却后自动重跑（见下）。
2. **自动重跑链已就位**（上一轮交付）：①逾期自动触发财报落数；
   ②宿主跨日补跑——今晚 20:00 会自动补跑 09-12 失败的 `financial_statements`（用的是修复后的代码）。
3. `debt_ratio` / `current_ratio` 仍留 NULL，需人工确认口径后再补算。
4. **测试基线说明**：财务相关子集现有 7 failed / 6 error 全部与本次改动无关，逐条核实——
   `test_adapters.py::TestGetFinancialData`（`ModuleNotFoundError: quantlib`，环境缺包）、
   `test_income_upsert.py`（fixture 插入 market='SH' 撞 `chk_stocks_market`）、
   `e2e/test_l1_data_pipeline.py::TestFinancialData`（跑在空的 quant_test 库上）、
   `test_portfolio_calculator.py`（现金余额，与财报链路无关）。
   唯一被本次改动打断的 `test_financial_statement_job.py::test_quarter_and_year_split` 已修复（见 3.1）。