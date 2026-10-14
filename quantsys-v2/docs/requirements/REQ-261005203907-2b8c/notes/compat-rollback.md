# 兼容与回滚核验（REQ-261005203907-2b8c · t-dbb9d0）

> 设计依据：[`../design/interfaces.md`](../design/interfaces.md) §5（兼容矩阵）、
> [`../design/data-model.md`](../design/data-model.md) §2/§4（零 DDL 与回滚）。
> 本文件是**实测记录**：命令与输出逐字粘贴，不是"应该没问题"。

## 1. 结论（一句话）

本需求**零 DDL、零迁移、零回填**：唯一的数据面变化是既有 `text` 列的取值集合多一个
`'skipped'`；回滚 = 撤掉 3 处标志与 1 处判定，**已产生的 `skipped` 行无需清理**
（没有任何消费者把它当异常态）。

## 2. 零 DDL 核验

### 2.1 变更文件里没有迁移脚本

```console
$ git diff --name-only | grep "infrastructure/persistence/migrations/"
（空）→ 无迁移脚本改动
```

### 2.2 `status` 列是 `text`，且无 CHECK 约束（故新增取值不需要 DDL）

```console
$ psql -d quant_investment -c "select column_name, data_type, is_nullable, column_default
  from information_schema.columns where table_schema='quant'
  and table_name='inprocess_job_runs' and column_name='status';"
 column_name | data_type | is_nullable | column_default
-------------+-----------+-------------+----------------
 status      | text      | NO          |
(1 row)

$ psql -d quant_investment -c "select conname, pg_get_constraintdef(oid) from pg_constraint
  where conrelid='quant.inprocess_job_runs'::regclass and contype='c';"
 conname | pg_get_constraintdef
---------+----------------------
(0 rows)
```

### 2.3 ORM 侧同样是自由文本（无枚举校验）

`infrastructure/persistence/orm/models/job_run.py:40`

```python
status = Column(Text, nullable=False, comment='任务级状态')
```

### 2.4 测试库与生产库同形（表结构漂移门禁不受影响）

```console
$ psql -d quant_test -c "select column_name, data_type, is_nullable from information_schema.columns
  where table_schema='quant' and table_name='inprocess_job_runs' order by ordinal_position;"
 column_name |        data_type         | is_nullable
-------------+--------------------------+-------------
 job_id      | text                     | NO
 run_date    | date                     | NO
 status      | text                     | NO
 started_at  | timestamp with time zone | NO
 finished_at | timestamp with time zone | YES
 result      | jsonb                    | YES
 error       | text                     | YES
(7 rows)
```

## 3. 既有消费者行为核验（可跑断言）

`tests/test_daily_jobs_trading_day_gate.py::TestSkippedRowCompatibility`（6 条，全部通过）

```console
$ ./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q
27 passed in 0.76s
notify-guard intercepted=0 egress=0 offenders=[]
```

| 消费者 | 断言 | 结果 |
|---|---|---|
| `is_due` | `{'status':'skipped'}` → `False`（当天不重跑） | ✅ |
| `is_due` 三分支 | `success` / `running` / `failed` 语义未被挤掉 | ✅ |
| `catchup_due` | 排班日恒 `False`；非排班日只由 `failed` 决定（`skipped` 不参与） | ✅ |
| `trigger_job` | 对 `skipped` 不返回「今日已有记录」；对 `success` 仍拒绝 | ✅ |
| `find_result_failure` | 顶层 `skipped=True` → `None`（不算失败） | ✅ |
| 命名撞车防呆 | `kline_sync.skipped=12`（int 跳过只数）不被读成布尔跳过 | ✅ |

**回滚后是否还需要这些断言？** 需要——它们是"新增状态值不改既有判定"的回归锁，
与门是否启用无关（撤标志后断言照样成立）。

## 4. 回滚步骤（三步，无需数据清理）

1. **撤标志**：`adapters/inbound/fastapi_app/daily_jobs/registry.py` 里去掉
   `pool_daily_refresh` / `chip_distribution` / `evolution_fitness` 三行的
   `trading_days_only=True`（或整体把 `JobDef.trading_days_only` 默认值改动回退）。
2. **撤局部判定**：`adapters/inbound/fastapi_app/daily_jobs/pipeline.py` 的
   `_job_evening_pipeline` 因子段恢复为无条件 `handle_factor_compute({'max_symbols': 6000})`。
3. **重启服务**：`launchctl kickstart -k gui/501/com.pi-investment.v2-api`
   （改的是宿主线程里的代码，必须在进程内重新加载）。

**不需要做的事**：
- 不需要回填/清理 `quant.inprocess_job_runs` 里的 `skipped` 行——`is_due` 对它落 `False`
  （当天不再跑）、`catchup_due` 只看 failed、`_reap_orphan_runs` 只看 running、
  `_job_failure_watch` 只看 failed。
- 不需要改任何表、跑任何迁移、清任何缓存。
- 不需要改 APScheduler 路径（本次未触碰）。

## 5. 残留风险（如实登记）

- `quant.inprocess_job_runs.status` 从此多一个取值，**监控/看板若对状态做白名单匹配**，
  需要把 `skipped` 纳入展示口径（本仓内已核：无白名单匹配；`list_today_runs()` 只透传）。
- 本核验未覆盖"跨进程/跨环境的旧版本读取新行"（不存在多版本并存的部署形态）。
