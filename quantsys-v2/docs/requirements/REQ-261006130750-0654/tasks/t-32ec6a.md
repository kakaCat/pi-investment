# t-32ec6a 给 IntradayMonitor.check() 加权威日级门·研发

> 需求：REQ-261006130750-0654 休市日盘中空转收口：IntradayMonitor 与编排线程接入交易日门

## 在做什么
给 IntradayMonitor.check() 加权威日级门·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T05:20:30.015Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

研发阶段完成：盘中监控的权威日级门已落地，等价测试口径 34 passed。

### 完成项

- 交付物：application/services/intraday_monitor.py（check() 权威日级门、常量、docstring 指向）
- 对应测试：tests/api/test_orchestrator_trading_day_gate.py 12 passed + tests/test_market_session_policy.py 28 passed = 34 passed
- git diff --stat 摘要：intraday_monitor.py 40 行变更（+新门与常量/docstring）
- 如实报出模板不符：本卡 acceptance 写的是 npx vitest run（JS 模板），本仓是 Python（无 package.json）
- 替代口径：以 pytest 等价执行同一意图（跑改动涉及的用例并全绿）
- 实现要点复述：门在时段判定之后，skip 时直接返回，不构造引擎、不读写持仓

### 改动文件

- `application/services/intraday_monitor.py`

### 下一步

复核子卡按设计逐条对照本改动（FR-1/FR-3/FR-5/FR-6），测试子卡复跑全套并留通知零外发证据。

---
