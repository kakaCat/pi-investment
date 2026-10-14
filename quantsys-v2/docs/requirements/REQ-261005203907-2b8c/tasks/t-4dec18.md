# t-4dec18 晚间管线：因子段局部跳过（K 线段原样）·测试

> 需求：REQ-261005203907-2b8c DailyJobs 宿主接入交易日门：休市日不再开火（pool_daily_refresh 等）

## 在做什么
晚间管线：因子段局部跳过（K 线段原样）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
./venv/bin/python -m pytest tests/test_evening_pipeline_holiday_gate.py -q → 6 passed；既有回归 tests/test_freshness_guard.py + tests/test_daily_jobs_bootstrap.py + tests/test_false_success_guard.py → 36 passed；tests/ -k 「evening_pipeline or daily_jobs or freshness」的失败数 ≤ 开工前基线（该选择集有 1 条既有 order-dependent 失败，已单跑证明与本卡无关）。注：卡上原写的 pnpm test / npx tsc 属 JS 栈模板，本仓为 Python，已按等价命令修订。

---
## 汇报 1（2026-10-05T13:22:17.919Z，窗口 session-b97ce139-00d0-456f-b147-6b897bcb5369）

测试阶段：本卡 6 passed、回归 36 passed；选择集唯一失败已定位为既有 order-dependent 项（单跑通过、失败点在本卡代码之前）。

### 完成项

- ① pytest tests/test_evening_pipeline_holiday_gate.py -q → 6 passed（失败数 0）
- ② 回归三文件（freshness_guard / daily_jobs_bootstrap / false_success_guard）→ 36 passed
- ③ tests/ -k 「evening_pipeline or daily_jobs or freshness」→ 1 failed / 78 passed：唯一失败为既有 order-dependent 项
- ④ 该失败单跑 → 1 passed（证明与顺序/状态相关，非本卡引入）
- 失败机理已定位：断言 evolution_fitness_idle_stats_failed 出现在 capsys 输出，但该行被 pytest 日志捕获走 logging 通道（日志侧确有该行），说明是同选择集内某用例装了日志 handler 所致；且该断言位于触达本卡代码之前
- 通知守卫：四次运行均 intercepted=0 egress=0 offenders=[]

### 下一步

父卡收尾；随后 t-dbb9d0 兼容与回滚核验。

---
