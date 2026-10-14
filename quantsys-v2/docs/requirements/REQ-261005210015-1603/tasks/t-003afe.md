# t-003afe 新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）·研发

> 需求：REQ-261005210015-1603 修复每日任务完成通知误导（耗时 0.0 分钟 / computed 语义 / 全 NULL 仍报 ✅）

## 在做什么
新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-05T13:24:26.463Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

研发段：通知层 14 条用例落地并跑通

### 完成项

- 新增 tests/test_daily_jobs_notify_truthfulness.py，共 14 条用例覆盖设计清单的 12 类断言
- 桩全部打在 runtime 模块（_send_feishu / _mark_running / _mark_done），不碰生产库与真通道
- 用例数据用 2026-10-05 生产真实计数形态（5 行全 NULL）
- 跑测结果 14 passed，notify-guard intercepted=0 egress=0

### 改动文件

- `tests/test_daily_jobs_notify_truthfulness.py`

### 下一步

复核段核对断言与设计清单的对应

---
