# a4 · 设计未覆盖缺口清单

> 需求：REQ-261006010812-cd19（t4）｜ 判定口径：设计**声称覆盖**的落点见 [`a2-impl-matrix.md`](a2-impl-matrix.md)；
> 本文件只收「设计**没管住**、但仍在风险中」的项，以及「设计了但载体不成立」的项。
> 取证时刻：2026-10-06 09:4x（CST）。

## 缺口清单（8 条；风险等级 ∈ {高, 中, 低}）

| # | 缺口 | 证据 | 影响面 | 风险 |
|---|---|---|---|---|
| G-1 | **V13 风险检查链路整条是坏的、且未排班**（设计未覆盖：a7cd 现状取证 E15 列了它，但 `design.md` 全文未提，拆分计划 14 张卡无对应卡） | [L2] `infrastructure/jobs/risk_check_job.py:56,81,101,142,169` 五处硬编码 `account_name='default'`；`:118,121` 读 `trade.direction`；[L1] `grep -rn "def get_trades_since\|def list_positions\|def count_rebalances" adapters/ application/ infrastructure/` → 唯一命中是 `adapters/inbound/fastapi_app/routes/p2_batch2_async.py:79 async def list_positions(`（**无关的 FastAPI 路由函数**）；在 risk_check_job 实际实例化的仓储类 `adapters/outbound/repositories/simulation_repository.py:50 SimulationORMRepository` 内三方法 **0 命中**（该类有的是 `get_all_positions` / `get_pending_orders` 等）→ 一跑就 AttributeError；[L3] `select command,count(*) from quant.scheduler_tasks group by 1` → 无 `v13_risk_check` 行 | V13 的组合级风险（回撤/集中度/流动性）无人计算；出现问题时没有任何一条自动链路会报 | **高** |
| G-2 | **V13 预测验证链路同病**：自造指标 + 未排班（设计未覆盖） | [L2] `infrastructure/jobs/verification_job.py:146,167,215` 同样硬编码 `default` 与不存在的方法；`:194 predicted_return = 0.12  # TODO: 从实际数据读取`；[L3] 无 `v13_verification` 任务行 | 「模型准不准」这个决定要不要继续用 V13 的问题，**没有可信答案**；空跑分支还返回 `completed` | **高** |
| G-3 | **盘中没有任何 V13 止损**（设计未覆盖：a7cd 现状取证 E16 列了它，设计 §7 只做了日检与挂单撮合） | [L2] `application/services/intraday_monitor.py:77` `PaperTradingEngine(account_name='rotation_main')` 写死；[L2] `domain/watch/services/rule_guard.py:31-39` `guard_account_applicable` 对策略账户抛 `WatchRuleNotApplicable`（注释自陈「策略账户的交易由策略引擎执行，与盯盘无关」） | V13 持仓只剩「每日 14:30 日检」一道止损；盘中急跌无人处置（8/24 起多次出现 −10% 以上持仓） | **高** |
| G-4 | **回滚路径与判据载体都不在版本控制内**（设计已覆盖 §11，但载体不成立） | [L1] **E-2**：`git status --porcelain` → `?? quantsys-v2/application/observability/run_outcome.py`（新件未跟踪）；`git ls-files --error-unmatch application/observability/run_outcome.py` → `error: pathspec … did not match any file(s) known to git`；受改 20 文件为 `M`、5 新模块 `??`；**整个需求目录** `?? quantsys-v2/docs/requirements/REQ-261004154902-a7cd/`；[L1] **E-3**：`ls tools/check_trading_day_judgment.py` → 不存在（C2 实跑报 `[Errno 2] No such file or directory`）；[L1] **E-4**：`git check-ignore -v tools/check_should_have_run.py` → `.gitignore:85:check_*.py`（另两个 check 工具同规则命中） | 换机器 / 干净 clone / 误删工作区 → 设计与实现**同时消失**，且没有可 `revert` 的提交（`design.md:289` 声明的回滚方式不成立） | **高** |
| G-5 | **盘点器与交易日历没打通**：休市日的排班缺失被报成「漏跑」（设计未覆盖） | [L1] `tools/check_should_have_run.py` 实跑 → `漏跑：1`（`daily-strategy-validation`，cron `0 21 * * 1-5`，应跑 `2026-10-05 21:00`，实际 `2026-10-02 21:02`），而 `2026-10-05` 是休市日（[L3] `quant.trading_calendar` 无该日行）；[L2] 判定链路 `application/services/should_have_run.py` 按 cron 工作日语义推演，未接 `trading_day_resolver` | 每次长假都会产出**假漏跑告警**（或反过来掩盖真漏跑）；与 §3「休市不开火」的口径不一致，值班会重新学会忽略告警 | **中** |
| G-6 | **「missed 可见」只到代码、未到证据**（设计已覆盖 §4/§8，未收口） | [L2] `infrastructure/scheduler/apscheduler_service.py:120-145 _on_job_missed` 写 `record_missed_run`；[L3] `select status,count(*) from quant.scheduler_runs group by 1` → `success 2999 / failed 155 / cancelled 1`，**无 missed 行**；[L3] 启用 11 条任务中仅 **1 条**宽限为 NULL（设计只把 v13 日检与"挂单撮合"列为关键任务，而后者从未建行 → G-1/M-12） | 「任务被跳过」这条判据从未被验证过；真发生 misfire 时未必可见 | **中** |
| G-7 | **声明失真在 v13 之外仍在**（设计 §5 只收了 v13 三参数） | [L1] `live_trading/configs/strategies/v14.yaml:20 factors_count: 75` vs `live_trading/models/v14_p0_valid_factors.json` 实测 **78**、`v14_p0_model.json` 特征 **78**；[L2] `live_trading/config_simulation.yaml:22,62,85` 注释仍写「v13 链路生效 8」，而 `v13.yaml:40 top_n: 5` | 读配置的人会得到与生效值相反的结论；`check_strategy_config_effective.py` 只查 v13 三参数，**不会**报出这类失真 | **中** |
| G-8 | **假绿灯的「结构门禁」缺失**（设计 test-cases §0 要求） | [L2] `pytest.ini` 无 `filterwarnings`（全文见 a3/t2 取证）；[L2] `tests/test_v13_scheduler.py:6` 的注释自陈旧写法 `return True/False` 骗过 pytest | 同类「打印失败却 passed」的用例可以再次混入；当前只靠人改用例，没有机器兜底 | **低** |

## 分级小结

- **高（4 条）**：G-1 风险检查链路坏且未排班 / G-2 验证链路坏且未排班 / G-3 盘中无止损 / G-4 回滚与判据载体不在版本控制。
- **中（3 条）**：G-5 盘点器未接日历 / G-6 missed 零实证 / G-7 v13 之外的声明失真。
- **低（1 条）**：G-8 假绿灯结构门禁。
- **其中「设计未覆盖」4 条**：G-1、G-2、G-3、G-5（其余为「设计已覆盖但未收口 / 载体不成立」）。

## 反面提醒（避免清单过长失真）

- 本清单**不含** V13 的策略规则与收益评价（D-2 边界）；也不含 10-01 起零成交的策略层原因
  （可能属"没到调仓周期"或"策略判断不买"，本审计不判）。
- G-1~G-3 三条在 a7cd 的 `requirement.md` 现状取证里**已经写明**（E15/E16），
  但**没有进入设计文档与拆分计划** —— 这不是"a7cd 不知道"，而是"知道了没排进去"，
  因此仍按「设计未覆盖」计（判据：`design.md` 6 份文档全文检索无 `risk_check` / `verification_job` / `intraday` 的落点声明）。
- [L2] 佐证：`grep -rnE "risk_check_job|verification_job|intraday_monitor|rule_guard" docs/requirements/REQ-261004154902-a7cd/design/` → **0 命中**。
  精确起见：`intraday` 一词在设计中**出现过**，但指的是 `application/risk/intraday_risk_service.py`
  的**通知**落点（design.md:236 / interfaces.md:88 的 D4「notifier 为 None 时 debug 静默」），
  与 G-3 说的**盘中止损执行路径**（`application/services/intraday_monitor.py` + `rule_guard`）不是同一条链路 —— 后者在设计中零命中。

## 附：置信度、适用边界与被证伪假设（可执行复核）

> 全部命令在 `quantsys-v2/` 下可直接粘贴执行。

### A. 置信度分级与复核方式

| 置信度 | 本文件中的缺口 | 复核命令 | 期望 |
|---|---|---|---|
| 高（L1/L2 双证据） | G-1、G-2、G-3、G-4 | `grep -c "def get_trades_since\|def list_positions\|def count_rebalances" adapters/outbound/repositories/simulation_repository.py`；`grep -c "predicted_return = 0.12" infrastructure/jobs/verification_job.py`；`grep -c "account_name='rotation_main'" application/services/intraday_monitor.py`；`git status --porcelain -- docs/requirements/REQ-261004154902-a7cd` | 分别：`0`；`1`；`1`；`?? …` |
| 高（L1 实跑 + L3 库） | G-5、G-6、G-7 | `venv/bin/python tools/check_should_have_run.py; echo exit=$?`；SQL `select status,count(*) from quant.scheduler_runs group by 1`；`grep -m1 factors_count live_trading/configs/strategies/v14.yaml` + `python3 -c "import json;print(len(json.load(open('live_trading/models/v14_p0_valid_factors.json'))))"` | exit 2；无 `missed` 行；`75` vs `78` |
| 中（L2 静态定位） | G-8 | `grep -c filterwarnings pytest.ini` | `0` |

### B. 适用边界（怎么验边界本身）

- **风险等级的判据**：等级不是主观打分，取自「链路是否在跑 + 坏了有没有人知道」。复核方式：对每条缺口跑 `grep -rn "<该链路符号>" --include=*.py .` 确认它仍被引用（仍在跑），再查 `quant.scheduler_tasks` 是否存在对应任务行（有没有人知道）。
  例：`grep -rn "risk_check_job" --include=*.py . | grep -v tests` 应命中 `application/jobs/trading_jobs.py`；SQL `select count(*) from quant.scheduler_tasks where command='v13_risk_check'` 应为 `0` → 支撑 G-1 的「高」。
- **覆盖归属的判据**：`grep -rnE "risk_check_job|verification_job|intraday_monitor|rule_guard" docs/requirements/REQ-261004154902-a7cd/design/ | wc -l` → `0` 即「设计未覆盖」。
- **时间边界**：所有结论截至 2026-10-06 09:4x；复核时先 `date +%F' '%T` 记录时刻。

### C. 被证伪的假设 → 支撑命令

| 被证伪的假设 | 复核命令（可直接粘贴） | 期望输出 |
|---|---|---|
| 「a7cd 现状取证里的 E15/E16 已一并修掉」 | `grep -rnE "risk_check_job\|verification_job\|intraday_monitor\|rule_guard" docs/requirements/REQ-261004154902-a7cd/design/ \| wc -l`；`grep -c "def count_rebalances" -r adapters/ application/ infrastructure/` | 前者 `0`（设计零命中）；后者 `0`（方法不存在） |
| 「归档需求的回滚路径可用」 | `git status --porcelain -- application/observability/run_outcome.py`；`git ls-files --error-unmatch application/observability/run_outcome.py` | `?? …`；`error: pathspec … did not match` |
| 「漏跑判据可靠（休市日不误报）」 | `venv/bin/python tools/check_should_have_run.py; echo exit=$?`；SQL `select count(*) from quant.trading_calendar where trade_date='2026-10-05'` | exit 2 且报 `daily-strategy-validation` 漏跑；而该日历表行数 `0`（休市）→ 误报成立 |
