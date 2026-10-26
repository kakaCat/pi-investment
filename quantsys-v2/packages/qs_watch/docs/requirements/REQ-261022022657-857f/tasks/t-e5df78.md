# t-e5df78 扩 metrics 读数并收口回归·研发

> 需求：REQ-261022022657-857f 交易闭环补口：反思唤醒 + 减仓批次收敛 + 消息→离场

## 在做什么
扩 metrics 读数并收口回归·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run tests/` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-21T18:38:50.522Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

metrics 扩展完成：两个当日计数、可注入、失败降级 null，3 例测试绿。

### 完成项

- watch_metrics_async.py 新增 _default_counters：news_todos_today（evidence.source=news 当日计数）与 reflection_woken_today（scheduler_runs 汇总 woken）
- build_metrics 支持 counts_provider 注入；取数失败 → null（不用 0 冒充）+ degraded 记录
- tests/plan/test_metrics_ext.py 3 例（注入可见/未知为 null/provider 失败降级）

### 改动文件

- `docs/requirements/REQ-261022022657-857f/tasks/t-e5df78.md`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/watch_metrics_async.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_metrics_ext.py`

---
