# t-bdfaae 宿主接线：_run_job 跳过早退 + 3 任务置位·测试

> 需求：REQ-261005203907-2b8c DailyJobs 宿主接入交易日门：休市日不再开火（pool_daily_refresh 等）

## 在做什么
宿主接线：_run_job 跳过早退 + 3 任务置位·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py -q → 21 passed；再加 -k 「skip or registry or degraded」选择器版本；既有回归 tests/test_daily_jobs_bootstrap.py + tests/test_false_success_guard.py + tests/test_pool_refresh_daily.py + tests/test_freshness_guard.py → 41 passed；tests/ -k 「daily_jobs or pool_refresh or job_failure」→ 62 passed（失败数 ≤ 开工前基线）。注：卡上原写的 pnpm test / npx tsc 属 JS 栈模板，本仓为 Python，已按等价命令修订。

---
## 汇报 1（2026-10-05T13:18:15.700Z，窗口 session-b97ce139-00d0-456f-b147-6b897bcb5369）

测试阶段：四条验收命令全绿（21 / 13 / 41 / 62 passed），失败数 0，通知守卫零外发。

### 完成项

- ① pytest tests/test_daily_jobs_trading_day_gate.py -q → 21 passed（失败数 0）
- ② 同文件 -k 「skip or registry or degraded」→ 13 passed / 8 deselected
- ③ 四文件回归（daily_jobs_bootstrap / false_success_guard / pool_refresh_daily / freshness_guard）→ 41 passed
- ④ tests/ -k 「daily_jobs or pool_refresh or job_failure」→ 62 passed / 6454 deselected（失败数 ≤ 开工前基线）
- 四次运行通知守卫均 intercepted=0 egress=0 offenders=[]

### 下一步

父卡收尾后进 t-588729（晚间管线因子段）。

---
