# t-bcbe54 编排循环加 A 层日历预过滤与跳过去噪

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
编排循环加 A 层日历预过滤与跳过去噪

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① ./venv/bin/python -m pytest tests/api/test_orchestrator_bootstrap.py -q → 全过（窗口契约不变）；② ./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q -k orchestrator → 全过（休市日零调用/交易日照调）；③ grep -c should_skip adapters/inbound/fastapi_app/orchestrator_bootstrap.py → ≥2；④ 同一 path+day 连调两次 _should_run_today → 跳过日志仅 1 条（用例断言）；⑤ 运行期 notify-guard intercepted=N egress=0

## 实施方案（implementation）
改 adapters/inbound/fastapi_app/orchestrator_bootstrap.py：① 新增模块级 _LAST_SKIP_LOG: Dict[str, str] 与 _should_run_today(now, *, path) -> Tuple[bool, Dict]（内部只调 from application.services.trading_day_gate import should_skip，策略固定 'trading-days'；返回 (not skip, info)；skip 为真时按 (path, day) 去噪记一条 logger.info('orchestrator_trading_day_skip', path=…, day=…, is_trading_day=…, source=…, degraded=…, reason=…)；函数内不得出现 weekday()、不得直查 trading_calendar、不得抛异常）；② _monitor_loop 两个分支内各插一次判定，path 取 'orchestrator_tick' / 'intraday_monitor'，仅当 run 为真才调 monitor_jobs.daily_orchestrator_tick() / monitor_jobs.intraday_monitor_check()；既有 try/except 与 finally close_session()、窗口函数 _in_orchestrator_window / _in_intraday_window 原样不动。依据 design/interfaces.md §2。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T05:24:32.081Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

t2 收尾：编排循环 A 层门交付并已部署生效，五项验收全绿，休市日 13:21:44 起产生真实跳过留痕。

### 完成项

- 交付物：adapters/inbound/fastapi_app/orchestrator_bootstrap.py 的 A 层日级预过滤（_should_run_today + _LAST_SKIP_LOG + 两个受控 path）
- 配套最小改动：tests/api/test_orchestrator_bootstrap.py 两条既有用例补「今天是交易日」桩（requirement FR-4 预先授权）
- 子卡链收口：研发 t-2ab0a5 → 复核 t-011042 → 测试 t-67db61 三张全 done
- 父卡验收①：tests/api/test_orchestrator_bootstrap.py → 6 passed（窗口契约不变）
- 父卡验收②：tests/api/test_orchestrator_trading_day_gate.py -k orchestrator → 12 passed（休市日零调用/交易日照调）
- 父卡验收③：grep -c should_skip orchestrator_bootstrap.py → 4（≥2）
- 父卡验收④：同 path+day 连调两次只留 1 条日志（用例 T10 断言）
- 父卡验收⑤：notify-guard intercepted=0 egress=0
- 部署后真实留痕：2026-10-06T13:21:44 logs/api.log 出现 orchestrator_trading_day_skip（path=orchestrator_tick、source=trading-calendar-holiday、degraded=false）
- 复核独立结论：周六不受影响（窗口先 False，门不被调用）、交易日照跑、无第二份判定来源

### 改动文件

- `adapters/inbound/fastapi_app/orchestrator_bootstrap.py`
- `tests/api/test_orchestrator_bootstrap.py`

### 下一步

t3 用例卡（回归锁与假绿防线）——依赖已满足，开工；13:30 盘中槽位留痕并入 t4 观察。

---
