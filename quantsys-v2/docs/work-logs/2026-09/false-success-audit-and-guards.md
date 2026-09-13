# 假成功治理：查出「记 success 的真失败」，并让异常抛出来（2026-09-13，w-32314d00）

> 触发：scheduler_tasks.last_status 三天都记 success（异常被业务层吞掉）——与指数事件
> （81d8f56c「跑成功但数据旧」）同源的假成功形态，只有 error 事件台账能露出。

## 1. 查出来的假成功（真实台账证据）

审计口径：**存库状态 = success，但返回值里带失败标记**。两条执行路径重扫结果：

**A. 进程内宿主 quant.inprocess_job_runs（近 30 天，49 条 run）**

| 日期 | job | 存库状态 | 结果里的真实情况 |
|---|---|---|---|
| 09-03 / 09-04 / 09-07 / 09-08 / 09-09 | evening_pipeline | success | kline_sync: column "updated_at" does not exist（全市场 K 线同步失败，连续 5 天） |
| 09-05 | financial_statements | success | handler reported success=false |
| 09-12 起 | financial_statements | **running（12h+）** | 进程重启后无人收尾 → 既不被重跑也不被告警（永久隐形） |

**B. APScheduler 路径 quant.scheduler_runs（近 14 天，356 条 run）**

7 条 success 的 run 结果带失败标记：

- task 323 / 301：`'MarketPerceptionService' object has no attribute 'regime_daily'`（4 次）
- task 258：`'function' object has no attribute 'list_pools'`
- task 232：`质量检查失败: name 'datetime' is not defined`

**C. scheduler_tasks.last_status=success 但近 14 天有 failed run**（慢性失败被「最后一次成功」掩盖）：
task 232（11 failed / 10 success）、308（9/12）、318（3/12）、258、333、271、320、334、268、269。

## 2. 根因：三个执行入口，只有两个做了结果契约校验

| 入口 | 失败判定 | 状态 |
|---|---|---|
| infrastructure/scheduler/job_executor.py（APScheduler 定时） | classify_job_result（2026-09-10 修） | 已有 |
| adapters/inbound/.../scheduler_webhook.py（webhook 派发） | 同上（共用） | 已有 |
| infrastructure/scheduler/scheduler.py::run_task（手动触发 / run_due_tasks） | **无**，只看有没有抛异常 | 本次修 |
| adapters/inbound/.../daily_jobs_bootstrap.py::_run_job（进程内宿主） | **无**，只看有没有抛异常 | 本次修 |

外加两个隐形窗口：

- classify_job_result 只判**顶层**——失败藏在嵌套 dict（如 kline_sync.status=error）时漏判，evening_pipeline 五天假成功正是这个形态；
- 宿主 is_due 只查**当天**的 run 行、_job_failure_watch 只看 failed → **僵死在 running 的行永久隐形**（financial_statements 09-12 实证）。

## 3. 落地改动

1. **job_executor.py::find_result_failure(result)**（新增，失败判定口径唯一来源）：classify_job_result 的嵌套版——最多下钻 2 层、只下钻「结果形状」的 dict（含 success/status 键，避免把 failed_jobs 这类诊断清单误判）、显式 skipped=True 不算失败（非交易日/幂等跳过是正常语义）。
2. **scheduler.py::run_task**：返回失败态 → complete_run(success=False, error=...) + status='failed' 返回 + ERROR 日志（此前无条件 success=True）。
3. **daily_jobs_bootstrap._run_job**：handler 返回失败态 → 记 failed + 飞书失败告警（不再发「每日任务完成」）。
4. **daily_jobs_bootstrap._reap_orphan_runs()**（新增）：宿主启动时把早于 5 分钟仍 running 的行判死（error=宿主重启导致中断（孤儿 running 行，进程已不在））→ 进入失败巡检与看门狗视野。
5. **financial_timeliness_check_job**：告警未送达 → raise AlertDeliveryError（job 判 failed，scheduler_tasks.last_error 写明原因）——「职责是告警而没告成」不再算成功。

## 4. 验证

```console
$ ./venv/bin/python -m pytest tests/test_false_success_guard.py tests/test_daily_jobs_bootstrap.py tests/test_financial_timeliness_alert.py -q
39 passed

$ ./venv/bin/python -m pytest tests/ -q -k "scheduler or daily_jobs or job_executor or job_registry or inprocess"
239 passed, 5 skipped, 5562 deselected
```

**线上实证（重启后进程内）**：

```console
$ launchctl kickstart -k gui/501/com.pi-investment.v2-api     # 新代码必须重启才生效
$ grep orphan logs/launchd-stdout.log | tail -2
{"job": "financial_statements", "date": "2026-09-12", "event": "inprocess_job_orphan_reaped", ...}
{"count": 1, "event": "inprocess_job_orphans_reaped", ...}

# 台账：卡了 12h 的 running 行被收尾，并生成错误事件（可见性闭环）
financial_statements 2026-09-12: status=failed, started_at=09-12 23:00:41,
  finished_at=09-13 11:37:02, error=宿主重启导致中断（孤儿 running 行，进程已不在）
→ public.error_events c0e69791-...（inprocess_job_orphan_reaped）
```

## 4.1 后续修正：孤儿判死的日志级别（2026-09-13 事件 c0e69791）

`_reap_orphan_runs` 首版**按行打 ERROR**，被日志采集器收成 error_events——每次实例重启只要存在孤儿行，
就生成一张需要人工闭环的卡片，把“已经处理好的事”变成待办噪声（实证：11:37:02 判死
`financial_statements@2026-09-12` 即产生 `c0e69791`；而该 run 的事故记录本来就已经落在
`quant.inprocess_job_runs`（status=failed + error 原因）并可被 `_job_failure_watch` 巡检）。

改为**一条聚合 warning**（`count` + `jobs=["<job>@<date>"]` 明细），事故留痕不变、待办噪声消失。
实测（13:41:03 重启时对合成孤儿行 `zz-orphan-probe`）：

```console
{"count": 1, "jobs": ["zz-orphan-probe@2026-09-13"], "event": "inprocess_job_orphans_reaped",
 "logger": "adapters.inbound.fastapi_app.daily_jobs_bootstrap", "level": "warning", ...}
# 同一时刻 error_events 新增 orphan 类事件：0 条
# 孤儿行同一毫秒被置 failed：宿主重启导致中断（孤儿 running 行，进程已不在）
```

并补回归测试 `test_orphan_reap_logs_single_warning_not_error` 锁死日志级别（不得退回按行 error）。
探针行验证后已删除；`pytest tests/test_false_success_guard.py` 16 passed。

## 5. 遗留（需人工决策，未擅自扩大范围）

1. **财报数据仍超期 6 天**（预期报告期 2026-06-30，balance_sheets 最新 2026-03-31）。现在 financial_statements 的失败可见了，但不会自动补跑（周六任务）。建议人工确认后执行 python -m infrastructure.jobs.financial_statement_update_job。
2. **历史假成功不追溯改写**：inprocess_job_runs / scheduler_runs 的历史行保持原样（反映当时的判定逻辑）；如需统计口径修正应另立数据修复任务。
3. **其余「静默吞异常」的 handler**（AST 扫描已列）都至少打了 WARNING/ERROR，属可观测而非隐形；扫描 FALSE_SUCCESS=0，故本轮未改。
