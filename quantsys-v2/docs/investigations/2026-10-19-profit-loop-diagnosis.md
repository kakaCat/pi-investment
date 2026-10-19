# 盈亏闭环断点诊断（2026-10-19）

> 流程 fix-perf-loop 任务 1 产物。问题：`quant.strategy_performance` 0 行，
> "信号→订单→成交→盈亏→经验积累"学习链空转。
> （同目录已有先例：2026-10-16-watch-messaging-chaos.md）

## 链路逐段核对结论

| 段 | 状态 | 证据 |
|---|---|---|
| ① 信号生成 `signal_generate_buy` | ✅ 今日修复 | 9-13 误删策略致断流 5 周，今日恢复 60 条/日 |
| ② 信号推送 Agent | ✅ 机制在 | orchestrator MARKET_OPEN 推送 + `signal_execution_daily` 兜底（7:30）；今日 pushed=false 只因 7:30 跑时当日信号尚未生成（9:00 生成），明日可验证 |
| ③ 订单 `simulation_order` | ⚠️ **断点 B1** | 50 行 `signal_id` **全空**——订单不关联信号，平仓后无法归因到策略/信号 |
| ④ 成交 `simulation_trades` | ⚠️ 半通 | 172 行中仅 50 带 order_id；SELL 77 行中仅 27 填了 `realized_pnl`（`qs_trading/application/services/trade_service.py:256` 有计算，但未全量覆盖） |
| ⑤ 盈亏落库 `strategy_performance` | ❌ **断点 C（主断点）** | `StrategyPerformanceORMRepository.create()` **全仓零调用方** |
| ⑥ 经验积累 `ExperienceAccumulator` | ❌ 空转 | 读空表，样本永远 <10，不产出推荐等级 |

## 断点 C 根因（考古实锤）

`strategy_performance` 的写入方是 `_update_signal_tracking()`，寄生在 **legacy 订单栈**
（`trade_service` 成交撮合路径，`quant.orders` 表）。该表 2026-08-25 归档后，legacy 栈
于 **2026-09-14（commit 9bb04e65d，REQ-24e15d B4-c2）整体删除**——删除本身正确
（对着归档表写 SQL 必抛错），但盈亏写入路径随之陪葬，**未在存活的模拟交易路径
（simulation_order/simulation_trades，qs_trading）上重新接线**。

即：闭环不是"没设计"，是 9-14 重构时**写端被带走、没人补挂**。

## 修复方向（任务 2 输入）

在存活的卖出成交路径上补一个挂钩：SELL 成交（含 realized_pnl 计算处，
`qs_trading` trade_service / simulation 执行路径）→ 组装
`strategy_name / symbol / signal_date / entry_price / exit_price / pnl_pct /
holding_days / source='paper'` → 调 `StrategyPerformanceORMRepository.create()`。

依赖断点 B1 的修复（订单带 signal_id，才能填 strategy_name/signal_date 归因）；
signal_id 缺失时降级：按 account+symbol 归因到持仓来源，strategy_name 标
`unattributed` 如实落库，不伪造归因。
