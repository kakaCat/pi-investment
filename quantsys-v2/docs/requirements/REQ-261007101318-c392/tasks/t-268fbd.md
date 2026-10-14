# t-268fbd FR-1 休市日闸门：tick() 日级收敛到 TradingDayGuard（回填）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
FR-1 休市日闸门：tick() 日级收敛到 TradingDayGuard（回填）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
跑 pytest tests/services/test_watch_engine_trading_day_gate.py -q 得 4 passed；其中必须断言：休市日（冻结 2026-10-07 10:00 且注入 is_trading_day_fn=False）时 tick()==[] 且 repo.calls==0（不判定而非判定后丢弃）、交易日盘中照常产出 1 条事件且 level 非空、交易日 16:00 仍返回 []、未注入时 _resolve_trading_day(2026-10-07) 为 (False, 含 holiday)。

## 实施方案（implementation）
application/services/watch_engine/engine.py：新增 _resolve_trading_day(day) 作为 tick() 与 run_forever() 的唯一日级入口（默认 TradingDayGuard.check，支持 is_trading_day_fn/trading_day_verdict_fn 注入）；tick() 前置改为「日级 + 时段」双闸门，未开市时调用 _log_market_closed() 按日去重留痕后 return []（不取规则、不评估、不落库、不外发）；判定异常一律保守判非交易日。新增 tests/services/test_watch_engine_trading_day_gate.py 锁定四条行为。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-07T05:43:11.774Z，窗口 session-c7b5b1ee-dc6a-497a-86d0-a3f34e787544）

FR-1 父卡收尾：休市日闸门已落地、复核无偏离、4 条回归锁全过，生产已生效。

### 完成项

- 子卡三段全 done：研发 t-dcdeb1 / 复核 t-b33b0b / 测试 t-e58107
- 研发段：engine.py 落地 _resolve_trading_day 单一入口（+85/-9）
- 复核段：入口复用恰好 2 处、判定异常保守返回、留痕去重，结论无偏离
- 测试段：4 条回归锁逐条 PASSED（休市日零事件/交易日照常/盘后仍拦/默认闸门认识节假日）
- 生产已生效：2026-10-07 12:50 服务重启加载新闸门，休市日不再产出事件

### 改动文件

- `application/services/watch_engine/engine.py`
- `tests/services/test_watch_engine_trading_day_gate.py`

### 下一步

父卡关账；进入 t2（FR-2 名称兜底）子卡链

---
