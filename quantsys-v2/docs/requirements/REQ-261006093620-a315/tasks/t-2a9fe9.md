# t-2a9fe9 人工触发改投一次性 manual=True job·测试

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
人工触发改投一次性 manual=True job·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T02:01:48.317Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

测试段完成：t6 验收 13 条与合并回归 81 条全过，读数已留档。

### 完成项

- 本卡验收：test_apscheduler_service.py 13 passed
- 合并回归 81 passed，与 t5 后持平未降
- 读数补入 notes/acceptance-run.md 的 t6 小节（含一次口径自我更正）
- notify-guard intercepted=0 egress=0

### 改动文件

- `docs/requirements/REQ-261006093620-a315/notes/acceptance-run.md`

### 下一步

t7（t-54d79f）：巡检口径同步 should_have_run 与 watchdog。

---
