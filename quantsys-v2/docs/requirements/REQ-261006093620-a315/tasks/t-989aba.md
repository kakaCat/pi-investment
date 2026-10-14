# t-989aba ③ 退为薄转发 + 打桩点迁移（行为零变化）·研发

> 需求：REQ-261006093620-a315 库表调度（APScheduler）补交易日门：休市日不再开盘前扫描与推送

## 在做什么
③ 退为薄转发 + 打桩点迁移（行为零变化）·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T01:55:21.534Z，窗口 session-35ba53fd-df95-40fa-92df-639ba03cba4d）

研发段完成：③ 的门模块退为纯转发壳，既有测试打桩点已迁到新模块并加证伪锁，28 条全过。

### 完成项

- adapters/inbound/fastapi_app/daily_jobs/gate.py 退为纯转发壳：只 re-export 四个名字，零判定实现
- 测试三处 monkeypatch 目标迁到 application.services.trading_day_gate（被调函数所在模块）
- 新增证伪用例：桩打新模块则转发壳结论随变；再打旧模块则结论不变
- 测试 28 passed（原 26 + 新增证伪 2 条断言），notify-guard egress=0
- 核验 shell 无本地实现：gate.skip_non_trading_day.__module__ = application.services.trading_day_gate
- 文件头打桩纪律注释同步改写，避免后人照旧指引打错模块

### 改动文件

- `adapters/inbound/fastapi_app/daily_jobs/gate.py`
- `tests/test_daily_jobs_trading_day_gate.py`

### 下一步

联调段：核实 ③ 既有调用方（runtime / pipeline）经转发壳行为逐字不变。

---
