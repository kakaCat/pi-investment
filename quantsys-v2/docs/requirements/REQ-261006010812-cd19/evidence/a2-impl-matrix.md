# a2 · 设计与实现一致性矩阵（面 B + 面 C 事实）

> 需求：REQ-261006010812-cd19（t2）｜ 判定口径与证据强度分级见 [`../design/interfaces.md`](../design/interfaces.md) §2/§3。
> 取证时刻：2026-10-06 09:3x（CST）｜ 库查询均连生产库 `quant_investment` 只读。

## 1. 一致性矩阵（26 个落点）

| # | 设计条目 | 判定 | 证据 | 说明 |
|---|---|---|---|---|
| M-01 | design.md:45-47（新增 RunOutcome，`ok` 唯一实现） | 已实现但语义偏离 | [L2] `application/observability/run_outcome.py:115`（类）、`:17`（公式） | 设计的公式是 `ok = executed and error is None`（design.md:68 / interfaces.md:19）；实现多一条 **`and reason not in SKIPPED_REASONS`** → 同一输入两侧结论可能不同（实现更严，但属未声明的偏离） |
| M-02 | design.md:46-47（新增 FailureSink） | 已实现且一致 | [L2] `application/observability/failure_sink.py:92 def report_failure`；接线 `live_trading/simulation_trader.py:60,865` | 落点存在且被日检链路实际调用 |
| M-03 | design.md:48-51（既有模块只做接线，不改算法） | 已实现且一致 | [L2] `live_trading/simulation_trader.py:841-870`（docstring 明写 skipped≠success / failed 带 error） | 与设计 §2.2 的返回语义一致 |
| M-04 | design.md:50-51（通知方法移回类体） | 已实现且一致 | [L2] `live_trading/simulation_trader.py:975 def _send_rebalance_notification` | 缩进已在类体内（改前在 `if __name__ == '__main__':` 块内） |
| M-05 | design.md:84-85（`except` 必须写 `self._last_error`） | 未实现 | [L2] `grep -rn "_last_error" live_trading/` → **0 命中** | 设计点名的字段从未存在；实现改由 `_report_failure`（:865/:901）承担留痕。字段级偏离，但目的达成 |
| M-06 | design.md:68-78 + interfaces.md:27-32（合理跳过记 `skipped`，**不得记 success**） | 已实现但语义偏离（**实锤·最重**） | [L1] `quant.scheduler_runs` id=**3375**（2026-10-05 14:37）`status='success'`，而其 `result.details.details.check.status='skipped'`、`reason='not_trading_day'`（路径已实测展开）；[L2] `application/jobs/trading_jobs.py:52 → application/jobs/job_protocol.py:43-50`（只把 failed/error/fail 判失败，其余一律 `JobResult.ok`） | `StrategyService` 侧的三态映射确实做了（`application/services/strategy_service.py:375-377`），但**生产调度路径**（task 249 → `v13_daily_check` → `V13DailyCheckJob`）绕过了它：休市日仍记 success。设计要消灭的「假绿」在 10-05 实际发生过 |
| M-07 | design.md:105-136（交易日真源改日历链） | 已实现且一致 | [L2] `application/services/trading_day_guard.py:62-64`（`SOURCE_CALENDAR` 常量）、`:314`（取用）；`application/services/trading_day_resolver.py:29,44,63`（三级降级）；`trading_calendar_service.py:9,25`（degraded 带出）；[L3] `select trade_date,exchange from quant.trading_calendar where trade_date between '2026-10-01' and '2026-10-09'` → 仅 10-08/10-09 有行（10-05/06/07 无行） | 设计的三条口径已收敛到日历链；面 C 的事实基础成立 |
| M-08 | design.md:133-134（`judge_trading_day(..., calendar_has_day=None)` 兼容） | 已实现且一致 | [L2] `application/services/trading_day_guard.py:138,144`；[L1] `pytest tests/live_trading/ tests/test_v13_scheduler.py -q` → **36 passed, exit 0** | 纯函数兼容参数在位，既有用例未破 |
| M-09 | design.md:149-154（宽限语义：NULL=必补跑） | 已实现且一致 | [L2] `infrastructure/scheduler/apscheduler_service.py:35 resolve_misfire_grace`、`:210` 调用点；[L3] `quant.scheduler_tasks` id=249 `misfire_grace_time_seconds = NULL` | 加载器不再用 `or 300` 抹掉 NULL |
| M-10 | design.md:143 + data-model.md:43（id=249 cron 改 `30 14 * * 1-5`） | 已实现且一致 | [L3] `select cron_expression,is_enabled from quant.scheduler_tasks where id=249` → `30 14 * * 1-5`, `t=1` | 与声明值一致；10-05 实际 14:37 触发（cron 生效） |
| M-11 | design.md:152-154（missed 落库为 `status='missed'`） | 无法判定 | [L2] `infrastructure/scheduler/apscheduler_service.py:120-145 _on_job_missed` 存在；[L3] `select status,count(*) from quant.scheduler_runs group by 1` → success 2999 / failed 155 / cancelled 1，**无 missed 行** | 缺的证据：一次真实的 missed 落库结果。本审计不能在生产制造 missed（D-3 禁止生产副作用）→ 只能判「落点在、端到端未证」 |
| M-12 | design.md:195-196 + data-model.md:45（新增任务行 `pending-orders-match`，cron `31 9 * * 1-5`） | 未实现 | [L1] `select id,name,command,cron_expression from quant.scheduler_tasks where name like '%pending%' or command like '%pending%'` → **0 行** | 撮合仍只依赖 orchestrator 相位，失败落不到 `scheduler_runs` —— 设计 §7 的调度归属未落地 |
| M-13 | design.md:186-193（撮合护栏 + 单笔续跑 + 过期契约） | 已实现且一致 | [L2] `application/services/account_trading_service.py:780`（docstring 摊开三条）、`:814-832`（off-hours 分支返回 `skipped_off_hours`）、`:839 expired` 计数 | 返回体字段与设计 §2.3 一致（errored/skipped_off_hours/expired/details） |
| M-14 | design.md:197-198（存量挂单按 `expired` 规则处置） | 已实现但语义偏离 | [L3] id=7/8 `status='expired'`，`fail_reason='frozen: 2026-10-04 止血 per REQ-261004154902-a7cd（原 status=pending…）'` | 设计口径是 `expired: pending > 1 trading day`。实际是一次**人工止血冻结**（notes/stopgap-2026-10-04.md），不是代码规则跑出来的结果 → 该规则本身仍缺一次真实执行的证据 |
| M-15 | design.md:159-163（配置单源 + 全量覆盖 + 打印生效值） | 已实现且一致 | [L2] `application/services/strategy_service.py:41,49,60`（覆盖清单与映射）；[L1] `venv/bin/python tools/check_strategy_config_effective.py` → **exit 0**，三参数「声明==生效」 | 10-04 记录的「声明 8 vs 生效 5」「-15% vs -12%」已收口 |
| M-16 | design.md:167-168（死参数 `enable_stop_loss`/`enable_rebalance` 要么接线、要么删） | 已实现但语义偏离 | [L2] `application/services/strategy_service.py:89 _DEAD_KWARGS`、`:514` 使用点；全仓仍有 **32** 处引用（API 路由/任务注册/文档字符串） | 实现选了第三条路：**保留并在传入时告警**，未接线也未从 API 删除 → 与设计二选一的要求不符（但已不再「假装能关」） |
| M-17 | design.md:173-180（未接线链路修实：真实路径 / 本金注入 / ok 判定 / 删假断言） | 已实现且一致 | [L2] `application/strategies/v13_config.py:21-22`（真实 model/factors 路径）、`domain/strategies/xgboost_strategy.py:49-56`（删 1_000_000 硬编码 + 兜底说明）、`infrastructure/jobs/strategy_trading_job.py:147 ok = bool(entry.get('ok'))`、`tests/regression/test_strategy_config_refactor.py:35,38,78`（`Path(...).exists()`）；[L1] C5 → **10 passed, exit 0** | 四处落点齐备 |
| M-18 | design.md:211-219（探活第三条判据 + 盘点器 + 节流） | 已实现且一致 | [L2] `tools/health_probe.py:207`（调用 `should_have_run.audit_should_have_run`）、`application/services/should_have_run.py:30-33,119`（dedup_key 节流）；[L1] `venv/bin/python tools/check_should_have_run.py` → **exit 2**（启用 11 / 漏跑 1 / 改动豁免 10） | 判据本身工作正常；**当前有 1 条真实漏跑**（见 M-19 后的说明与缺口清单） |
| M-19 | design.md:246-252（渠道兜底 D1 + formatter 兜底 D2） | 已实现且一致 | [L2] `domain/notification/policies/notification_policy.py:126-135`（兜底追加，替代 `return supported if supported else available`）、`infrastructure/notification/channels/feishu_channel.py:200-230`（两轮选择 + `catch_all` 兜底）；[L2] `infrastructure/notification/formatters/feishu_formatters.py:449 SystemAlertFormatter` | 设计允许「补两个 formatter **或** 兜底渲染」→ 实现取后者，符合设计 |
| M-20 | design.md:248（`AgentChannel.supports()` 不得恒真） | 已实现但语义偏离 | [L2] `infrastructure/notification/channels/agent_channel.py:249-265`（docstring 明写「始终返回 True（能力层面）」） | 设计要求「按 OS 实存性/健康态返回」；实现**保留恒真**，把修复全部压在 `select_channels` 兜底排序上并写了理由。风险：任何**直接用 supported 做排除**的新调用方会重演 7 类通知 100% 丢弃 |
| M-21 | design.md:251-252（D4/D5：`skipping` 升 warning；`_send_feishu` 返回值必须被消费） | 已实现但语义偏离 | [L2] `adapters/inbound/fastapi_app/daily_jobs/alerting.py:9`（声明已消费）、`:68 def _send_feishu`；但 `adapters/inbound/fastapi_app/daily_jobs/health.py:187` 仍 `_send_feishu('...')` **不接返回值** | 「4 处调用方全不看返回值」已收敛但未归零：还剩 1 处 |
| M-22 | design.md:238 + interfaces.md:90（`pool_scan_scheduler` 的假通知：补实现或删除） | 未实现 | [L2] `grep -n "TODO" application/services/pool_scan_scheduler.py` → `:85 # TODO: 实现通知逻辑（邮件、飞书、钉钉等）` | 占位日志仍在，一个字节不外发 |
| M-23 | design.md:263-271（账本自洽：唯一真源 + 卖出前置校验 + 对账器，超卖清单必须 0 行） | 已实现但语义偏离 | [L1] `tools/reconcile_sim_account.py --account v13_simulation` → **exit 0**（结论「自洽」，已排除 4 只已登记脏数据）；[L3] 但 raw 口径 `select symbol,sum(case when action='BUY' then shares else -shares end) from quant.simulation_trades where account_name='v13_simulation' group by 1 having ...<0` → **仍有 4 行**（300045 -1000 / 300469 -200 / 300561 -700 / 300765 -300）；[L2] 卖出侧护栏在 `live_trading/simulation_trader.py:1476` + `tests/test_oversell_guard.py` | 设计/需求的判据是「超卖清单必须 **0 行**」；实际以「登记为脏 + 工具内排除」达成 exit 0。**口径已被裁定替换**（notes/legacy-cash-disposition.md），但设计文档与验收判据没同步 → 读者按原文验证会判失败 |
| M-24 | design.md:276-289（回滚 = `git revert` 对应提交） | 未实现 | [L1] `git status --porcelain`（20 个受改文件为 `M`、5 个新模块为 `??`）；`git log -1 -- <path>` 的最近提交均为 a7cd 之前（2026-09-07~10-03） | 无提交可 revert（详见 a1 / A1-17）。实际留档载体是 notes 的 patch + tar 快照 |
| M-25 | design.md:287-288（灰度开关 `V13_CHAIN_STRICT`，默认 true） | 未实现 | [L2] `grep -rn "V13_CHAIN_STRICT" --include=*.py .` → **0 命中**（仅设计/计划文档命中） | 设计的止血开关从未接线 → 若告警风暴，只能改代码回滚 |
| M-26 | test-cases.md:14-18（T0 假绿灯修正 + 结构门禁） | 已实现但语义偏离 | [L2] `tests/test_v13_scheduler.py:44-106` 已是真 `assert`；`tests/regression/test_strategy_config_refactor.py` 已改 → [L1] C1 36 passed / C5 10 passed；但 `pytest.ini` **无** `filterwarnings` 把 `PytestReturnNotNoneWarning` 升级为错误 | 三条用例的**内容**修好了；「让 `return True` 必然变红」的**结构门禁**没落地 |

## 2. 判定汇总

| 判定 | 条数 | 编号 |
|---|---|---|
| 已实现且一致 | 12 | M-02, M-03, M-04, M-07, M-08, M-09, M-10, M-13, M-15, M-17, M-18, M-19 |
| 已实现但语义偏离 | 8 | M-01, M-06, M-14, M-16, M-20, M-21, M-23, M-26 |
| 未实现 | 5 | M-05, M-12, M-22, M-24, M-25 |
| 无法判定 | 1 | M-11 |
| **合计** | **26** | — |

## 3. 本轮新增的库面事实（面 C，供报告引用）

- [L3] `quant.scheduler_tasks`：启用 11 条中 **仅 1 条**宽限为 NULL（其余 10 条 = 300 秒）；禁用 22 条全部 NULL。
- [L3] task 249 最近 6 次 run 全部 `success`，最近一次 **2026-10-05 14:37:10**（休市日，见 M-06）。
- [L3] `quant.simulation_pending_orders` 共 7 行：executed 3、failed 2（`fail_reason` 均为「非交易时段（16:41）…」，8/21 的历史形态）、expired 2（止血冻结）；**当前无 pending**。
- [L3] `quant.simulation_account` v13：`cash_available=57171.96`、`last_rebalance_date=2026-08-31`（自 8/31 起未再调仓）。
- [L3] `quant.simulation_positions` v13 行数 = 4；按成交净额的非零标的数 = 4（当前两侧一致，未观察到双源劈叉）。
- [L3] 10-01 起全账户 **零成交**；净值快照最新为 2026-10-02。

## 4. 与 t1 结论的交叉印证

- t1 的 A1-17（回滚押 git 但实现未提交）↔ M-24（同一条落点，判定「未实现」）。
- t1 的 A1-14（v14 factors_count 75 vs 真实 78）↔ M-15 的边界：本卡只核了 v13 三参数一致（C4 exit 0 覆盖的是 v13 链路），v14 的声明失真不在 C4 覆盖内。
- t1 的 A1-2（判据两载体）↔ M-18/C3 实跑：盘点器确实能跑（exit 2 且给出逐条对照），说明**判据可用**，缺的是版本控制内的载体（A1-7）。

## 5. 置信度、适用边界与被证伪假设（可执行复核）

> 全部命令在 `quantsys-v2/` 下可直接粘贴执行；SQL 用 `venv/bin/python -c "import psycopg2;c=psycopg2.connect(host='localhost',port=5432,dbname='quant_investment');cur=c.cursor();cur.execute(\"<SQL>\");print(cur.fetchall())"` 形态或等价的 psql。

### 5.1 置信度分级与复核方式

| 置信度 | 本文件中的条目 | 复核命令 | 期望 |
|---|---|---|---|
| 高（L1/L3 可复跑） | M-06、M-10、M-12、M-14、M-23 | SQL：`select status, result->'details'->'details'->'check'->>'status' as inner from quant.scheduler_runs where id=3375`；`select count(*) from quant.scheduler_tasks where name like '%pending%'`；`select count(*) from (select symbol from quant.simulation_trades where account_name='v13_simulation' group by 1 having sum(case when action='BUY' then shares else -shares end)<0) t` | 分别：`success \| skipped`；`0`；`4` |
| 中（L2 静态定位） | M-01、M-05、M-16、M-20、M-21、M-22、M-25、M-26 | `sed -n '17p' application/observability/run_outcome.py`；`grep -rc _last_error live_trading/`；`grep -rc V13_CHAIN_STRICT --include=*.py .` | 分别：含 `SKIPPED_REASONS`；`0`；`0` |

### 5.2 适用边界（怎么验边界本身）

- **时间边界**：库面结论是快照。复核前先跑 `select max(started_at) from quant.scheduler_runs` 记下最新 run 时刻；若之后有新 run，`M-06` 的形态可能变化，结论应表述为「截至该时刻」。
- **口径边界**：`M-23` 有**两个口径**（工具口径 exit 0 / raw SQL 4 行）。复核时必须**同时**跑两个，只看其一即会得出相反结论：
  `venv/bin/python tools/reconcile_sim_account.py --account v13_simulation; echo "exit=$?"` + 上面的 raw SQL。
- **环境边界**：库连接参数取仓根 `.env` 的 `PG*`；若 `PGDATABASE` 不是 `quant_investment`，先确认 `select current_database()` 再解读结论。

### 5.3 被证伪的假设 → 支撑命令

| 被证伪的假设 | 复核命令（可直接粘贴） | 期望输出 |
|---|---|---|
| 「三态映射已覆盖生产路径」 | SQL `select status, result->'details'->'details'->'check'->>'status' from quant.scheduler_runs where id=3375`；`sed -n '43,50p' application/jobs/job_protocol.py` | `success \| skipped`（外层 success、内层 skipped）；代码只把 `failed/error/fail` 判失败 |
| 「调度归属已扩到 pending-orders-match」 | SQL `select count(*) from quant.scheduler_tasks where name like '%pending%' or command like '%pending%'` | `0` |
| 「灰度开关可用于止血」 | `grep -rn V13_CHAIN_STRICT --include=*.py . \| wc -l` | `0` |
| 「超卖清单已 0 行」 | SQL `select count(*) from (select symbol from quant.simulation_trades where account_name='v13_simulation' group by 1 having sum(case when action='BUY' then shares else -shares end)<0) t` | `4` |
