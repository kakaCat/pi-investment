# REQ-261006130750-0654 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：v2 剩下的第 ④ 条日级判据路径已接上唯一真源交易日门。\n代码：编排循环加 A 层预过滤（休市日零调用 + 按 path/day 去噪留痕）；IntradayMonitor.check() 首部加 B 层权威门（休市日不构造引擎、不读写持仓、返回 non-trading-day），旁路调用也拦得住；门 fail-open（降级照跑）、窗口函数语义与钱路 fail-closed 一行未改；零 DDL、零迁移、零开关。\n证据：12 条新用例 + 三次注入证红；同族 98 passed；现场 4 条真实跳过留痕（10-06 休市日）；写库面零变化。\n如实报出：① 10-07 与 10-08 两个日历窗口**未取到**（当天为 10-06），按用户 W-3 裁定以 10-06 同性质休市日观察收口，请人判定是否接受；② 复核发现 scheduler_tasks_runtime.handle_intraday_monitor 会把 skipped 包成 success（未来接线的假成功雷）；③ resume_from_breakpoint 仍 fail-closed，日历覆盖断档时休市日仍会跑（属取舍残留，修它需动日历自动补刷）。

## 1. 验收列表

### v1-1 · 给 IntradayMonitor.check() 加权威日级门

**验收内容**：【给 IntradayMonitor.check() 加权威日级门】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q -k 'intraday_holiday or intraday_trading_day' → 全过
2. ② ./venv/bin/python -c 「from application.services.intraday_monitor import IntradayMonitor
3. from datetime import datetime
4. print(IntradayMonitor().check(now=datetime(2026,10,6,10,30)))」→ 输出 status='skipped'、reason='non-trading-day'、trading_day.source='trading-calendar-holiday'
5. ③ 同一探针传 20:00 → reason='not trading time'（不是 non-trading-day）
6. ④ ./venv/bin/python -m pytest tests/test_market_session_policy.py -q → 全过
7. ⑤ grep -c force application/services/intraday_monitor.py → 0

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：真库探针 check(now=2026-10-06 10:30) → skipped/non-trading-day/source=trading-calendar-holiday；20:00 → 仍 not trading time（严格增量）；失败注入 → ok=False 且不抛；test_market_session_policy.py 22 passed

**验收状态**：✓ 通过

---

### v1-2 · 编排循环加 A 层日历预过滤与跳过去噪

**验收内容**：【编排循环加 A 层日历预过滤与跳过去噪】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/api/test_orchestrator_bootstrap.py -q → 全过（窗口契约不变）
2. ② ./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q -k orchestrator → 全过（休市日零调用/交易日照调）
3. ③ grep -c should_skip adapters/inbound/fastapi_app/orchestrator_bootstrap.py → ≥2
4. ④ 同一 path+day 连调两次 _should_run_today → 跳过日志仅 1 条（用例断言）
5. ⑤ 运行期 notify-guard intercepted=N egress=0

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：_should_run_today(2026-10-06 12:30)=False / (2026-09-30)=True；周六窗口 False ⇒ 门不被调用；同 path+day 只 1 条日志；grep should_skip=4；orchestrator_bootstrap 6 passed

**验收状态**：✓ 通过

---

### v1-3 · 回归锁与假绿防线（新建用例文件）

**验收内容**：【回归锁与假绿防线（新建用例文件）】验收

**操作步骤**：
1. ① ./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py -q → 全过（≥12 条）
2. ② ./venv/bin/python -m pytest tests/api/test_orchestrator_bootstrap.py tests/test_market_session_policy.py tests/test_trading_window_guard.py tests/test_scheduler_trading_day_gate.py tests/test_daily_jobs_trading_day_gate.py -q → 全过（同族三条路径不被带坏）
3. ③ 反向注入「degraded 也跳过」→ 至少 1 条用例变红，复原后全绿
4. ④ 反向注入「用 check('2026-10-07') 当休市日判据」→ 变红，复原后全绿
5. ⑤ 会话末 notify-guard 输出 egress=0

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：新增 12 条用例全过；三次注入逐条证红并复原（shasum 一致、INJECT 残留 0）；静态红线可红；notify-guard egress=0

**验收状态**：✓ 通过

---

### v1-4 · 休市日 / 复市首日真实观察留档

**验收内容**：【休市日 / 复市首日真实观察留档】验收

**操作步骤**：
1. 验收分两档（按当天日期自动择一，命令可直接跑）：【窗口未到档（当天 < 2026-10-07，本次即此档）】① ls -l docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md → 文件存在且 >0 字节
2. ② grep -c "窗口未取到" docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md → ≥1
3. ③ grep -c "先完成这个项目" 同文件 → ≥1（用户 W-3 原话留痕）
4. ④ grep -c "TradingDayGuard.check()" 同文件 → ≥1（复跑命令仍可用）
5. ⑤ grep -c "当作替代证据" 同文件 → ≥1（明文禁止把单测当观察）。【窗口已到档】⑥ 当天 ≥2026-10-07 时：grep -o '"path": "[a-z_]*", "day": "2026-10-07"' logs/api.log | sort | uniq -c → orchestrator_tick 与 intraday_monitor 各 ≥1，且 ./venv/bin/python -c "from application.services.trading_day_guard import TradingDayGuard as G
6. v=G.check('2026-10-07')
7. print(v.is_trading_day, v.source, v.degraded)" → source=trading-calendar-holiday
8. ⑦ 当天 ≥2026-10-08 时：grep -c '"day": "2026-10-08".*orchestrator_trading_day_skip' logs/api.log → 0
9. ⑧ 写库面：psql -h 127.0.0.1 -U mac -d quant_investment -At -c "select max(updated_at) from quant.simulation_positions" → 休市日不得被监控刷新。

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：窗口未到档五条全绿：① 文件 9396 bytes 存在；② grep -c 窗口未取到 = 1（≥1）；③ grep -c 先完成这个项目 = 1（≥1）；④ grep -c TradingDayGuard.check() = 1（≥1）；⑤ grep -c 当作替代证据 = 1（≥1）。日期判定：2026-10-06 → 窗口未到（10-07/10-08 均 False）

**验收状态**：✓ 通过

---

### v1-5 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：需求级判定 1/2/3/4/6 全绿（单测、降级 fail-open、反例锁、既有回归、静态）；判定 5（10-07 真实观察）与 10-08 复市首日实证属窗口未取到，已如实登记并在验收材料中标出

**验收状态**：✓ 通过

---

### v1-6 · 需求级验收

**验收内容**：与裁定对照（逐条说明如何落实）

**操作步骤**：
1. 与裁定对照（逐条说明如何落实）

**预期结果**：上述步骤全部执行成功，输出与「验收内容」描述一致即通过

**实际结果**：D-1（治理报告立项；以实测取代替「27 次」口径）：已兑现——台账复现不出该数字并登记为待对齐项，未据此扩范围；D-2（范围 A：只收口 v2 剩余盘中路径）：已兑现——只动 orchestrator_bootstrap 与 IntradayMonitor 两处 + 用例；agent-ts 与 data_validator 报错均未入范围（后者另立项 1fdf，已归档）

**验收状态**：✓ 通过

---

## 2. 测试报告

- $ ./venv/bin/python -m pytest tests/api/test_orchestrator_trading_day_gate.py tests/api/test_orchestrator_bootstrap.py -q → 18 passed；notify-guard intercepted=0 egress=0 offenders=[]
- 同族回归：新增 + orchestrator_bootstrap + market_session_policy + trading_window_guard + scheduler_trading_day_gate + daily_jobs_trading_day_gate → 98 passed
- 三次注入证红（均复原、shasum 一致、INJECT 残留 0）：degraded 也跳过 → 2 红；判错的一天 → 2 红；B 层门改成 if False → 2 红
- 现场留痕（10-06 同性质休市日，实测 4 条）：13:21:44 orchestrator_tick、13:30:46 intraday_monitor、13:48:32 orchestrator_tick（重启清内存去噪键）、14:00:33 intraday_monitor；均 source=trading-calendar-holiday、degraded=false
- 写库面零变化：quant.simulation_positions 最新 2026-10-04 16:49:36、simulation_account(rotation_main) 2026-07-25、daily_orchestrator_state(2026-10-06) 0 行
- 行为对照：_in_intraday_window(2026-10-06 10:30)=True（时段层放行）但 check() 由 no_positions 变为 non-trading-day；编排 tick 由每分钟空转调用变为零调用
- 静态：grep should_skip orchestrator_bootstrap.py → 4（≥2）；intraday_monitor 零 weekday()；两文件零直查交易日历
- 观察档（含 W-1/W-2/W-3 三条裁定与窗口未取到登记）：docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md
- 测试证据（T1–T12 矩阵 + 注入表 + covers 16 张卡）：docs/requirements/REQ-261006130750-0654/tests/test-evidence.md
- 独立复核报告（F1 第二调用方假成功 / F2 日历断档残留 / 三条低影响观察）：docs/requirements/REQ-261006130750-0654/reviews/code-review.md
- 部署记录：13:21:33 与 13:48:28 两次 launchctl kickstart -k（休市日重启影响最小，用户已认可）

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 给 IntradayMonitor.check() 加权威日级门 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 14:43 |
| v1-2 | 编排循环加 A 层日历预过滤与跳过去噪 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 14:43 |
| v1-3 | 回归锁与假绿防线（新建用例文件） | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 14:43 |
| v1-4 | 休市日 / 复市首日真实观察留档 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 14:43 |
| v1-5 | 需求级验收 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 14:43 |
| v1-6 | 需求级验收 | ✓ 通过 | human/session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6 | 2026-10-06 14:44 |
