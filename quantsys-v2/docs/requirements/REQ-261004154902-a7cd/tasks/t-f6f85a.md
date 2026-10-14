# t-f6f85a cron 时刻口径、misfire 语义与「被跳过」落库·测试

> 需求：REQ-261004154902-a7cd V13 策略实现缺陷排查（因子/模型/调仓/止损全链路取证）

## 在做什么
cron 时刻口径、misfire 语义与「被跳过」落库·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-04T08:25:39.523Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

测试子卡：22 条用例锁住宽限语义与本地 14:30，另加一次真库端到端证明。

### 完成项

- venv/bin/python -m pytest tests/test_scheduler_misfire_semantics.py -q → 22 passed
- 覆盖：宽限语义（NULL / 零 / 负 / 脏值 / 显式值）、job_id 解析、本地 14:30 回归锁、装载器把 NULL 传成空宽限、MISSED 事件落库、记账失败不外抛、仓储行字段与「不许动下次触发时间」
- 另跑一次端到端证明（测试库，含临时数据清理）：missed 行成功落库并可查回
- 零数据库依赖的单元用例 + 一次显式清理的集成证明，测试期 notify-guard 零外发

### 改动文件

- `tests/test_scheduler_misfire_semantics.py`

---
