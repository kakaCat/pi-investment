# t-ea86ce 回归锁与假绿防线（新建用例文件）·研发

> 需求：REQ-261006130750-0654 休市日盘中空转收口：IntradayMonitor 与编排线程接入交易日门

## 在做什么
回归锁与假绿防线（新建用例文件）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T05:25:46.376Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

研发阶段完成：交易日门回归锁 12 条用例落盘并全绿，全部日期用例桩定、不依赖机器日期与测试库日历。

### 完成项

- 交付物：tests/api/test_orchestrator_trading_day_gate.py（新建，12 条用例）
- 对应测试：./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py → 12 passed
- 覆盖对照 design/test-cases.md T1-T13：逐条落地（T13 通知零外发并入 T1/T3 断言 agent_service 未被调用）
- 打桩点：统一桩在 application.services.trading_day_gate.TradingDayGuard（tdg.TradingDayGuard）
- 确定性设计：日期用例一律桩定结论，不依赖机器当天是否交易日、也不依赖测试库日历被填过
- T5 未来日反例锁改为动态取「今天 +400 天后的首个工作日」，避免写死日期随时间失效
- git diff --stat：新文件未跟踪（?? quants-v2/tests/api/...），12 条用例、无对既有文件的改动
- 如实报出模板不符：本卡 acceptance 的 npx vitest 不适用本仓 Python 栈，改用 pytest 等价口径

### 改动文件

- `tests/api/test_orchestrator_trading_day_gate.py`

### 下一步

复核子卡独立审：用例是否真能红、有无假绿（尤其休市日零调用的断言是否会被「循环没跑」蒙混）。

---
