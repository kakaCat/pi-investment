# a1 · 设计文档自洽性与版本面取证

> 需求：REQ-261006010812-cd19（t1）｜ 被审对象：REQ-261004154902-a7cd 的 6 份设计文档 + requirement.md
> 口径见 [`../design/architecture.md`](../design/architecture.md)（五个取证面 / 四档判定 / 证据强度 L1-L4）。
> 取证时刻：2026-10-06 09:2x（CST）｜ 库与代码均为该时刻快照。

## 0. 取证命令（可复跑）

[L1] `cd /Users/mac/Documents/ai/pi-investment && git status --porcelain | wc -l` → **128**（全仓脏文件数，本审计只读，未新增改动）
[L1] `git status --porcelain -- quantsys-v2/docs/requirements/REQ-261004154902-a7cd` → `?? quantsys-v2/docs/requirements/REQ-261004154902-a7cd/`（**整个需求目录未跟踪**）
[L1] 逐路径三查（存在性 / 是否在版本内 / 被哪条 ignore 规则吃 / 最近一次提交）见 §3 全量表，命令形态：
  `git ls-files --error-unmatch <path>`、`git check-ignore -v <path>`、`git log -1 --format='%h %ad' --date=short -- <path>`

## 1. 设计条目清单（T-01 ~ T-16，本轮取证对象）

| 编号 | 文档:行 | 声明（摘要） | serves |
|---|---|---|---|
| [L2] T-01 | architecture.md:30-35 | 六个断点与落点：结果契约 / 可见性出口 / 判定真源 / 批量中断 / 时刻漂移 / 通知渠道收窄 | FR-1,2,3,4,7,9 |
| [L2] T-02 | design.md:45-47 | 新增 `application/observability/run_outcome.py` + `failure_sink.py`（应用层小模块，不新增表） | FR-1,2 |
| [L2] T-03 | design.md:50-51 | 把 `_send_rebalance_notification` / `_format_rebalance_content` 从 `if __name__ == '__main__':` 移回类体 | FR-1,2 |
| [L2] T-04 | design.md:68-78 | `RunOutcome` 字段与 `reason` 受控枚举；`ok = executed and error is None` 唯一实现 | FR-1,2 |
| [L2] T-05 | design.md:83-87 | `run_daily_check` 消费 `rebalance()` 返回值；`except` 保留但必须写 `_last_error` + `report_failure` | FR-1,2 |
| [L2] T-06 | design.md:89-103 | `execute_pending_orders` 返回 `errored`/`skipped_off_hours`/`expired`/`details[]`；单笔异常续跑 | FR-7 |
| [L2] T-07 | design.md:105-136 | 交易日判定唯一真源 = `quant.trading_calendar`，经 `trading_day_resolver` 降级链；`SOURCE_CALENDAR` | FR-3 |
| [L2] T-08 | design.md:138-154 | cron 口径以本地时区为准；id=249 由 `30 6 * * 1-5` 改 `30 14 * * 1-5`；加载器区分 misfire NULL 与显式值 | FR-4 |
| [L2] T-09 | design.md:156-168 | 配置单源 = `v13.yaml`；`_create_trader` 全量覆盖并打印生效值；`tools/check_strategy_config_effective.py` 退出码 2 表不一致 | FR-5 |
| [L2] T-10 | design.md:170-180 | 未接线链路修实（真实模型/因子路径、`reference_capital` 注入、`success`→`ok`、删假断言） | FR-6 |
| [L2] T-11 | design.md:182-198 | 挂单撮合：时段护栏 + 超 1 交易日 → `expired` + 外发；新增任务行 `pending-orders-match`（`31 9 * * 1-5`） | FR-7 |
| [L2] T-12 | design.md:200-222 | 探活第三条判据（关键任务心跳）+ `application/services/should_have_run.py` + `tools/check_should_have_run.py`（退出码 0/2/3、带节流） | FR-8 |
| [L2] T-13 | design.md:224-261 | 通知渠道兜底追加 + `AgentChannel.supports()` 不恒真 + 补 REBALANCE/RISK_ALERT formatter + `debug`→`warning` | FR-9 |
| [L2] T-14 | design.md:263-271 | 账本自洽：`simulation_trades` 唯一真源 + 卖出前置校验 `oversell_blocked` + `tools/reconcile_sim_account.py` | FR-10 |
| [L2] T-15 | design.md:273-289 | 迁移兼容与回滚：无表结构变更；回滚 = `git revert` 对应提交 + 数据行改回原值 | FR-1,4,7 |
| [L2] T-16 | design.md:332-342 | §13 四条未定决策，**答完才可进拆分** | FR-7,10 |

## 2. 自洽性检查

### 2.1 跨文档同一事实的取值一致性

[L2] **A1-1（不一致·中）** `reason` 受控枚举两处不等：`design.md:70` 列 11 个值（含 `no_cash`），
  `interfaces.md:27-32` 只列 9 类（**无 `no_cash`**，且 `ok` 单列一行）。同一契约两个权威表 → 实现者按哪份都可能被另一份判错。
[L2] **A1-2（不一致·高）** 同一判据两个载体、其中一个不可跑：`design.md:308` 要求用
  `tools/check_trading_day_judgment.py --dates ...` 验交易日判定；而 `test-cases.md:35-43` 用**内联 heredoc python** 做同一件事。
  设计把 CLI 工具当作验收载体，但该工具不存在（见 A1-5）；两份文档给出的判据形态不同（CLI vs 内联）。
[L2] **A1-3（一致·通过）** cron 目标值三处一致：`design.md:143` / `design.md:280-281` / `data-model.md:43` 均为 `30 14 * * 1-5`。
[L2] **A1-4（不一致·低）** 挂单撮合时段护栏的复用对象两处不同：`design.md:186` 写「复用既有 `TradingWindowGuard`」，
  `interfaces.md:65-66` 写「复用 `AccountTradingService._check_trading_window` / `_is_in_trading_window`，其唯一时段口径为 `MarketSessionPolicy`」。
  三个名字不是同一个东西，读者无法判定最终落点。
[L2] **A1-5（不一致·低）** 挂单过期的上层映射只在 `interfaces.md:32` 给出（`pending_expired` → 任务级 `failed`），
  `design.md:75-78` 的「按 reason 映射三态」段落未含该值 → 只读 design.md 的实现者会漏掉这条映射。

### 2.2 引用有效性（设计点名的路径是否真存在）

[L1] **A1-6（引用失效·高）** `design.md:308` 的 `tools/check_trading_day_judgment.py` **不存在**
  （`ls tools/` 无此文件）。该条是 FR-3 的验收判据 → 判据载体缺失。
[L1] **A1-7（留档失效·高）** `design.md:311`/`:314` 的 `tools/check_should_have_run.py`、`tools/check_strategy_config_effective.py`
  与 `tools/check_v13_chain_health.py` 均被 `.gitignore:85`（规则 `check_*.py`）吃掉：
  `git check-ignore -v → .gitignore:85:check_*.py`，`git ls-files --error-unmatch → pathspec ... did not match`。
  → **FR-4/FR-5 的判据载体不在版本控制内**（换机器、干净 clone 即失）。
[L1] **A1-8（留档失效·高）** `design.md:117-120` 依赖的 `application/services/trading_day_resolver.py`（REQ-261004102115-d3de 新建）
  以及 `docs/requirements/REQ-261004102115-d3de/design/architecture.md`（`design.md:325-326` 引它做口径对照）**均未跟踪**（`??`）。
[L2] **A1-9（可解析·通过）** `design.md:208` / `architecture.md:71` 写 `health-probe.plist`，
  实际文件为 `deployment/launchd/com.pi-investment.health-probe.plist`（存在，已跟踪）→ 名字略写但可解析，不计缺陷。

### 2.3 §13 四条未定决策是否闭环

[L3] **A1-10（已闭环·通过）** 四条决策**都已由人裁定并落地**，证据：
  1. 搁浅挂单 → 作废：`notes/stopgap-2026-10-04.md:8-12`（id=7/8 `pending`→`expired` + `fail_reason`）；
  2. 历史虚增 → 标记为脏并排除统计：`notes/legacy-cash-disposition.md:1-5` 引用户原话「标记为脏并从统计排除（推荐）」，
     `verification.md:343` 该验收项 `✓ 通过`；
  3. v13 日检时刻 → 14:30：`verification.md:316`「cron=30 14 * * 1-5」；
  4. 周一止血 → 已执行：`notes/stopgap-2026-10-04.md`（含回滚原值）。
[L2] **A1-11（未收口·低）** 但 `design.md:332-342` 的 §13 正文仍写「需人点头，答完才可进拆分」，
  **未回写裁定结果**；只读 design.md 的人会以为四条至今悬空。裁定落在 `notes/` 与 `verification.md`，设计本体没有指针。

### 2.4 数值口径（设计声明的数字 vs 盘上真实值）

[L1] **A1-12（已修·通过）** v13 因子数：`live_trading/configs/strategies/v13.yaml:28` `factors_count: 75`
  == `live_trading/models/valid_factors.json` 实测 75 == 模型特征数 75（`design.md:166` 记录的「声明 68 vs 真实 75」已修）。
[L1] **A1-13（已修·通过）** v13 持仓数：`v13.yaml:38,40` `max_positions/top_n = 5`（`design.md:161-165` 的「声明 8 vs 生效 5」已按用户裁定收口为 5）。
[L1] **A1-14（未修·高）** v14 因子数：`live_trading/configs/strategies/v14.yaml:20` 仍写 `factors_count: 75`，
  而 `live_trading/models/v14_p0_valid_factors.json` 实测 **78**、`v14_p0_model.json` 的 `feature_names` 实测 **78**。
  `design.md:166` 自己把这条列为「当前实证不一致」的待修项 → **该项未落地**。
[L2] **A1-15（自相矛盾·中）** `live_trading/config_simulation.yaml:22`/`:62`/`:85` 的注释仍声明
  「`top_n` 5 → **v13 链路生效 8**」，而 `v13.yaml:40` 已改为 `top_n: 5`（生效 5）。
  两处对同一事实给出相反取值 —— 恰是本设计 §5 要消灭的「假声明」形态，只是这次藏在注释里。

## 3. 版本面（面 E）全量表

> 判据：`在版本内?` = `git ls-files --error-unmatch` 是否命中；`最近提交` = `git log -1 -- <path>`；
> 工作区状态列 `??`=未跟踪、`M`=已改未提交、`clean`=与最近提交一致。

| 路径（相对 quantsys-v2/） | 存在 | 在版本内? | 被 ignore 规则 | 最近提交 | 工作区 |
|---|---|---|---|---|---|
| application/observability/run_outcome.py | 是 | **否** | — | — | ?? |
| application/observability/failure_sink.py | 是 | **否** | — | — | ?? |
| application/services/should_have_run.py | 是 | **否** | — | — | ?? |
| application/services/trading_day_resolver.py | 是 | **否** | — | — | ?? |
| tools/reconcile_sim_account.py | 是 | **否** | — | — | ?? |
| tools/check_should_have_run.py | 是 | **否** | .gitignore:85 | — | clean |
| tools/check_strategy_config_effective.py | 是 | **否** | .gitignore:85 | — | clean |
| tools/check_v13_chain_health.py | 是 | **否** | .gitignore:85 | — | clean |
| tools/check_trading_day_judgment.py | **否** | 否 | .gitignore:85 | — | — |
| tests/test_v13_chain_wiring.py | 是 | **否** | — | — | ?? |
| live_trading/simulation_trader.py | 是 | 是 | — | 749f21cd 2026-09-13 | M |
| application/services/strategy_service.py | 是 | 是 | — | 20c63187 2026-10-02 | M |
| application/services/account_trading_service.py | 是 | 是 | — | 6538b2d4 2026-10-03 | M |
| application/services/trading_day_guard.py | 是 | 是 | — | e90dea22 2026-09-14 | M |
| application/services/trading_calendar_service.py | 是 | 是 | — | e05bd620 2026-09-10 | M |
| application/services/daily_orchestrator.py | 是 | 是 | — | 20c63187 2026-10-02 | M |
| application/services/intraday_monitor.py | 是 | 是 | — | 27585cea 2026-09-12 | clean |
| application/services/pool_scan_scheduler.py | 是 | 是 | — | d4a26975 2026-09-07 | clean |
| application/strategies/v13_config.py | 是 | 是 | — | c91cd148 2026-09-09 | M |
| application/strategies/v14_config.py | 是 | 是 | — | c91cd148 2026-09-09 | M |
| application/strategies/v13_use_case.py | 是 | 是 | — | df57a042 2026-09-14 | M |
| application/risk/intraday_risk_service.py | 是 | 是 | — | 7fea7e97 2026-09-11 | M |
| application/notification/notification_factory.py | 是 | 是 | — | 14f1103d 2026-10-01 | clean |
| domain/notification/policies/notification_policy.py | 是 | 是 | — | d4a26975 2026-09-07 | M |
| domain/strategies/xgboost_strategy.py | 是 | 是 | — | d4a26975 2026-09-07 | M |
| domain/watch/services/rule_guard.py | 是 | 是 | — | 4a4e6ba1 2026-09-11 | clean |
| infrastructure/scheduler/apscheduler_service.py | 是 | 是 | — | fddaba30 2026-09-13 | M |
| infrastructure/scheduler/job_executor.py | 是 | 是 | — | 942ddfa8 2026-09-13 | M |
| infrastructure/error_reporting/agent_os_reporter.py | 是 | 是 | — | ee2658c0 2026-09-11 | M |
| infrastructure/notification/channels/agent_channel.py | 是 | 是 | — | 7fea7e97 2026-09-11 | M |
| infrastructure/notification/channels/feishu_channel.py | 是 | 是 | — | d4a26975 2026-09-07 | M |
| infrastructure/notification/formatters/feishu_formatters.py | 是 | 是 | — | 04c0b6b5 2026-09-18 | M |
| infrastructure/jobs/strategy_trading_job.py | 是 | 是 | — | d4a26975 2026-09-07 | M |
| infrastructure/jobs/risk_check_job.py | 是 | 是 | — | 41fac465 2026-10-01 | clean |
| infrastructure/jobs/verification_job.py | 是 | 是 | — | 41fac465 2026-10-01 | clean |
| adapters/inbound/fastapi_app/daily_jobs/alerting.py | 是 | 是 | — | c4fc27a4 2026-10-02 | M |
| tests/live_trading/（目录） | 是 | 是 | — | d4a26975 2026-09-07 | M |
| tests/test_v13_scheduler.py | 是 | 是 | — | d4a26975 2026-09-07 | M |
| tests/test_trading_day_guard.py | 是 | 是 | — | 3a8fe4a7 2026-10-03 | M |
| tests/test_scheduled_jobs_account_value.py | 是 | 是 | — | a4ad5664 2026-10-03 | M |
| tests/regression/test_strategy_config_refactor.py | 是 | 是 | — | c91cd148 2026-09-09 | M |
| tests/services/test_pending_orders.py | 是 | 是 | — | 6de945b5 2026-10-02 | M |
| pytest.ini | 是 | 是 | — | 763213a3 2026-08-21 | clean |
| tools/health_probe.py | 是 | 是 | — | 51f5bbbc 2026-10-01 | M |
| tools/refresh_trading_calendar.py | 是 | 是 | — | e6de5bad 2026-09-11 | M |
| live_trading/config_simulation.yaml | 是 | 是 | — | 0f41286e 2026-09-11 | M |
| live_trading/configs/strategies/v13.yaml | 是 | 是 | — | 0f41286e 2026-09-11 | M |
| live_trading/configs/strategies/v14.yaml | 是 | 是 | — | 0f41286e 2026-09-11 | clean |
| live_trading/models/v13_model.json | 是 | 是 | — | 0f41286e 2026-09-11 | clean |
| live_trading/models/valid_factors.json | 是 | 是 | — | 0f41286e 2026-09-11 | clean |
| live_trading/models/xgboost_multi_factor_model.json | **否** | 否 | — | — | — |
| config/v13_factors.json | **否** | 否 | — | — | — |
| deployment/launchd/com.pi-investment.health-probe.plist | 是 | 是 | — | 见 `git log` | clean |
| docs/requirements/REQ-261004102115-d3de/design/architecture.md | 是 | **否** | — | — | ?? |
| infrastructure/persistence/migrations/20261002_orm_drift_missing_columns.py | 是 | 是 | — | 3039fc89 2026-10-02 | clean |
| docs/requirements/REQ-261004154902-a7cd/（**被审文档本身**） | 是 | **否** | — | — | ?? |

### 3.1 面 E 的三条硬结论

[L1] **A1-16（留档缺口·高）** 被审的**整个需求目录**（含 6 份设计文档、requirement.md、decomposition.md、
  67 张任务卡、notes/、verification.md）**未纳入版本控制**（`git status --porcelain` → `??`，目录级）。
  → 设计文档的"可回滚/可追溯"没有版本层保障。
[L1] **A1-17（回滚路径不成立·高）** `design.md:289` 声明回滚 = `git revert 对应提交`（`architecture.md:68` 亦称「按主题分 commit」），
  但 a7cd 触及的代码**没有对应提交**：20 个文件为 `M`（已改未提交）、5 个新模块与 2 个测试文件为 `??`（未跟踪）。
  实际留档载体是 `notes/code-changes-2026-10-04.patch`（37 个 diff）与 `notes/code-snapshot-2026-10-04.tar.gz`（234 条目）。
[L1] **A1-18（patch 不自足·中）** 该 patch 只含**已跟踪文件的改动**，新建模块不在其中
  （`grep -c` 命中仅来自其它文件对它们的引用；`reconcile_sim_account` 在 patch 中 0 命中），
  新模块只在 tar 快照里（`tar tzf` 命中 `application/observability/run_outcome.py` 等）。
  → 单靠 patch 恢复会留下悬空 import；恢复必须用 tar 快照，而设计文档从未提到这个载体。
[L2] **A1-19（非孤立现象·参考）** 全仓脏文件 128 项，a7cd 只是其中一部分 →
  "未提交"更像本仓当前的整体工作方式，而不是 a7cd 单独的疏漏；但设计文档把回滚押在 git 上，仍属**声明与事实不符**。

## 4. t1 结论（供一致性矩阵与缺口清单引用）

- 条目数：**16 条设计条目**（T-01~T-16）；自洽性条目 **15 条**（A1-1~A1-15）；面 E 硬结论 **4 条**（A1-16~A1-19）。
- 一致（通过）：A1-3、A1-9、A1-10、A1-12、A1-13 —— 共 5 条。
- 不一致：A1-1、A1-2、A1-4、A1-5、A1-11、A1-15 —— 共 6 条（其中 A1-2 高风险：判据载体不存在）。
- 引用/留档失效：A1-6、A1-7、A1-8、A1-16、A1-17、A1-18、A1-19 —— 共 7 条。
- 对本审计需求的意义：`design.md` §12 的验收命令**不能原样当判据**（缺 1 个工具、3 个被 ignore、若干未跟踪）；
  报告第 3 节必须逐条标注「实跑 / 不可跑」，并对不可跑项给替代判据。

## 5. 置信度、适用边界与被证伪假设（可执行复核）

> 本节是对「分析」段结论的自证：每条都给**可直接粘贴执行的命令**（在 `quantsys-v2/` 下运行）。

### 5.1 置信度分级与复核方式

| 置信度 | 本文件中的条目 | 复核命令 | 期望 |
|---|---|---|---|
| 高（L1 可复跑） | A1-6、A1-7、A1-12、A1-13、A1-14、A1-16、A1-17、A1-18 | `ls tools/check_trading_day_judgment.py` / `git check-ignore -v tools/check_should_have_run.py` / `git status --porcelain -- docs/requirements/REQ-261004154902-a7cd` / `python3 -c "import json;print(len(json.load(open('live_trading/models/v14_p0_valid_factors.json'))))"` | 分别：`No such file` / `.gitignore:85` / `?? …` / `78` |
| 中（L2 静态定位） | A1-1、A1-2、A1-4、A1-5、A1-11、A1-15 | `sed -n '70p' docs/requirements/REQ-261004154902-a7cd/design/design.md \| grep -c no_cash` / `grep -c no_cash docs/requirements/REQ-261004154902-a7cd/design/interfaces.md` | 分别：`1` / `0`（枚举不一致成立） |

### 5.2 适用边界（怎么验边界本身）

- **时间边界**：本文件所有面 E 结论 = 快照值。复核方式：`date +%F' '%T` 记下当前时刻，再跑同一条 `git status`/`git log`；若结论方向变化，说明工作区在此期间被改动（不是本审计出错）。
- **仓库边界**：`git rev-parse --show-toplevel` 应变到 `/Users/mac/Documents/ai/pi-investment`；若不是，说明不在本仓执行，路径口径需整体重算。
- **面 E 的时效**：`git log -1 -- <path>` 的提交号会随提交变化；判据是「a7cd 受改文件的最近提交**早于 2026-10-04**」，复核：`for f in live_trading/simulation_trader.py application/services/strategy_service.py; do git log -1 --date=short --format='%ad %h %s' -- $f; done`。

### 5.3 被证伪的假设 → 支撑命令

| 被证伪的假设 | 复核命令（可直接粘贴） | 期望输出 |
|---|---|---|
| 「设计 §12 的验收命令清单可以直接当判据」 | `ls tools/check_trading_day_judgment.py; git check-ignore -v tools/check_should_have_run.py` | `No such file or directory` + `.gitignore:85:check_*.py` |
| 「已归档需求至少进了版本控制」 | `git status --porcelain -- docs/requirements/REQ-261004154902-a7cd` | `?? docs/requirements/REQ-261004154902-a7cd/`（整目录未跟踪） |
| 「notes 的 patch 足以恢复实现」 | `grep -c reconcile_sim_account docs/requirements/REQ-261004154902-a7cd/notes/code-changes-2026-10-04.patch; tar tzf docs/requirements/REQ-261004154902-a7cd/notes/code-snapshot-2026-10-04.tar.gz \| grep -c run_outcome` | 前者 `0`（patch 不含新模块）；后者 `≥1`（只在 tar 快照里） |
