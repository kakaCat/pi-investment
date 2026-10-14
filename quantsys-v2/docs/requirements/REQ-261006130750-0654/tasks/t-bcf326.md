# t-bcf326 回归锁与假绿防线（新建用例文件）·测试

> 需求：REQ-261006130750-0654 休市日盘中空转收口：IntradayMonitor 与编排线程接入交易日门

## 在做什么
回归锁与假绿防线（新建用例文件）·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
`pnpm test` → 失败数 ≤ 开工前基线；`npx tsc --noEmit` → 错误数 ≤ 基线（贴汇总输出）

---
## 汇报 1（2026-10-06T05:26:34.650Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

测试阶段完成：98 passed、两次注入逐条证红并复原、通知零外发、失败数不高于基线。

### 完成项

- 父卡验收①：tests/api/test_orchestrator_trading_day_gate.py → 12 passed（≥12 条）
- 父卡验收②：新增 + 同族五套 → 98 passed（orchestrator_bootstrap / market_session_policy / trading_window_guard / scheduler_trading_day_gate / daily_jobs_trading_day_gate）
- 父卡验收③（阶段内重跑）：注入 degraded 也跳过 → 2 红（intraday_degraded_is_fail_open、gate_own_exception_is_fail_open），复原后全绿
- 父卡验收④（阶段内重跑·按卡原文）：拿 check(2026-10-07) 未来日当休市日判据 → 1 红，报错原文 assert future == trading-calendar-holiday（正是 T5 要锁的语义），复原后全绿
- 复原校验：两次注入后 shasum 与注入前逐一相同；两文件 grep INJECTED 计数均为 0
- 父卡验收⑤：notify-guard intercepted=0 egress=0 offenders=[]
- 基线对照：改前同命令失败数 0 → 改后 0（不高于基线）
- 如实报出：本卡 acceptance 的 pnpm test / npx tsc 是 JS 栈模板，本仓无 package.json，改用 pytest 等价口径

### 下一步

父卡 t3 收尾（受 60s 节流，稍后关）；随后 t4 真实观察留档（10-06 已取基线 + 13:30 槽位）。

---
