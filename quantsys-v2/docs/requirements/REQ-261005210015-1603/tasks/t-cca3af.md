# t-cca3af 新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）·测试

> 需求：REQ-261005210015-1603 修复每日任务完成通知误导（耗时 0.0 分钟 / computed 语义 / 全 NULL 仍报 ✅）

## 在做什么
新增通知层用例（12 条：格式/摘要/语气/空转/降级/失败判定不变式/其他任务逐字不变）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-05T13:24:26.700Z，窗口 session-2bee6968-97b4-45c8-af2d-c3b953e9ff08）

测试段：14 条用例全绿，关键不变式断言齐备

### 完成项

- tests/test_daily_jobs_notify_truthfulness.py → 14 passed（0 failed）
- 关键两条断言均在：find_result_failure 返回 None、_mark_done 收到 success
- notify-guard intercepted=0 egress=0，无未声明外发
- 与全量回归同跑 → 68 passed, 1 skipped

### 下一步

父卡 t-cef289 收尾

---
