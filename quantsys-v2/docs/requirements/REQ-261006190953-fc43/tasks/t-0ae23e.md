# t-0ae23e 接线两处写入入口：非交易日拒写并留痕 refused/skipped

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
接线两处写入入口：非交易日拒写并留痕 refused/skipped

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_equity_snapshot_trading_day_gate.py -q 全过，且至少断言：① 休市日 snapshot_all_accounts 返回 written=0 且 refused=n（n=活跃账户数）并带五键 trading_day；② 交易日返回 written=n 且 refused=0；③ take_daily_snapshot 在休市日返回 skipped 结构且不抛异常（snap=None 路径被覆盖）；④ EquitySnapshotJob.run 休市日 skipped=True，reason 与“未收盘”可区分；⑤ 该日 K 线存在但日历判休市时仍跳过（证明 _has_bar 已不是交易日判据）；⑥ 打桩 trading_day_gate.skip_non_trading_day 后断言两条路径都被调用过（防各自另写判定）。

## 实施方案（implementation）
改 application/services/evolution/daily_snapshot_service.py：snapshot_all_accounts 汇总 refused（被闸门拒写的账户数）与 trading_day 五键，written 不计被拒账户；EquitySnapshotJob._has_bar 由“交易日代理判据”降级为“是否已收盘”辅助判据，交易日判定交给闸门，reason 文案区分“非交易日”与“未收盘”。改 application/trading/paper_trading_engine.py：take_daily_snapshot 处理闸门返回 None（不得 AttributeError），返回 {'skipped': True, 'reason': ..., 'trading_day_source': ..., 'trading_day': 五键}。改 tests/test_daily_jobs_trading_day_gate.py 补 EquitySnapshotJob 休市日用例；扩展 tests/test_equity_snapshot_trading_day_gate.py 的服务路径部分。验证：./venv/bin/python -m pytest tests/test_daily_jobs_trading_day_gate.py tests/test_equity_snapshot_trading_day_gate.py -q 全过。

## 上游产出摘要（dependsSummary）
- 给净值仓储加唯一写入闸门，并让日收益基准按交易日回退

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T11:59:21.753Z，窗口 session-0a409569-b1b3-44b9-b67b-2f9a9e3d16f8）

卡 C 完工：两处写入入口不再假设一定写成功，闸门结论（refused/skipped + 五键注解）都带得出来；期间修掉回填计数虚高与一处测试卫生问题

### 完成项

- snapshot_all_accounts 带出 written / refused / skipped 与五键 trading_day，被拒不计入 written
- EquitySnapshotJob 先问门再问收盘，两段跳过文案可区分
- take_daily_snapshot 处理 snap=None，返回 skipped 结构，非交易日不刷账户表
- 新增 6 例任务入口用例 + 8 例服务/引擎路径用例（含真仓储联动与双路径同判据）
- 额外修 DEV-6：回填被拒的日子不再算作已写
- 额外修测试卫生：evolution 快照测试打桩常真门，去掉真实 provider 依赖（约 4s → 0.54s）
- 子卡链四段全过；验收 52 passed；邻域回归 245 passed 零失败

### 改动文件

- `application/services/evolution/daily_snapshot_service.py`
- `application/trading/paper_trading_engine.py`
- `tests/test_daily_jobs_trading_day_gate.py`
- `tests/test_equity_snapshot_trading_day_gate.py`
- `tests/services/evolution/test_daily_snapshot_service.py`
- `application/services/nav_series.py`
- `adapters/outbound/repositories/trading_calendar_repository.py`
- `adapters/outbound/repositories/simulation_repository.py`

### 下一步

批 2 剩 D（读取端 window/nav_coverage）、F（存量清理迁移）、G（常驻巡检判据）三张。

---
