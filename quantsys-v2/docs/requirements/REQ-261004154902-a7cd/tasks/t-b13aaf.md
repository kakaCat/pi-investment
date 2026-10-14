# t-b13aaf 策略日检如实上报并修回通知方法

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
策略日检如实上报并修回通知方法

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
venv/bin/python -m pytest tests/live_trading/test_daily_check_contract.py tests/test_v13_scheduler.py -q 全过；用例含：①因子返回空 → ok=False 且 reason='factor_empty'；②model.predict 抛错 → ok=False reason='rebalance_failed'；③hasattr(SimulationTrader,'_send_rebalance_notification') is True；④通知抛错时 ok 仍为 True 且 detail['notify_error'] 非空；⑤周末 → reason='not_trading_day' 且上层 status='skipped'。

## 实施方案（implementation）
改 live_trading/simulation_trader.py：run_daily_check 消费 self.rebalance(today) 的返回值，成功与否如实映射为 RunOutcome；rebalance 的 except 分支改为 logger.error(exc_info=True) + FailureSink.report_failure；把误缩进在 if __name__ == '__main__': 块内的 _send_rebalance_notification 与 _format_rebalance_content 移回类体，并保证通知失败不改变调仓成功判定（进 detail['notify_error']）。改 application/services/strategy_service.py 的 daily_check 为三态映射（success/skipped/failed）。改 tests/test_v13_scheduler.py：把三处 return True/False 的假绿灯改成真断言。新增 tests/live_trading/test_daily_check_contract.py。

## 上游产出摘要（dependsSummary）
- 新增结果契约与失败可见性出口

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-04T08:12:02.641Z，窗口 session-8eb5b6f2-0d2a-44d3-bfca-878578124cec）

主卡：V13 日检从「永远报 success」变成如实三态，并把那个让每次调仓都崩在最后一步的通知方法修回类里。

### 完成项

- 主卡目标达成：V13 日检的「干了没干、成了没成」现在如实可读（success / skipped / failed 三态）
- 修掉真 bug：调仓通知方法缩进错位导致每次调仓崩在最后一步（钱已下单、错被吞、通知从未发出）
- 失败主动外发：调仓失败、因子上空、模型未加载、止损失败都会经统一出口外发
- 通知是副作用：发送失败只留痕，不把成功的调仓判成失败
- 清理三条假绿灯（打印 ❌ 却 passed），并补 9 条新契约用例
- 回归面 1082 passed / 18 skipped / 0 failed；卡内 16 passed；零真实外发

### 改动文件

- `live_trading/simulation_trader.py`
- `application/services/strategy_service.py`
- `tests/live_trading/test_daily_check_contract.py`
- `tests/live_trading/test_trading_day_judge.py`
- `tests/test_v13_scheduler.py`

---
