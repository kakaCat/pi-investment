# t-e8c8e2 e2e 手动触发用例不再执行真实 handler·研发

> 需求：REQ-261003150739-b98d 修复 pytest 向真实通知渠道发消息（打桩点漂移）

## 在做什么
e2e 手动触发用例不再执行真实 handler·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-03T07:13:03.918Z，窗口 session-06404018-404f-4c74-b75d-0e786a1bb5d7）

研发段完成：用例改为打桩 runtime._run_job 并断言派发。

### 完成项

- 把真 handler 执行换成记录器
- 新增 5s 内派发的等待断言

### 改动文件

- `tests/e2e/test_daily_orchestrator.py`

---
