# REQ-261004154902-a7cd · V13 策略实现缺陷排查（因子/模型/调仓/止损全链路取证）

> **TL;DR**
> 1. **是什么**：用户反馈「V13 这些策略有问题」+「**经常罢工、不交易、不发信息**」——取证结论：**因子与模型是好的**，坏的是**失败不可见**（干了没干、成了没成，外部看不出来，也没人被告知）。
> 2. **为什么**：调仓失败被吞后仍记 success；挂单撮合崩在取数那一步 → 两笔挂单从 8/24 搁浅至今、只留 ERROR 日志；交易日判定只看「近 7 日有 K 线」→ 长假被当成交易日；失败上报的唯一出口是**已下线的 Agent OS(8080)**；通知只在「成功干了活」时发。
> 3. **得到什么**：修完「声明 = 记录 = 实际 = 有人知道」，并把休市日误开火（下一个爆点 **2026-10-05 06:30 / 09:31**）堵掉。

```
  APScheduler                 StrategyService               SimulationTrader
  scheduler_tasks             configs/strategies/v13.yaml    (+ config_simulation.yaml)
  cron '30 6 * * 1-5'   -->   get_config('v13')        -->   run_daily_check()
  tz=Asia/Shanghai            account=v13_simulation         |
  = 06:30 CST（盘前）          stop_loss=-0.15（覆盖生效）      +--> ① _is_trading_day(today)
        |                     top_n=8（未覆盖，实际 5）      |      只看「近 7 日有 K 线」
        |                                                    |      长假 -> 误判为交易日  ✗
        v                                                    +--> ② check_stop_loss
  job_executor                                               |
  classify_job_result  <--  status='success'  <---------+     +--> ③ rebalance()
  （只看 status / success）                              |            except: 吞掉，返回 success=False
                                                        |                  |
                                                        +--------------------+  返回值被丢弃 ✗
                                                             run_daily_check 无条件
                                                             return executed=True ✗
```

> 立项动因：用户直接反馈「感觉策略 v13 这些策略有问题，没有实现好」。
> 本需求不走「凭感觉改代码」，先取证定性，再修可证伪的缺陷。
> 分类：feature（按 reqboard 立项类型档执行）；轻档。

## L1 一句话目标 + 可证伪判定标准

**目标**：把 V13 日检链路上「声明 / 记录 / 实际」三者不一致的缺陷修到一致——
即**跑起来的那一刻、报出来的状态、账户里真实发生的事，三者必须对得上**。

**判定标准（可跑，见文末「判定标准」逐条命令）**：
1. 制造一次调仓失败（因子为空 / 模型抛错），`run_daily_check()` 不得再返回 `executed=True, action='rebalance'`，
   且 `quant.scheduler_runs` 该次 run 不得记 `success`；
2. 以 `today=2026-10-05` 判交易日 → `False`（当前实现为 `True`，见证据 E4）；
3. 以 `today=2026-10-08` 判交易日 → `True`（当前实现为 `False`，见证据 E4）；
4. `v13-simulation-trading` 的下一次触发时刻，与 `v13.yaml` / 代码 docstring 声明的时刻一致；
5. 生效参数单源：`rebalance_days` / `top_n`（持仓数）/ `single_stop_loss` 的声明值与运行时值一致；
6. `V13_CONFIG.model_path` / `factors_path` 指向真实存在的文件，或该链路被显式下线（无调用方）。

## 边界

（L2 范围边界；≤3 条；未写入即本次不做）

- **B1（做）口径一致**：修「静默成功 + 声明与实际不符」——调仓/止损失败必须如实上报、
  声明参数必须等于生效参数、cron 声明时刻必须等于真实触发时刻。
- **B2（做）失败必须有人知道**：任何自动链路（策略日检 / 挂单撮合 / 调度任务 / 服务停摆）
  的失败与「该跑没跑」必须留痕并主动外发；休市日不得开火、复市首日不得跳过。
- **B3（不做）**：不改模型与因子算法本身、不调参、不评价收益、不动数据库表结构、
   不改写 `v13_simulation` 的历史成交与净值。

## L3 轻路径依据 + 单向升级

**依据**：缺陷集中在 3 个已存在的函数与 1 份配置的**语义**上（`run_daily_check` 的返回值、
`TradingDayGuard` 的判定来源、`build_cron_trigger` 的时区口径、两份策略配置的优先级），
无新子系统、无新数据模型、无新决策点。

**单向升级信号（出现任一即停手升重档）**：需要改表结构 / 需要新增调度子系统 /
需要为「交易日判定」引入新数据源 / 需要重写 `SimulationTrader` 的调仓算法 /
「账本自洽」这条若需重构账本口径或回填历史数据（E14 的虚增现金怎么处置是人的决定，不是 agent 能自定的）。

## 产品定义

本需求的产品是**策略执行链路的可信性**，不是策略收益。
对下游（agent 投资脑、看板、复盘）而言，V13 日检的价值在于「它报的一切都是真的」：
- 它说今天调仓了 → 账户里真有对应的成交；
- 它说 success → 真的没跳过、没抛错；
- 它声明持仓 8 只、止损 -15% → 运行时就是 8 只、-15%；
- 它说「今天不是交易日」→ 交易所确实休市，而不是数据没到。

现状破坏了上述全部四条（证据见下），因此下游读到的是**看起来正常、实际不可信**的信号。

## 用户与角色

| 角色 | 关心什么 | 现状痛点 |
|---|---|---|
| 用户（策略所有者） | V13 是否按设计在跑、要不要继续信它 | 9/1–9/11 账户 0 成交而任务每天记 success（E2）；「经常罢工、不交易、不发信息」（E9–E12） |
| agent（投资脑） | 是否需要人工补位干预 | 9/11 只能自己手工补一笔止损（E3）；挂单搁浅 41 天无人知（E9） |
| 看板 / 调度 | 任务健康度 | 「success」不区分「干了」与「跳过了」（E1） |
| 运维 | 为什么某天没跑 | cron 写 6:30、历史实跑 14:30、下次要按 6:30 打（E5） |

## 功能点（G2 条款）

- **FR-1: 日检返回值必须如实反映调仓与止损的成败** —— `run_daily_check` 不得丢弃 `rebalance()`
  的返回值；`rebalance()` 的 `except` 不得吞异常后仍被上层记成功。
- **FR-2: 调仓/止损失败必须让调度态可见** —— 失败要落进 `quant.scheduler_runs.status` 与日志，
  与「正常跳过」可区分（新增 `reason` 语义：`rebalance_failed` / `factor_empty` / `not_trading_day` / `hold`）。
- **FR-3: 交易日判定以 `quant.trading_calendar` 为准** —— 「今天」分支不得只靠「近 7 日有 K 线」
  启发式；数据源不可用时保守判非交易日并**保持可见**（现有降级告警保留）。
- **FR-4: V13 日检触发时刻的声明与实现必须一致** —— cron 小时字段的时区口径二选一并写进文档，
  同时给出回归锁（断言 next_run_time）。
- **FR-5: 策略参数单一来源** —— `live_trading/configs/strategies/v13.yaml` 与
  `live_trading/config_simulation.yaml` 的冲突项（持仓数、止损线、权重）必须收敛为一份，
  且运行时值等于声明值。
- **FR-6: 未接线的重构链路必须显式处置** —— `application/strategies` 新链路
  （`V13_CONFIG` / `StrategyExecutor` / `XGBoostStrategy`）当前既未排班、又指向不存在的
  模型与因子文件、且账户写死 `default`；要么接线并修好，要么标注下线，不得留着冒充「已实现」。
- **FR-7: 挂单不得永久搁浅**（用户症状「不交易」）—— `execute_pending_orders` 在任何单笔
  异常下都不得中断整批且不留痕；撮合失败必须落库（`status`/`fail_reason`）+ 主动外发；
  撮合窗口必须落在交易时段内（不许再出现「非交易时段（16:41）→ 全部拒绝」）。
- **FR-8: 停摆与「该跑没跑」必须可见**（用户症状「经常罢工」）—— 服务停摆、调度静默、
  关键任务漏跑，必须由**进程外**的探活/盘点发现并主动外发；不允许「监控跑在被监控进程里」，
  也不允许「任务该跑没跑」只能靠人翻库发现。
- **FR-9: 只在失败时闭嘴是不允许的**（用户症状「不发信息」）—— 失败上报不得依赖单一外部
  通道（当前唯一出口 Agent OS `localhost:8080` **不可达**）；通道失败必须降级到飞书并留痕；
  「今天什么都没干」本身也要有一条可见的日结信号。
- **FR-10: 账本必须自洽**（症状「不交易」背后更坏的一条：**账是假的**）—— 同一账户下任一标的
  的累计卖出不得超过累计买入；现金/持仓/成交三表必须可互相重放对上；重复卖出必须被拦截并留痕。
  当前实证超出量为 300045/300561/300765/300469 四只，虚增现金 ≈ ¥49,425（E14）。

## 现状取证（2026-10-04 实测；证据编号在判定标准中被引用）

- **E1 静默成功（代码级）**：`live_trading/simulation_trader.py:870`（`run_daily_check` 尾部，函数起于 :821）
  无条件 `return {'executed': True, 'action': 'rebalance'}`，**丢弃** `self.rebalance(today)` 的返回值；
  而 `rebalance()`（起于 :872）的 `except`（:981）把异常转成 `{'success': False}` 后仅记日志。
  → 调仓抛错 = 对外 success。
- **E2 账户 0 成交却每天 success（库级）**：`quant.simulation_trades` 中 `v13_simulation`
  在 2026-09-01~2026-09-11 **零笔成交**；`quant.simulation_equity_snapshot` 显示现金
  自 8/31 起钉在 `39272.10`；同期 `quant.scheduler_runs`(task_id=249) 9/1、9/4、9/6、9/7、9/9
  **全部 `success`**。而按 `_is_rebalance_due`（5 个交易日）实测 9/9 已达 7 个交易日 →
  调仓应当发生却未发生（`simulation_account.last_rebalance_date` 至今停在 `2026-08-31`）。
- **E3 人工补位痕迹（库级）**：`quant.simulation_trades` 2026-09-11 SELL 300345 的 `reason`
  为自然语言：「rule31补位止损：华民股份-15.17%深度证伪，**并行进程11日无任何处置记录**（decision_history为0）…」
  —— 即自动链路 11 天没动作，只能由 agent 手工补。
- **E4 长假误判（纯函数复刻，实跑）**：`TradingDayGuard` 对「今天」用
  「近 7 日有 K 线」启发式；库内最新日 K = `2026-09-30`，而 `quant.trading_calendar` 记载
  **10-01~10-07 休市、10-08 为下一交易日**。复刻结果：
  `10-05→True(差5天)`、`10-06→True(差6天)`、`10-07→True(差7天)`、`10-08→False(差8天)`。
  → 休市第 5~7 天会被判成交易日（会调仓），**复市首日反而被判非交易日（会跳过）**。
- **E5 触发时刻漂移（库 + 代码）**：库内该任务 `cron_expression='30 6 * * 1-5'`，
  而现行 `build_cron_trigger(..., tz='Asia/Shanghai')` 用**本地时区**解释 → **06:30 触发（盘前）**；
  同一行的 `next_run_at` 却写着 `2026-09-14 14:30:00+08`（旧口径遗留），
  代码 docstring 写「Runs at 14:30 (30 minutes before market close)」、
  `v13.yaml schedule` 写 15:30、`docs/FEISHU_NOTIFICATIONS.md` 写 14:25。
  → 历史实跑确为 14:30（`scheduler_runs` 8/13、8/14、8/31 均 14:30:0x），
  自 2026-09-01 引入 `tz='Asia/Shanghai'` 后语义变为 06:30，且 9/12 之后服务停摆，
  **这次漂移尚未在生产暴露**；最早暴露点是 **2026-10-05(周一) 06:30**（恰为休市日，见 E4）。
- **E6 配置双源、部分静默失效（代码级）**：`SimulationTrader` 加载
  `live_trading/config_simulation.yaml`，其中 `risk_control.top_n=5` / `single_stock_stop_loss=-0.12` /
  `max_single_weight=0.18`；`StrategyService._create_trader` 只用 `v13.yaml` 覆盖了
  `rebalance_days` 与 `single_stop_loss`（= -0.15），**`top_n`、权重上限没有覆盖**。
  实测账户持 **5** 只（`quant.simulation_positions`），而 `v13.yaml`、`V13StrategyDefaults`、
  `V13StrategyUseCase` docstring 一律声明 **8** 只。
- **E7 未接线的新链路（代码级）**：`application/strategies/v13_config.py:16-17`
  指向 `live_trading/models/xgboost_multi_factor_model.json` 与 `config/v13_factors.json`
  ——**两个文件在磁盘上都不存在**（真实为 `v13_model.json` / `valid_factors.json`）；
  `V13_CONFIG.params` 为空 → `min_score` 落 0.0（yaml 为 0.5）、`reference_capital` 落 1,000,000（yaml `initial_capital` 为 100,000）；
  `StrategyExecutor.execute_all` 一律以 `account_name='default'`（已冻结账户）执行 V13/V14；
  库里**没有** `strategy_execute_all` 任务行 → 该链路未被排班。
- **E8 口径数字漂移（代码级）**：`v13.yaml` 写 `factors_count: 68`、`_handle_v13_daily_check`
  docstring 写「68 factors」，实际 `valid_factors.json` 与模型特征数均为 **75**；
  因子计算器日志自述 85，实测初始化报「共 86 个因子」。
- **E9 挂单搁浅 41 天（库级，症状「不交易」）**：`quant.simulation_pending_orders` 中
  `agent_virtual` 两笔挂单（id=7 买 688169、id=8 买 601888）自 **2026-08-24** 创建后
  `updated_at` 与 `created_at` 完全相同 → **从未被任何一次撮合触碰过**，至今 `status='pending'`。
  同表另两笔（id=5/6）的 `fail_reason` 是「**非交易时段（16:41）**，A股交易时段为 9:30-11:30 / 13:00-15:00，委托拒绝」
  ——撮合曾被放在盘后执行。
  全账户自 **2026-09-11** 起再无任何成交（`quant.simulation_trades`）。
- **E10 撮合崩在取数第一步（日志级）**：2026-10-02 09:31:07 的 MARKET_OPEN 撮合
  （`DailyOrchestrator._match_pending_orders`）连续报
  `(psycopg2.errors.UndefinedColumn) column simulation_pending_orders.decision_price does not exist`
  → 撮合在「取挂单」这一步即失败，`pending_orders_matched` 在整个日志中出现 **0 次**。
  该缺列已由 `20261002_orm_drift_missing_columns.py` 于 10-02 12:46 之后补上
  （现测 `get_pending_orders` 正常返回那 2 笔）；根因是 9/13 `cedfb4ed`（M5）引入的
  ORM↔DB 漂移，9/14 `5ea49c5e` 的提交信息亦自陈同一类故障（「挂单构造 TypeError」「orchestrator 全天停摆 263 次 tick error」）。
- **E11 失败上报的唯一出口是下线服务（日志级，症状「不发信息」）**：Agent OS `localhost:8080`
  **不可达**（实测连接被拒）；而调度器的内层失败上报走 `agent_os_reporter.report_event(...)`
  （`infrastructure/scheduler/job_executor.py:197-203`），失败只留日志。
  飞书通道本身**是通的**（`logs/api.log` 有「飞书发送成功 / delivered: true」实证），
  但通知只在「确实干了活」时触发（如 `_send_notification` 仅当有买卖单才发）——
  **「什么都没干」与「干失败了」都不产生任何面向人的消息**。
- **E13 调仓最后一步必崩、且通知方法根本不存在（代码级，已由本窗口独立复核）**：
  `live_trading/simulation_trader.py:957` 调 `self._send_rebalance_notification(...)`，
  而该方法的 `def` 缩进在 `if __name__ == '__main__':` 块内（:1561-1563）→ **不是类方法**。
  实测 `hasattr(SimulationTrader, '_send_rebalance_notification') == False`
  （同块内 `_format_rebalance_content` 亦 False；调用点由 2026-09-11 `7fea7e973` 引入，def 来自 07-21 `3713d377a`）。
  后果：每次调仓走到第 10 步必抛 `AttributeError` → 被 `rebalance()` 的 `except`（:981）吞成
  `{'success': False}` → 被 `run_daily_check`（:870）丢弃 → 对外 success；
  **且「调仓通知」自 2026-09-11 起从未发出过**（正是用户症状「不发信息」的一个直接来源）。
  注意时序：该方法在第 7/8 步（执行交易、存库）之后 → **钱已动、错被吞**，这是「不可信」的最坏形态。
- **E14 账本超卖、凭空多出 ¥49,425 卖出收入（库级，已独立复核）**：`v13_simulation` 有 4 只
  累计卖出 > 累计买入：300045 买 1000 / 卖 2000、300561 买 700 / 卖 1400、
  300765 买 300 / 卖 600、300469 买 200 / 卖 400（净额分别为 -1000/-700/-300/-200）。
  成因是**双数据源**：一条读 `simulation_positions`（持仓表）的路径与
  `_rebuild_portfolio_from_trades`（交易流水净额口径，已把它们算成 0）并存 → 重复卖出。
  金额合计 ≈ ¥49,425（≈初始资金 10 万的 49%）→ 账户显示的累计收益 **+32.99% 里含虚增部分**。
- **E15 风险检查/预测验证/周报三条链路是坏的、且没排班（库 + 代码）**：
  调度表内**没有** `v13_risk_check` / `v13_verification` / `v13_weekly_report` 任何一行
  （仅 `id=249 v13-simulation-trading`）；`infrastructure/jobs/risk_check_job.py` 五处硬编码
  `account_name='default'`（冻结账户、0 持仓）且调用仓储**不存在**的方法
  （`get_trades_since`/`list_positions`/`count_rebalances`）与不存在的列 `trade.direction`
  （ORM 列名是 `action`）；`verification_job.py` 同病，且**预测收益硬编码 `0.12  # TODO`**
  ——「预测准确性验证」是自造的；两者空跑分支返回 `{"status":"completed"}` → 空跑也算成功。
- **E16 盘中无人止损 V13（代码级）**：`application/services/intraday_monitor.py:77`
  `PaperTradingEngine(account_name='rotation_main')` 写死；而
  `domain/watch/services/rule_guard.py:31-39` 自 2026-09-11 起拒绝为策略账户建盯盘规则。
  两头叠加 → V13 持仓只剩「每日 06:30 日检」这一道止损，**盘中没有任何保护**。
  当前 4 只持仓最深 -12.3%，未触及 -15%（阈值经 `_create_trader` 覆盖确为 -15%，见反向证据）。
- **E17 测试假绿灯（代码级）**：`tests/test_v13_scheduler.py` 的用例体是 `return True/False`
  —— pytest 忽略返回值，输出里打印「❌ Job执行失败」「❌ 任务不存在」却报 **3 passed**；
  `tests/regression/test_strategy_config_refactor.py:25-26` 把**不存在的模型路径**断言为期望值
  → 回归测试把 E7 的 bug **锁死**；`tests/test_scheduled_jobs_account_value.py` 用真实仓储
  **没有的**方法做 Fake → 掩盖 E15 的 AttributeError。「测试全绿」因此不能当证据。

### 反向证据（必须一并记录，避免为迎合而罗列）

- **因子→模型路径本身是通的**：以生产同源代码复刻（`V13FactorCalculator.get_latest_factors` +
  `xgboost.XGBRegressor.load_model` + `model.predict`），5 只样本实测 **75/75 因子可用、0 缺失**，
  预测正常出值（`0.0160 / 0.0213 / 0.0174 / 0.0099 / -0.0007`）。
  → V13 的**因子与模型不是坏的**，坏的是「什么时候跑、跑失败了怎么报、报的参数是不是真的」。
- **止损阈值经 `_create_trader` 覆盖后确为 -15%**：虽然 `config_simulation.yaml` 写 -0.12，
  但 `StrategyService._create_trader` 会用 `v13.yaml` 的 `risk.single_stock_stop_loss` 覆盖 → 生效 -15%。
  据此核对现有 4 只持仓亏损（300862 -12.3% / 300109 -10.4% / 300534 -9.8%）**均未触及 -15%**，
  **不能**据此宣称「止损该响没响」。
- **`_get_stock_pool` 近 10 天窗口当前有效**：实测 5279 只候选、最新日 K 滞后 4 天，池子非空。

## 接口与数据契约（feature 档必填）

- **`SimulationTrader.run_daily_check() -> dict`**（本次要改的对外语义）
  - 输入：无（日期取 `datetime.now()`；账户来自构造）
  - 输出：`{'executed': bool, 'reason': str, 'action': 'stop_loss'|'rebalance'|'hold', ...}`
  - **新契约**：`rebalance()` 返回 `success=False` 时必须体现为
    `{'executed': False, 'reason': 'rebalance_failed', 'error': <str>}`；
    `executed=True` 仅当调仓**确实执行成功**。
  - 兼容：`executed` / `reason` 字段为既有字段（2026-08-12 引入），本次只修正取值语义，不新增字段名。
- **`TradingDayGuard.check(day) -> TradingDayVerdict`**
  - 新增来源常量 `SOURCE_CALENDAR='trading-calendar'`；`is_trading_day` 的判定真源改为
    `quant.trading_calendar` 是否有该日行（表内仅存交易日，实测 23373 行、无 `false` 行）。
  - 保留既有 `degraded` / `source` 语义与降级外发；日历不可用时仍保守判非交易日并标 `degraded`。
- **`quant.scheduler_runs`**：不新增列，`status` 取值集合不变（`success` / `failed`），
  失败原因进 `error`；不在本次新增表结构（B3）。
- **迁移与回滚**：无表结构变更、无历史数据改写；回滚 = `git revert` 对应提交。
  唯一「数据面」影响是修复后 V13 日检会重新开始产生成交与快照——属预期行为。

## 判定标准（可跑，逐条对应条款）

1. 对应 FR-1 / FR-2：`venv/bin/python -m pytest tests/live_trading/ -v`（新增用例：让 `factor_calc.get_latest_factors`
   返回空 DataFrame / 让 `model.predict` 抛错 → 断言 `run_daily_check()` 不回 `executed=True`）。
2. 对应 FR-3：`venv/bin/python - <<'PY'` 复刻 E4 的 5 个日期断言：
   10-05/10-06/10-07 → `False`；10-08 → `True`。
3. 对应 FR-4：打印 jobstore 中 `v13-simulation-trading` 的 `next_run_time`，与声明口径一致；
   并补一条回归断言（防止再次引入 8 小时漂移）。
4. 对应 FR-5：一条只读脚本打印「声明值 vs 运行时值」三元组
   （`rebalance_days` / `top_n` / `single_stop_loss`），三处必须一致。
5. 对应 FR-6：`grep -n "model_path\|factors_path" application/strategies/v13_config.py`
   → 指向存在的文件，或该文件已无调用方（`grep -rn "V13_CONFIG\|StrategyExecutor" --include='*.py'` 给出结论）。
6. 对应 FR-7：造一笔必然抛错（非 `TradingError`）的 pending 挂单 → 断言 ①该单被标 `failed`
   或保留 `pending` 但**有 fail_reason/留痕**；②其后的挂单**仍被继续处理**（批量不中断）；
   ③产生一条外发告警。另：断言撮合入口在非交易时段被调用时不会把挂单批量打成 `failed`。
7. 对应 FR-8：杀一次 API 进程（`kill -9`）后，**进程外**探活必须在 N 分钟内主动外发一条
   「服务停摆」；并对「应跑未跑」给出盘点命令（`is_enabled=true` 的任务按 cron 推演
   「今天该跑几条 / 实际跑了几条」，差额必须可见）。
8. 对应 FR-9：在 Agent OS 不可达的前提下，触发一次失败类通知 → 断言飞书侧收到，
   日志同时留下「agent 通道失败 → 降级 feishu → delivered=true」三行证据。
9. 对应 FR-10：`psql -c "select symbol, sum(case when action='BUY' then shares else -shares end) from quant.simulation_trades where account_name='v13_simulation' group by 1 having sum(...) < 0"`
   → 修复后**必须 0 行**；且「现金重放」（按 trades 从初始资金重放）与
   `simulation_account.cash_available` 的差额必须能逐项解释（含 E14 那 ¥49,425 的处置结论）。
10. 回归：`venv/bin/python -m pytest tests/test_v13_scheduler.py tests/live_trading/ tests/test_trading_day_guard.py tests/services/test_pending_orders.py -v` 全绿，
   且 E17 的三处「假绿灯」用例**已改成真断言**（断言失败必须让用例红）。

## L4 批准闸门 + 下一步

- **下一步**：design —— 用 `reqboard_ask_confirm(target=artifact, kind=requirement)` 交棒；未获批准不得进入。
- 批准后产出设计文档至 `docs/requirements/REQ-261004154902-a7cd/design/`，
  再经 `reqboard_submit(kind=design)` + 确认后进入拆分。

## L5 轻档 ≠ 无产物

本文件即 requirement 产物（头部带 REQ id），经 `reqboard_submit(kind=requirement)` 登记后请人确认。

<!-- reqboard:marks:begin 机器维护，请勿手改 -->

#### 条款接收状态（随卡的生命周期自动更新）

| 编号 | 接收状态 | 承载任务 |
|------|---------|---------|
| FR-1 | 🔴 **未被接收** | — |
| FR-2 | 🔴 **未被接收** | — |
| FR-3 | 🔴 **未被接收** | — |
| FR-4 | 🔴 **未被接收** | — |
| FR-5 | 🔴 **未被接收** | — |
| FR-6 | 🔴 **未被接收** | — |
| FR-7 | 🔴 **未被接收** | — |
| FR-8 | 🔴 **未被接收** | — |
| FR-9 | 🔴 **未被接收** | — |
| FR-10 | 🔴 **未被接收** | — |

> 🔴 **未被接收（10 条）**：FR-1、FR-2、FR-3、FR-4、FR-5、FR-6、FR-7、FR-8、FR-9、FR-10

<!-- reqboard:marks:end -->
