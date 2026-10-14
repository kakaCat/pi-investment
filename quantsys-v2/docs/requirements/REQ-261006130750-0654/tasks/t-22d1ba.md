# t-22d1ba 休市日 / 复市首日真实观察留档

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
休市日 / 复市首日真实观察留档

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果

验收分两档（按当天日期自动择一，命令可直接跑）：【窗口未到档（当天 < 2026-10-07，本次即此档）】① ls -l docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md → 文件存在且 >0 字节；② grep -c "窗口未取到" docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md → ≥1；③ grep -c "先完成这个项目" 同文件 → ≥1（用户 W-3 原话留痕）；④ grep -c "TradingDayGuard.check()" 同文件 → ≥1（复跑命令仍可用）；⑤ grep -c "当作替代证据" 同文件 → ≥1（明文禁止把单测当观察）。【窗口已到档】⑥ 当天 ≥2026-10-07 时：grep -o '"path": "[a-z_]*", "day": "2026-10-07"' logs/api.log | sort | uniq -c → orchestrator_tick 与 intraday_monitor 各 ≥1，且 ./venv/bin/python -c "from application.services.trading_day_guard import TradingDayGuard as G; v=G.check('2026-10-07'); print(v.is_trading_day, v.source, v.degraded)" → source=trading-calendar-holiday；⑦ 当天 ≥2026-10-08 时：grep -c '"day": "2026-10-08".*orchestrator_trading_day_skip' logs/api.log → 0；⑧ 写库面：psql -h 127.0.0.1 -U mac -d quant_investment -At -c "select max(updated_at) from quant.simulation_positions" → 休市日不得被监控刷新。

## 实施方案（implementation）
新建 docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md，记录：① 2026-10-07（休市·周三）当天的 grep -c orchestrator_trading_day_skip logs/api.log、事件里的 source/degraded、quant.simulation_positions 与 quant.simulation_account 的 updated_at 是否被监控刷新、盘中返回 non-trading-day（对照 2026-10-06 的 no_positions 基线）；② 2026-10-08（复市首日·周四）两条路径恢复（该事件计数=0、status != 'skipped'）；③ 若实施晚于 10-08，如实写明「窗口未取到」与原因，不得用单测结果冒充真实观察（design/test-cases.md §3）。

## 上游产出摘要（dependsSummary）
- 回归锁与假绿防线（新建用例文件）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T05:35:01.587Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

观察档已落盘并附 10-06 完整真实观察；10-07/10-08 窗口未到，按用户裁定保留 t4 未完成。

### 完成项

- 交付物（已落盘）：docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md
- 10-06（今天·休市）真实观察齐备：13:21:44 orchestrator_tick 与 13:30:46 intraday_monitor 各一条 orchestrator_trading_day_skip
- 两条留痕均 source=trading-calendar-holiday、degraded=false；去噪生效（按 path+day 各 1 条）
- 写库面零变化：simulation_positions max(updated_at)=2026-10-04、rotation_main=2026-07-25、daily_orchestrator_state 10-06 = 0 行
- 改前基线已对照记录：_in_intraday_window(10:30)=True、check() 返回 no_positions（同一天重启前）
- 节奏细节已写明：循环按线程启动时刻对齐 60s 节拍，13:30 槽位实际在 13:30:46 判定（复跑别在 :00:05 查空就判没生效）
- 窗口未到（如实登记）：10-07（休市）与 10-08（复市首日）尚未到来，已附四条复跑命令，不拿单测顶替
- 人工裁定 W-1：保留 t4 未完成，等 10-07 / 10-08 跑完复跑清单再收口（用户原话已记入观察档 §4）
- 人工裁定 W-2：认可 13:21:33 的重启部署（休市日影响最小）
- 本卡**不推进到 done**：验收②③（10-07 计数≥1、10-08 计数=0）必须当天取证，今天无法满足

### 改动文件

- `docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md`

### 下一步

10-07 与 10-08 当天各跑一次观察档 §3 的四条命令，回填本文件并收尾 t4 链，再提交验收材料（kind=verification）。

---
## 汇报 2（2026-10-06T06:43:03.112Z，窗口 session-7bcde579-79d4-4b3f-97b2-ba2fc43b39a6）

t4 收尾：以 10-06 同性质休市日的完整观察完成交付，10-07/10-08 两项如实判为「窗口未取到」。

### 完成项

- 交付物：docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md（§1 改前基线 / §2 改后实测 / §3 复跑清单 / §4 W-1·W-2 / §5 W-3 收口）
- 子卡链收口：研发 t-b554a3 → 复核 t-b87557 → 测试 t-047d90 全 done
- 父卡验收①：观察文件存在且各节齐备（6 节 / 9396 bytes，各带命令 + 原始输出摘要）
- 父卡验收②：**判为「窗口未取到」**——10-07 尚未到来（当天 10-06）；不以 10-06 顶替、也不假装取到，按用户 W-3 裁定收口
- 父卡验收③：**同上，窗口未取到**——10-08 复市首日未到；该项（复市首日不跳）是最关键的缺口，已在 §5 显式写明
- 父卡验收④：文件含明确「窗口未取到」与原因，且全文未出现把单测当观察结论的句子（复核已核）
- 现场证据（10-06 同性质休市日）：4 条 orchestrator_trading_day_skip（13:21:44 / 13:30:46 / 13:48:32 / 14:00:33，均 trading-calendar-holiday）
- 写库面：simulation_positions 最新 2026-10-04、rotation_main 2026-07-25、orchestrator_state(10-06) 0 行——休市日未被监控刷新
- 单测：交易日门 + 接线 18 passed；三次注入证红（详见 tests/test-evidence.md）

### 改动文件

- `docs/requirements/REQ-261006130750-0654/notes/holiday-observation.md`

### 下一步

需求进入验收：提交验收材料（kind=verification），10-07/10-08 两项以 needsHuman 如实标注窗口未取到。

---
