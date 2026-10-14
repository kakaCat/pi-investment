# t-dbb9d0 兼容与回滚核验（零 DDL / 既有消费者行为）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
兼容与回滚核验（零 DDL / 既有消费者行为）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_pool_refresh_daily.py -q 全过（既有 TestIsDue 三分支不回归）；git diff --name-only 不含 infrastructure/persistence/migrations/**；notes/compat-rollback.md 落盘且含实际命令输出。

## 实施方案（implementation）
在 tests/test_daily_jobs_trading_day_gate.py 追加兼容判据用例：is_due(job, now, {'status':'skipped','started_at':now}) is False；catchup_due(job, now, has_recent_failure=True) 在排班日 is False；trigger_job 对 skipped 行不返回『今日已有记录』拒绝；find_result_failure({'skipped':True,...}) is None；find_result_failure({'kline_sync':{'status':'success','skipped':12}}) 不因 int 误判（is True 严格布尔）。写 docs/requirements/REQ-261005203907-2b8c/notes/compat-rollback.md：记录 git diff --name-only 中不含 infrastructure/persistence/migrations/** 的核验输出、status 列 text 无 CHECK 约束的核验、以及回滚步骤（撤 3 处 trading_days_only=True 与 pipeline 因子段判定，已产生的 skipped 行无需清理）。

## 上游产出摘要（dependsSummary）
- 宿主接线：_run_job 跳过早退 + 3 任务置位

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-05T13:23:57.070Z，窗口 session-b97ce139-00d0-456f-b147-6b897bcb5369）

兼容与回滚核验交付：零 DDL 已实测证明，skipped 对 7 个既有消费者的行为逐行核对，回滚步骤可照做。

### 完成项

- 新增 TestSkippedRowCompatibility 6 条兼容判据（is_due / catchup_due / trigger_job / find_result_failure / int 防呆）
- 落盘 notes/compat-rollback.md：零 DDL 实测（无迁移改动、status 为 text 无 CHECK、测试库同形）+ 兼容矩阵 + 三步回滚 + 残留风险
- 验证：门用例 27 passed；回归 daily_jobs_bootstrap + pool_refresh_daily → 20 passed
- 子卡链：研发 t-434c63 / 复核 t-e199f4 / 测试 t-0c1cf7 三张全 done

### 改动文件

- `tests/test_daily_jobs_trading_day_gate.py`
- `docs/requirements/REQ-261005203907-2b8c/notes/compat-rollback.md`

### 下一步

下一卡 t-6384c0：回归 + 真实休市日/复市首日观察。

---
