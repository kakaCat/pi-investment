# quantsys-v2 调度任务重复/相似功能审计（2026-09-02）

> 审计人：investor w-8366e526 @ :13080
> 用户问题：v2（quantsys-v2）30 个定时任务有重复功能和相似功能的
> 审计方法：① 30 任务 command → JobRegistry/Legacy 分发映射；② 逐 job 读实现（application/jobs/*.py + infrastructure/jobs/*.py）；③ 对账 quant.scheduler_runs 真实执行记录（3 日窗口）；④ cron 时区语义核对（APScheduler timezone=Asia/Shanghai）。

---

## 1. 前置事实澄清（避免误判）

- **两套表**：`quant.scheduler_tasks`（30 行，数字 id 232-312，APScheduler 正在执行的主表）+ `public.scheduler_tasks`（7 行 uuid/文本 id，**遗留表，无独立调度器消费**——dag_async/注册已迁 quant schema）。审计对象是 quant 30 条。
- 30 个 command **名称全部唯一**，但"名字唯一 ≠ 功能唯一"。真正的重复问题分四类，见下。
- **30 个任务全部 enabled**，近期真实触发正常（cron 全部 CST、next_run 均在 09-03 之后），**调度器本身健康**。

## 2. 审计结论总览

30 个任务实际分四类：

| 类别 | 数量 | 含义 |
|---|---|---|
| ✅ 真活任务 | ~7 | 确实执行了实质逻辑 |
| 🟡 降级/假成功 | ~8 | Job 内部抛错但外层 execute_scheduled_job 不检查 result.status，落库 success（假绿） |
| ⚪ 空壳/占位 | ~10 | execute 只打日志/数行数/TODO，不干实事 |
| 🔴 运行期错误 | ~5 | 近期直接 failed 或调不存在方法 |

**最严重的问题不是"功能重复"，而是三层叠加：A. 同一业务被多个任务分片/重复调度（数据更新、信号生成、v13 风控）；B. 大量任务空壳假成功造成"看似都在跑、其实没跑"；C. 描述与 cron 时间不一致（desc 写收盘后 15:30，实际 cron 07:30 凌晨/盘前触发）。**

---

## 3. 重复 / 相似功能组（按业务）

### 组 A：每日数据更新 —— 233 vs 240 疑似重复 + 240 运行期失败

| id | 名称 | command | cron(CST) | 状态 | 实际行为 |
|---|---|---|---|---|---|
| 233 | 每日数据更新 | data_update | 30 7 (07:30) | ✅ 真活 | legacy handler：全市场(500 只/次)K线更新，456ms→symbols_updated=500 |
| 240 | 每日数据流水线 | data_pipeline_daily | 30 8 (08:30) | 🔴 failed | DataPipelineService.run_incremental_update 缺 `config/data_pipeline.yaml`，报 No such file；desc 却写 "16:30 after market close" |
| 241 | 每周全量重建 | data_pipeline_weekly | 0 18 周六 18:00 | ⚪ 空壳 | desc "Sunday 2:00 AM" 与 cron 不符；result 为 08-25 遗留旧记录 |

**判定**：233(data_update, market=A 全市场) 与 240(data_pipeline_daily, 增量) 业务域重叠（都是"每日更新 A 股行情"），240 已因缺配置文件持续失败；241 与 238(财务) 每周也在 18:00 档。数据更新至少存在 2 套实现路径（legacy data_update / DataPipelineService），建议收敛到一条主线。

### 组 B：信号生成 —— 236 vs 242 vs 251 三层混乱

| id | 名称 | command | cron | 状态 | 实际行为 |
|---|---|---|---|---|---|
| 236 | 每日信号生成 | signal_generate | 30 8 (08:30) | ✅ 真活 | PoolSignalScanner：54 只宇宙 × 4 策略，16 信号落库（真） |
| 242 | 每日信号执行 | signal_execution_daily | 30 7 (07:30) | ⚪ 空壳 | desc 写 15:30；execute 里"临时跳过策略执行"TODO，orders_created=0，18ms |
| 251 | 实时信号监控 | signal_monitor_realtime | */5 1-6 (01:00-06:00 每5分钟) | ⚪ 空壳 | 纯 TODO："实时监控完成（待实现）"；**每 5 分钟空转 72 次/天**，且 cron 在凌晨 1-6 点非盘中（desc 说盘中） |

**判定**：242 声称"运行策略→生成信号→风控→建单"，实际空转；与 236 信号生成语义高度重叠；251 定时任务名实不符（凌晨空转 72 次）。建议：242/251 二选一补实现或停用；251 cron 若真要盘中监控应改为 9-11/13-15 时段。

### 组 C：v13 风控验证 —— 268 vs 269 vs 235 功能重叠 + 假成功

| id | 名称 | command | cron | 状态 | 实际行为 |
|---|---|---|---|---|---|
| 268 | v13-risk-check | v13_risk_check | 0 8 (08:00) | 🟡 假成功 | 调 risk_check_job.execute，details=null，实际未产出风险项 |
| 269 | v13-verification | v13_verification | 30 7 (07:30) | 🟡 假成功 | 调 verification_job.execute，details=null |
| 235 | 每周风险检查 | risk_check | 0 1 周一 01:00 | 🟡 假成功 | **调不存在方法 run_comprehensive_risk_check** → AttributeError 却落库 success |
| 249 | v13-simulation-trading | v13_daily_check | 30 6 (06:30) | ✅ 真活 | StrategyService.daily_check('v13')，真实调仓/hold 决策 |
| 270 | v14-daily-trading | v14_daily_check | 30 7 (07:30) | ✅ 真活 | 同框架 v14 |

**判定**：v13 一族有 4 个任务（249 每日检查/268 风险/269 验证/271 周报）而 v14 只有 1 个（270）——v13/v14 是同一统一框架 strategy_daily_check('v13'/'v14') 的两个版本实例，不是功能重复；但 **268/269 与 235 的风控语义重叠**（都做组合风险），且三者全是"假成功"（方法不存在/结果 null）。RiskCheckService 只有 check_signal 等单信号方法，没有 run_comprehensive_risk_check——ADR-002 迁移时把 legacy 的 `_handle_risk_check` 迁成了调用不存在方法的新 Job。

### 组 D：每日权益/市场快照 —— 264 vs 301 双快照 + 301 假成功

| id | 名称 | command | cron | 状态 | 实际行为 |
|---|---|---|---|---|---|
| 264 | daily-equity-snapshot | daily_equity_snapshot | 0 18 (18:00) | ⚪ 空壳 | 纯 TODO："权益快照完成（待实现）"，snapshots=0 |
| 301 | market_daily_snapshot | market_perception_daily_snapshot | 0 9 (09:00) | 🟡 假成功 | **调不存在方法 regime_daily**（真实方法 run_daily_snapshot），AttributeError 落库 success |

**判定**：264 与 301 名字像重复，实为不同域（账户权益 vs 市场 regime）；但 **301 调用了不存在的方法，M1 市场感知快照从未真正落库**，与 235/265/266 同属 ADR-002 迁移期假成功家族。需修 service 调用或回退 legacy。

### 组 E：行为进化链 263→266→265（刻意设计的有序链，非重复）

| id | command | cron | 状态 |
|---|---|---|---|
| 263 | evolution_fitness_daily | 30 18 (18:30) | 🟡 假成功（EvolutionFitnessORMRepository import 失败） |
| 266 | missed_opportunity_daily | 40 18 (18:40) | 🔴 failed（IAgentIntelligenceRepository 未注册） |
| 265 | decision_score_daily | 45 18 (18:45) | 🔴 failed（同 266 缺 service 注册） |

**判定**：这是 P0a/P0b 行为进化设计链（fitness 30 分后、踏空 40 分、打分 45 分），**时序不重复**，但 263/265/266 三个**全部失败**（依赖未注册/import 错误），等于行为进化 Phase1 整条链没在跑。这是"三个任务相似且全废"的最典型样本——相似不是因为重复设计，而是同一批迁移没落地。

### 组 F：其余独苗任务（无重复，独立职责）

| id | command | cron | 状态 | 行为 |
|---|---|---|---|---|
| 232 | data_quality_check | 0 16 (16:00) | ✅ 真活 | 全市场质量检查+回填，耗时 ~58min 真重活 |
| 236 | signal_generate | 见组 B | ✅ | 真 |
| 250 | pre-market-scan | 25 1 (01:25) | 🟡 半真 | desc"开盘前"，实际 01:25 凌晨；scans 5532 只→只统计未产生信号 |
| 252 | strategy_validate_daily | 0 13 (13:00) | 🟡 假成功 | 只 count 19 个策略，"TODO 实现实际验证逻辑" |
| 253 | strategy_discover_weekly | 0 2 周六 | 🔴 failed | 调 None.list_all_active |
| 258 | pool_refresh_daily | 0 18 周日-四 | 🔴 failed | 'function' object has no attribute 'list_pools' |
| 307 | trade_verify_daily | 35 15 (15:35) | ✅ 真活 | 交易对账 0 异常 |
| 308 | fund_flow_update | 30 15 (15:30) | ✅ 真活 | sina 源 6423 条，88s 真采集 |
| 311 | signal_perf_backfill | 45 15 (15:45) | ✅ 真活 | 信号胜率回填 |
| 262 | chan_knowledge_distill | 0 12 周日 | ⚪ 空壳 | 3 次历史记录，details 无实质 |
| 261 | chan_scan | 10 10 (10:10) | ⚪ 空壳 | 8ms TODO |
| 237 | 每周报告生成 | report_daily | 0 10 周五 | 🔴 failed | None.list_all_active；desc 写每周但 command 叫 daily |
| 271 | v13-weekly-report | v13_weekly_report | 0 1 周日 | ⚪ 空壳 | weekly_report_job 有 run() 但未调通（2 条历史） |
| 312 | market-style-update | market_style_update | 30 7 (07:30) | ⚪ 空壳 | style=unknown TODO |

---

## 4. 根因归纳

1. **假成功机制（最危险）**：`job_executor.execute_scheduled_job` 只 catch 异常，JobRegistry 返回的 `result.status="failed"` 不被检查 → 方法不存在/依赖缺失全部落库 success。235/301/252/263 等"每周/每日绿着失败"。
2. **迁移半成品**：desc 大量标注"从 agent-ts/scheduler_daemon 迁入"，但迁入后（a）调用不存在方法（235/301）、（b）import 错误（263/258/265/266）、（c）服务未注册（265/266）、（d）配置缺失（240）——ADR-002 迁了一批"壳"。
3. **多套实现并存**：数据更新有 legacy data_update + DataPipelineService 两套；信号有 signal_generate / signal_execution_daily / signal_monitor_realtime 三张皮；风控有 risk_check / v13_risk_check 两套入口——同一能力多任务承载。
4. **desc 与 cron 脱节**：233/240/241/242/250/251/301 的 desc 时间（15:30/16:30/盘中/收盘后）与 cron（07:30/08:30/凌晨/01:25）矛盾，读 desc 会误判意图。
5. **凌晨执行窗风险**：250 在 01:25、251 在 01:00-06:00、235 在周一 01:00、249 在 06:30、242/269/270/312 在 07:30——大量任务在盘前甚至凌晨跑，涉及"收盘后数据"的更新必然拿到旧数据。

---

## 5. 处置方案（2026-09-02 用户已批准执行，见第 6 节执行结果）

> 用户裁决：A 组（240/241/251/264）+ B 组（235/263/265/266/270）**disable，且数据库行与代码全部删除**（"disable 数据库和代码都删除，要不太乱"）；C 组（242/268/269/301）**修复不删除**。

### P0 修假成功机制（一行级修复，收益最大）
`job_executor.execute_scheduled_job` 第 89-97 行：`result = _execute_command(...)` 后检查 `result.get('status') == 'failed'` 时走 failed 分支，不再落 success。修完 235/301/252/263 等"假绿"立即现形。

### P1 收敛重复组（每组合一）
- **组 A**：停 240（缺配置持续失败）或补 config 后 233/240 二选一；241 修正 cron desc。
- **组 B**：242 与 236 合并到 signal_generate 一条线；251 要么实现盘中监控并改 cron 到 9-15 点，要么停用。
- **组 C**：修 235（RiskCheckService 无 run_comprehensive_risk_check——补方法或回 legacy _handle_risk_check）；268/269 输出 null 需检查调用的 execute 是否真执行。

### P2 清空壳
daily_equity_snapshot(264)、chan_scan(261)、chan_knowledge_distill(262)、market_style_update(312)、strategy_validate_daily(252) 若短期无实现计划，disable 比空转好。

### P3 行为进化链 263/265/266
三个全失败 = Phase1 未落地；依赖 import 错误 + service 未注册属代码问题，若 Phase1 已暂停可 disable 整链，避免每日三条失败噪音。

### P4 全量 task 大扫除后
建议逐任务核对 desc vs cron 时间语义，统一数据更新/信号生成的主执行路径，再考虑是否合并进 DSH-native 13 任务的职责（避免 v2 与 agent-os 双调度重叠——此为另一次审计）。

---

## 附：真活清单（建议保留/重点守护）

232 data_quality_check / 233 data_update / 236 signal_generate / 249 v13_daily_check / 270 v14_daily_check / 307 trade_verify_daily / 308 fund_flow_update / 311 signal_perf_backfill_daily

---

## 6. 执行结果（2026-09-02 深夜，investor w-8366e526）

### 6.1 处置矩阵（按用户 A/B/C 分组）

| 组 | id | command | 处置 | 说明 |
|---|---|---|---|---|
| A（删除） | 240 | data_pipeline_daily | 🗑 DB 删 + 代码删 | 缺 config/data_pipeline.yaml 持续失败 |
| A（删除） | 241 | data_pipeline_weekly | 🗑 DB 删 + 代码删 | 空壳 TODO，desc 与 cron 不符 |
| A（删除） | 251 | signal_monitor_realtime | 🗑 DB 删 + 代码删 | 空壳，每 5 分钟凌晨空转 |
| A（删除） | 264 | daily_equity_snapshot | 🗑 DB 删 + 代码删 | 纯 TODO 空壳 |
| B（删除） | 235 | risk_check | 🗑 DB 删 + 代码删 | 调不存在方法假成功 |
| B（删除） | 263 | evolution_fitness_daily | 🗑 DB 删 + 代码删 | import 失败 |
| B（删除） | 265 | decision_score_daily | 🗑 DB 删 + 代码删 | service 未注册失败 |
| B（删除） | 266 | missed_opportunity_daily | 🗑 DB 删 + 代码删 | service 未注册失败 |
| B（删除） | 270 | v14_daily_check | 🗑 DB 删 + 代码删 | 保留统一框架 v13 主线（249），v14 从调度表移除 |
| C（修复） | 242 | signal_execution_daily | 🔧 rebind | 空壳改为真实实现（见 6.3） |
| C（修复） | 268 | v13_risk_check | 🔧 补 return | execute/main 无返回值 → details=null 假成功（见 6.3） |
| C（修复） | 269 | v13_verification | 🔧 补 return | 同上 |
| C（修复） | 301 | market_perception_daily_snapshot | 🔧 修方法名 | 调不存在 regime_daily → run_daily_snapshot（见 6.3） |

### 6.2 数据库删除（A/B 9 行物理 DELETE）

- 执行：`DELETE FROM quant.scheduler_tasks WHERE id IN (240,241,251,264,235,263,265,266,270)`。
- 备份：`docs/work-logs/2026-09/backup/scheduler_tasks_full_20260902.tsv`（删除前 30 行全量）+ `docs/work-logs/2026-09/backup/scheduler_tasks_delete_restore_20260902.sql`（9 行恢复脚本，验证 9 条干净 INSERT）。
- 验证：现表 21 行（30-9），id = 232,233,236,237,238,242,249,250,252,253,258,261,262,268,269,271,301,307,308,311,312，全部为保留任务 ✓。

### 6.3 代码清理与修复明细

**JobRegistry 类删除**（`application/jobs/*_jobs.py`，registry_setup 动态注册自动生效）：
- `data_jobs.py`：删 DataPipelineDailyJob + DataPipelineWeeklyJob（DATA_JOBS 剩 3 项）。
- `signal_jobs.py`：删 SignalMonitorRealtimeJob（SIGNAL_JOBS 剩 4 项，含保留的 SignalExecutionDailyJob）。
- `monitor_jobs.py`：删 DailyEquitySnapshotJob + RiskCheckJob（MONITOR_JOBS 剩 1 项）。
- `analysis_jobs.py`：删 DecisionScoreDailyJob + EvolutionFitnessDailyJob + MissedOpportunityDailyJob（ANALYSIS_JOBS 剩 8 项）。
- `trading_jobs.py`：删 V14DailyCheckJob（TRADING_JOBS 剩 5 项，V13 一族 268/269 保留）。

**调度分发四通道清理**（防"删了 DB 但 legacy dict 仍可达"的平行注册陷阱）：
- `infrastructure/scheduler/job_executor.py`：legacy_handlers 删 `"risk_check"` 项（docstring 6→5 特殊命令）。
- `infrastructure/scheduler/scheduler.py`：handlers dict 删 risk_check / data_pipeline_daily / data_pipeline_weekly / signal_monitor_realtime / v14_daily_check 5 项 + 对应 `_handle_*` 方法；清理孤儿 import（PortfolioORMRepository）。
- `application/services/scheduler_tasks.py`：`_TASK_HANDLERS` 删 8 项 + `handle_*` 函数（data_pipeline_daily / data_pipeline_weekly / risk_check / signal_monitor_realtime / daily_equity_snapshot / evolution_fitness_daily / decision_score_daily / missed_opportunity_daily）。
- `application/services/scheduler_handlers.py`：删 6 个 `@register_job_handler`（data_pipeline_daily / data_pipeline_weekly / risk_check / signal_monitor_realtime / daily_equity_snapshot / v14_daily_check），清空节标题。
- `infrastructure/scheduler/scheduled_tasks.py`：删孤儿函数 daily_data_pipeline + weekly_full_rebuild（仅被 scheduler.py 已删 handler 引用）。

**C 组修复**：
- **242**：`SignalExecutionDailyJob.execute`（signal_jobs.py）与 `SchedulerService._handle_signal_execution_daily`（scheduler.py）从空壳 `infrastructure.scheduler.signal_execution_job.execute_daily_signals_job`（策略全跳过、orders=0 的 TODO）rebind 到真实实现 `application.services.scheduler_tasks.handle_signal_execution_daily`（2026-07-24 盈利闭环改造后本任务职责=当日 pending 信号兜底推送 Agent，按信号 ID 判重不重复交易）。空壳模块 signal_execution_job.py 现已无生产引用（保留文件待裁决，见 6.5）。
  - **rebind 后冒烟发现的连带根因（2026-09-02 深夜补充修复）**：`handle_signal_execution_daily` 无参构造 `SignalExecutionScheduler()` 后调 `_collect_signals`，曾必崩 `'NoneType' object has no attribute 'get_signals_by_date'`。根因：`SignalExecutionScheduler.__init__`（P2-1 依赖注入）**只给 portfolio/stock/kline repo 做了 ServiceFactory 兜底，signal/log/strategy 三个 repo 漏了**（docstring 声称"否则回退到 ServiceFactory"但未实现）——无参构造时 signal_repo=None。同款无参构造调用 `_collect_signals` 的还有 orchestrator MARKET_OPEN 主推路径（daily_orchestrator.py:344 `_collect_pending_signals`），同样在雷上。**修复**：`service_factory.py` 新增 `get_signal_execution_log_repository()`（此前缺失），`signal_execution_scheduler.py.__init__` 补上 signal_repo/log_repo/strategy_repo 三个 `or ServiceFactory.get_xxx()` 兜底（与其他 repo 对齐）。冒烟：`handle_signal_execution_daily({'skip_notify': True})` → `status: success, signals_pending: 16`；无参构造与注入构造双路径均正常。
- **268/269**：`infrastructure/jobs/risk_check_job.py` + `verification_job.py` 的 `execute()` 调 `main()` 但无 return → 调度层 `JobResult.details=None` 假成功。修复：`main()` 返回 `job.run()` 结果，`execute()` `return main()`，run 无返回值分支兜底 `{"status":"completed"}`。
- **301**：`monitor_jobs.py` `MarketPerceptionDailySnapshotJob.execute` 原 `await service.regime_daily()`（MarketPerceptionService 无此方法）→ 改为调用真实方法 `service.run_daily_snapshot(trade_date=(params or {}).get("date"))`（同步方法）。

### 6.4 验证结果

- **py_compile**：13 个改动 .py 全通过。
- **JobRegistry 运行时校验**：register_all_jobs 实际注册 25 个任务，9 个已删命令零残留；242/268/269/301 全部在注册列表。⚠️ `main.py` 日志字符串硬编码 "28 jobs registered"（非动态计数），与真实 25 不符——纯日志误导，未改代码（非本次范围，见 6.5）。
- **服务重启**：quantsys-v2 重启成功（pid 24500，health ok），最新启动段日志无 import 错误/无 Traceback；APScheduler started（fallback 模式）。
- **残留 grep**：`data_pipeline_* / signal_monitor_realtime / daily_equity_snapshot / v14_daily_check / evolution_fitness_daily / decision_score_daily / missed_opportunity_daily / risk_check` 在 6 大调度注册通道（job_executor legacy_handlers / scheduler handlers / scheduled_tasks / scheduler_handlers JOB_HANDLERS / scheduler_tasks _TASK_HANDLERS / *_jobs.py 列表）**零残留**。允许保留：① v13_risk_check/v13_verification 名称（保留任务 268/269 的 command 前缀）；② jobs_state.py `job_type='risk_check'`（独立手动异步任务框架，非 scheduler_tasks 分发通道）；③ daily_jobs_bootstrap.py 历史叙述注释。

### 6.5 顺带发现（未处理，留待裁决）

1. **scheduled_tasks.py 成孤儿模块**：删完 2 个 TODO 函数后，模块仅剩 `get_csi300_components`（也是 TODO 空壳），且全仓 grep 无任何 import 方 → 整个模块可删。不在本次 9 任务范围，未擅动。
2. **signal_execution_job.py 成孤儿**：242 rebind 后无生产引用（仅自引用 docstring/`__main__`）。是否连同删除待裁决。
3. **main.py "28 jobs registered" 硬编码**：两处日志字符串写死 28，实际 register_all_jobs 打印 25（删除前 34→后 25）。建议后续改为动态计数。
4. **249 v13_daily_check 运行期 KeyError**（stderr L16862，旧进程段）：`strategy_trading_job.py L93` `result['final_value']` KeyError——249 是保留任务、非本次回归，属独立 bug，建议另行排查。
5. **scheduler_handlers.py 无静态 importer**：删的 6 个 webhook handler 未见静态 import 方（webhook 路由可能经反射/动态加载），删除为幂等安全操作，但建议核实 webhook 注册链是否有动态发现机制。
