# t-0b1d7e 改写被新口径推翻的 2 条既有断言 + 相邻回归·研发

> 需求：REQ-261006165125-23a9 每日任务空结果不发飞书（no_event/skipped 静默）

## 在做什么
改写被新口径推翻的 2 条既有断言 + 相邻回归·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T09:08:42.339Z，窗口 session-981b7858-34a5-4ea0-88c9-a7e2efb95886）

研发段：两条旧口径断言按新口径改写，旧行为作为回滚态用例保留。

### 完成项

- test_zero_output_uses_warning_title 拆为默认态静默与开关态 ⚠️ 两条
- 默认态断言零消息且台账 status 仍 success
- 开关态断言两条消息且完成消息为 ⚠️ 无有效产出语气
- test_elapsed_line_rendered_by_formatter 改用有产出结果构造
- 该文件 30 passed（含 notify_guard），旧断言仅剩开关态 1 处
- 阶段模板的 vitest 命令不适用本仓（Python 栈），改用 pytest

### 改动文件

- `tests/test_daily_jobs_notify_truthfulness.py`

### 下一步

复核段：确认改写后的用例仍守住原意（台账 success、耗时格式）

---
