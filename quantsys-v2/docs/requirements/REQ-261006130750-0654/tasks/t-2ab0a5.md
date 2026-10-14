# t-2ab0a5 编排循环加 A 层日历预过滤与跳过去噪·研发

> 需求：REQ-261006130750-0654 休市日盘中空转收口：IntradayMonitor 与编排线程接入交易日门

## 在做什么
编排循环加 A 层日历预过滤与跳过去噪·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`npx vitest run <本卡改动涉及的测试文件>` → 全绿；并附 `git diff --stat` 摘要

---
## 汇报 1（2026-10-06T05:22:24.591Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

研发阶段完成：编排循环装上 A 层日级预过滤与跳过去噪；既有两条接线用例按 FR-4 补最小桩后 6 passed。

### 完成项

- 交付物：adapters/inbound/fastapi_app/orchestrator_bootstrap.py 新增 _should_run_today 与 _LAST_SKIP_LOG、两个受控 path 常量，_monitor_loop 两分支各插一次判定
- 顺带最小改动：tests/api/test_orchestrator_bootstrap.py 给两条既有用例补「今天是交易日」桩（requirement FR-4 已预先授权）
- 补桩理由：不补则用例成败由真实日历决定（今天正是休市日）；用例原意（循环接线、线程存活）不变
- 探针（真日历，不桩）：_should_run_today(2026-10-06 12:30) → False / trading-calendar-holiday / degraded=False
- 探针：同函数传 2026-09-30 → True / trading-calendar；去噪表 _LAST_SKIP_LOG = {orchestrator_tick: 2026-10-06}
- 静态：grep -c should_skip orchestrator_bootstrap.py → 4（≥2）；新增逻辑零 weekday() 命中（仅窗口函数里既有那处保留）
- 测试：tests/api/test_orchestrator_bootstrap.py → 6 passed
- git diff --stat：orchestrator_bootstrap.py 76 行；tests/api/test_orchestrator_bootstrap.py 6 行
- 如实报出模板不符：本卡 acceptance 是 npx vitest 模板，本仓 Python 无 package.json，改用 pytest 等价口径

### 改动文件

- `adapters/inbound/fastapi_app/orchestrator_bootstrap.py`
- `tests/api/test_orchestrator_bootstrap.py`

### 下一步

复核子卡重点看：日级门是否真的只拦自动排班、钱路调用次数在交易日/降级日是否不变、去噪是否只按 (path, day)。

---
