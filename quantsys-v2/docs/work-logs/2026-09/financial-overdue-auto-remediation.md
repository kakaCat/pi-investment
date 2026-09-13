# 财报超期闭环：补上资产负债表写入通道 + 逾期自动重跑（2026-09-13，w-32314d00）

## 0. 用户指令与执行结果

用户要求：①手动执行 `python -m infrastructure.jobs.financial_data_update_job --report-date 20260630`；②「需要自动重跑」。

**① 手动执行（真实输出）**：

```console
$ ./venv/bin/python -m infrastructure.jobs.financial_data_update_job --report-date 20260630
业绩报表获取成功: 11449 行 (报告期 20260630)
财务数据更新完成: {'success': True, 'report_date': '20260630', 'fetched': 11449, 'universe': 5857,
  'updated': 5510, 'skipped': 347, 'failed': 0,
  'columns': ['roe', 'gross_margin', 'net_profit_growth', 'revenue_growth'], 'elapsed_s': 8}
```

⚠️ **但它治不了这条告警**——实测：跑完后再执行时效性检查，仍然 `latest_report_date=2026-03-31, is_overdue=true`。原因：

- 该 job 写的是 **`quant.stocks` 的指标列**（roe/毛利率/增长率）；
- 而时效性巡检与数据契约读的是 **`quant.balance_sheets` 的最新 `report_date`**；
- 更关键的是：**`quant.balance_sheets` 当时根本没有写入通道**（`FinancialORMRepository` 只有 `upsert_income_statements`，没有 balance 版本）——表停在 2026-03-31（1200 行，历史 bulk 导入），告警每天响、数据永远修不动。

## 1. 真正的修复：补写入通道 + 落 Q2 数据

1. **`adapters/outbound/repositories/financial_repository.py`** 新增 `upsert_balance_sheets()`
   （按 `symbol+report_date+period_type` 冲突更新；该唯一约束线上已存在）。
   踩坑留档：多行 `pg_insert` 要求**每行键集合一致**——首版按“非空才放键”构造，5 只里 2 只因缺
   `non_current_liabilities` 整批失败（`explicitly rendered as a boundparameter`），现统一补齐键。
2. **`infrastructure/jobs/financial_statement_update_job.py`**：
   - 新增 `_map_balance_rows()`（中文键 → balance_sheets 列；`报告日 20260630` → `2026-06-30`；12 月 = `Y`，其余 `Q`；关键金额全空的行丢弃）；
   - 在同一次 provider 调用里**同时落利润表与资产负债表**（adapter 本就一次返回 income+balance+cashflow，此前 balance 只是被丢弃）；
   - `success` 口径改为“利润表或资产负债表任一落库即成功”（原来只看利润表，会把“只写了资产负债表”的批次误判 failed）；
   - 诚实声明：**不计算** `debt_ratio`/`current_ratio`（单位口径未统一，留 NULL）。
3. **落数据（实测）**：

```console
$ ./venv/bin/python -m infrastructure.jobs.financial_statement_update_job --symbols 600519 000858 601899 600036 000001 --periods 4
{'success': True, 'balance_rows': 512, 'balance_updated': 5, ...}
# balance_sheets 2026-06-30 出现首批真实数据：
('000858', 184999362605.88, 64054972918.06, 120944389687.82)
('600519', 309050784569.31, 46954432394.95, 262096352174.36)
```

全量（池成员+watchlist+沪深300）后台补数已启动（`nohup ... /tmp/fin_stmt_update.log`）。

## 2. 告警闭环（实测转绿）

```console
$ ./venv/bin/python -c "from infrastructure.jobs.financial_timeliness_check_job import execute; print(execute())"
{'success': True, 'check_date': '2026-09-13', 'latest_report_date': '2026-06-30',
 'expected_report_date': '2026-06-30', 'is_overdue': False, 'days_overdue': 0, 'alert_sent': False}

# 线上（重启后进程内）触发调度任务 318：
财报时效性检查开始
✅ 财报数据时效性正常
检查结果: 预期=2026-06-30, 实际=2026-06-30, 超期=False
```

→ 09:00 的每日“财报超期”告警终止；Q2 资产负债表数据补齐。

## 3. 「需要自动重跑」——两条自动补救链路

### 3.1 逾期即自动补数（`financial_timeliness_check_job._maybe_auto_remediate`）

- 检查发现逾期 → **自动触发**财报落库（利润表+资产负债表），**后台线程**执行，不阻塞调度线程；
- 每天最多一次：进程内 20h 冷却 + 查 `quant.inprocess_job_runs` 当天是否已有记录（宿主当天跑过就不重复）；
- 告警正文里带上补救状态（`自动重跑: 已自动触发…`），当日复测仍逾期才继续告警；
- 显式 `dry_run` / `auto_remediate=False` 可关闭。

### 3.2 宿主跨日补跑（`daily_jobs_bootstrap.catchup_due` + `_recent_failed_run`）

原行为：`is_due` 只认“今天是不是它的排班日”→ **周六任务周六失败要等下周六**（一周空窗，
financial_statements 09-12 卡死就是这个形态）。
现行为：非排班日 + 已过该任务执行时刻 + 近 3 天内有 failed 记录 → **当天补跑一次**；
跑完即写当天记录，天然每天最多一次；排班日仍交给 `is_due`（含 2h 失败重试），不双跑。

## 4. 验证

```console
$ ./venv/bin/python -m pytest tests/test_financial_auto_rerun.py -q
15 passed
```

（覆盖：报告日/期间类型归一、空行丢弃、缺字段不整批失败、不计算比率、
触发一次/冷却/宿主当天已跑/显式关闭、跨日补跑四种边界。）

## 5. 遗留

1. **`_map_income_rows` 与 provider 中文键不匹配**：实测 600519 等标的的 provider 行用中文键（`营业总收入`），
   而映射函数读 `revenue`/`total_revenue` → 这些标的被记成 `no_data`（利润表面向前 329 只来自其它 provider 的英文键样式）。
   本次未改（不在本任务范围），但它是“利润表覆盖只有 364 只”的一个真实原因，建议后续统一键口径。
2. **debt_ratio / current_ratio 仍为 NULL**：单位口径未统一，需要人工确认后再补算。
3. 全量补数任务在后台运行中（约 600 标的，受 provider 限速与部分接口报错影响，耗时较长）。