# t-dd129f runtime 接线：通知收敛 + manual 参数 + 超阈值提示 + trigger_job·研发

> 需求：REQ-261006165125-23a9 每日任务空结果不发飞书（no_event/skipped 静默）

## 在做什么
runtime 接线：通知收敛 + manual 参数 + 超阈值提示 + trigger_job·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T09:06:46.577Z，窗口 session-981b7858-34a5-4ea0-88c9-a7e2efb95886）

研发段：runtime 三处通知收敛到唯一判据，新增超阈值提示，trigger_job 传 manual=True。

### 完成项

- _run_job 新增 manual 参数（默认 False），定时路径行为不变
- 删除无条件开始消息，改为 should_send_start 条件式（仅回滚态为真）
- handler 前 arm 超阈值 Timer，finally 取消（阈值内零消息）
- 完成消息改走 should_send_completion + format_completion
- 静默时记 inprocess_job_notify_skipped（可解释性）
- 新增 _arm_running_notice 与 _send_running_notice，回调留在 runtime 保住打桩点
- trigger_job 线程调用传 manual=True（人工触发必有回执）
- 验收①②③全过：四文件 75 passed、host ok、两处 grep 命中
- 计划偏离一：必须同时改 daily_jobs/__init__.py 导出（bootstrap 从包聚合导入，否则 ImportError）
- 计划偏离二：tests/test_daily_jobs_trading_day_gate.py 两条旧断言（开始+完成 2 条）按新口径改为 1 条完成

### 改动文件

- `adapters/inbound/fastapi_app/daily_jobs/runtime.py`
- `adapters/inbound/fastapi_app/daily_jobs/__init__.py`
- `adapters/inbound/fastapi_app/daily_jobs_bootstrap.py`
- `tests/test_daily_jobs_trading_day_gate.py`

### 下一步

复核段：核对分支表与打桩点纪律

---
