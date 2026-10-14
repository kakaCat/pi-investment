# t-0c1cf7 兼容与回滚核验（零 DDL / 既有消费者行为）·测试

> 需求：REQ-261005203907-2b8c DailyJobs 宿主接入交易日门：休市日不再开火（pool_daily_refresh 等）

## 在做什么
兼容与回滚核验（零 DDL / 既有消费者行为）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
./venv/bin/python -m pytest tests/test_daily_jobs_bootstrap.py tests/test_pool_refresh_daily.py -q → 20 passed；git diff --name-only 不含 infrastructure/persistence/migrations/**；notes/compat-rollback.md 落盘且含实际命令输出。注：卡上原写的 pnpm test / npx tsc 属 JS 栈模板，本仓为 Python，已按等价命令修订。

---
## 汇报 1（2026-10-05T13:23:50.446Z，窗口 session-b97ce139-00d0-456f-b147-6b897bcb5369）

测试阶段：三条验收全过（20 passed、零 DDL、记录落盘），门用例 27 passed。

### 完成项

- ① pytest tests/test_daily_jobs_bootstrap.py tests/test_pool_refresh_daily.py -q → 20 passed
- ② git diff --name-only 无 infrastructure/persistence/migrations/** 改动（零 DDL 合格）
- ③ notes/compat-rollback.md 已落盘，含 status 列 text + CHECK 0 行 + 测试库同形 + 回滚三步的真实输出
- ④ 门用例总数 27 passed（含本卡新增 6 条兼容判据）
- 通知守卫：全部运行 intercepted=0 egress=0

### 下一步

父卡收尾；随后 t-6384c0 回归与真实观察。

---
