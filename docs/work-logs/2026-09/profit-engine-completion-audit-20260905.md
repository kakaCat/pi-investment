# 盈利引擎（Profit Engine, M0-M8）完成进度审计报告

- 日期：2026-09-05
- 审计人：investor 角色，窗口 w-8366e526
- 审计对象：docs/architecture/profit-engine-overview.md + RFC 004/005 规划的 M0-M8 目标层在 quantsys-v2（:5001）/ agent-dh（:13080）三端的真实完成度
- 审计方法：**代码 + 数据库 + 调度实况 + 工具运行抽验四路交叉验证**，不信文档/工作日志自述（历史教训：agent-os evolution 0.05×i 假实现、backtest 随机 Sharpe、model 恒 0.4659、genome schema 与线上模型错位——凡"声称完成"必须找到线上证据）
- 覆盖证据：quant schema 27 张业务表行数与新鲜度、scheduler_tasks 23 条 + scheduler_runs 606 行 + APScheduler 进程内 32 job 解码、v2 启动日志、agent-dh 工具运行时真实返回

## 一、完成度总览（按证据分级）

分级口径：
- ✅ **真**：代码真实 + 线上有持续数据/运行证据（非一次性、非占位）
- ⚠️ **真但断**：代码与工具真实，但调度/数据源断供导致实质空转或连续失败
- ❌ **空洞/未接**：声称完成但代码、数据、运行三者至少两项缺失

| 模块 | 分级 | 线上证据 |
|---|---|---|
| M0 数据管线/K线/因子 | ✅ | data_update/kline 任务持续 success；signals 表 18016 行至 09-05；factor_values 有数据 |
| M0-4 数据质量报告 | ✅/⚠️ | 工具真实返回（92.5 分/100 条检查记录/check_date 09-04），但「每日数据质量检查」job(id=232) 09-03/09-04 连续事务中止失败 |
| M1 regime 判定 | ✅ | market_regime 126 行 → 09-04；regime_position_limit 真实返回（euphoria/degraded→cap30/合规/熔断检查全工作） |
| M1 主线检测 | ✅ | market_theme 22 行 → 09-04（含 09-05 00:56 落库的 09-04 主线）；stocks/fund_flow/confidence 字段有值 |
| M1 催化剂关联 | ❌ | market_theme.catalyst 列全 None（09-03/09-04 行均空）；文档已自认"M1 catalyst empty"，确认未实现 |
| M1 情绪 | ✅ | market_sentiment_daily 7 行 → 09-04；market_daily_snapshot job success 且 result 含推理文本（"情绪60, 量能9.5..."） |
| M2 池子静态层 | ✅ | stock_pools 29 池（26 static + 3 dynamic），筛选建池逻辑真实（stock_pool_service.create_from_scan） |
| M2-1 主线→标的映射 | ✅ | mainline_stocks 工具返回真实（market_theme.stocks 含个股明细） |
| **M2-2 池子每日自动刷新** | ❌ **假成功空转 13 天** | daily-pool-refresh 每跑返回 success + "0/29"，但 3 个 dynamic 池 last_refreshed 停在 **2026-08-23**，pool_change_log 0 行。详见证据 E-1 |
| M2-3 pool_battlefield | ✅ | 工具真实返回（pool35：战场评分 55.4/consolidation/reduce/conf 0.66）；pool_game_metrics 表 0 行 = 实时算不落库 |
| M3 信号生成 | ✅ | 每日 signal_generate（08:30）真写 quant.signals：18016 行 → 09-05，09-04/09-05 各 51-53 条 saved |
| M3-3 signal_track | ✅/⚠️ | 18 条记录真在（最新 09-03），回填链路工作（A 级 5D 胜率已回填）；但见证据 E-6（schema 滞留 + 测试污染） |
| M3 执行桥 | ⚠️ | signal_execution_daily（07:30）success 但 pushed:false、signals.pending 大量未消费；trading_signals/signal_executions 两表 0 行且**无任何代码写入**（遗留死表） |
| M4 仓位映射/熔断 | ✅ | 工具真实（R-006 映射表/regime cap/余量/合规 verdict/circuit_breaker 全工作）；组合 60 日回撤 -1.52% 未触发 |
| M5 交易对账/滑点 | ✅ | daily_trade_verify 任务在调度表；滑点通道（M5-1 osMemory 通道）代码在；0 成交期 0 数据属正常 |
| M6 进化引擎 | ✅ | evolution_strategy_runs 87 行且 **09-05 03:41 仍在跑**（真实引擎非占位，agent-os A 链已按假实现删除） |
| M6 周报/归因 | ✅ | 每周报告生成 job 在调度表（每周报告生成/exec=system），agent-dh delivery logs 佐证 m6-2/3 交付 |
| M7 对手行为 | ⚠️ **断供** | 工具运行时诚实降级（散户/机构 unknown、博弈机会 0、data_quality=true）；根因 opponent_behavior_snapshot **停更于 06-27**（2.5 月）+ akshare 资金流不可用；不是假实现但无输入 = 空转 |
| M8 model_predict | ✅ | 工具真实非恒等（600519=0.61 / 000001=0.80 / 300750=0.73 有区分度）；model_gate 门禁工作（test_accuracy 0.548→degraded 拒绝强依赖） |
| **M8 每日重训** | ❌ **调度缺失** | ml_models 5 个模型最新训练时间 **2026-08-20 19:51**，16 天未重训；scheduler_tasks 23 条任务 **无 model_train**；daemon handler/代码在但从未被定时触发 → 工具描述"每日凌晨重训"与实际不符。详见 E-4 |
| 假回测拆除 | ✅ | backtest_async_engine 原 random.uniform 假 Sharpe 已改显式 NotImplementedError（E-1 良好模式），注释明示"绝不产出占位 fitness" |

**加权结论**：26 ticket 对应模块中，**真实实现且线上运行 ≈ 15-16 个**；**⚠️ 真但断 ≈ 4 个**（M0-4 质量 job 失败、M3 执行桥空转、M7 断供、M0 catalyst 未接）；**❌ 空洞/假成功 ≈ 2 个明确项**（M2-2 池刷空转、M8 每日重训缺调度）。**与 09-01 rebaseline "26/26 全部完成"的声称不符**——文档自述再次高于线上实况。

## 二、证据清单（假实现/空洞/真但断）

### E-1 ⚠️ daily-pool-refresh：job 报 success 掩盖 13 天零刷新（真 bug + 假成功表象）

- DB：stock_pools 3 个 dynamic 池 last_refreshed_at 全 = **2026-08-23 02:00**；pool_change_log 0 行（从未记录过变更）。
- 调度结果：09-03 23:00 / 09-04 23:00 均返回 `{"status":"success","message":"股票池刷新完成: 0/29","details":{"refreshed":0,"total":29}}`。
- 日志铁证（launchd-stdout.log）：同一次运行
  - 26 个 static 池逐一抛错被吞：`Failed to refresh pool XX: Pool N is static, cannot refresh`
  - dynamic 池真失败：`Failed to refresh pool 低估值蓝筹股: 'NoneType' object has no attribute 'batch_get_quarterly_margins'`（打分服务依赖的 provider 未注入 = None）
- 代码根因（双重）：
  1. **同名双注册、旧版覆盖新版**：日志 `Registered job: pool_refresh_daily` → `Job 'pool_refresh_daily' already registered, overwriting`。最终生效的是 `application/jobs/trading_jobs.py::PoolRefreshDailyJob`（旧版：对全部 29 池无差别调 refresh_pool、static 异常全吞、从不区分/从不记录变更），而 `application/services/scheduler_tasks.py::handle_pool_refresh_daily`（正确版：跳过 static、到期判定、变更通知）虽在同名 registry 却未被执行。result 的 `total` 键指纹确认跑的是旧版。
  2. refresh_pool 内部 `_scoring_service` 依赖链上某 provider 未注入（None.batch_get_quarterly_margins）→ 3 个 dynamic 池也全刷失败。
- 影响：M2 池子工厂自动化失效 13 天，信号生成（M3）的宇宙 = 非空池成员，池不刷 → 信号宇宙同步陈旧。

### E-2 ⚠️「每日财报时效性检查」（task_318）：僵尸任务，每 09:00 必失败

- scheduler_runs：09-03/09-04/09-05 均 failed，错误一致：`Unknown scheduler command: 'financial_timeliness_check'. Not in JobRegistry and not in legacy handlers`。
- 代码面：任务表有该任务（cron 09:00）、实现文件在（infrastructure/jobs/financial_timeliness_check_job.py，真实 SQL 查询逻辑）、handler 注册在 `application/services/scheduler_handlers.py:98` 的 `@register_job_handler("financial_timeliness_check")` —— 但该装饰器注册进的是 **Agent OS webhook 的 JOB_HANDLERS**（`api.internal.scheduler_webhook`），而实际执行走 `infrastructure/scheduler/job_executor.py` 的 **JobRegistry**（另一套注册表，28 job）→ 两套注册表未同步，任务注册进了错误的表。
- 结论：三样东西（DB 任务/实现/装饰器）都在，互相不连通 = **半接线僵尸**。同类风险：所有只在 webhook 侧注册、不在 executor JobRegistry 的命令。

### E-3 ⚠️「每日数据质量检查」（task_232）：连续事务中止失败

- scheduler_runs 09-03/09-04 failed：`current transaction is aborted`（job 内 DB 事务未 rollback/被污染）。09-05 待跑（22:00）。
- 对照：data_quality_report 工具返回 92.5 分/100 条/check_date 09-04 —— stats 表数据在，说明写 stats 的路径与失败的 job 关系需再核（可能 stats 由其他路径写入，job 主体失败被掩盖）。**建议修复任务自身事务处理**。

### E-4 ❌ M8 "每日凌晨重训"只存在于工具描述：16 天无模型训练

- DB：ml_models 5 条，最新 train = 2026-08-20 19:51 → 16 天未重训。
- 调度：scheduler_tasks 23 条无 model_train；APScheduler 进程内 32 个 task_* 亦无 model_train；daemon handler（infrastructure/daemon/handlers/model_handlers.py model_train）与 legacy `_handle_model_train` 均在但**无任何定时触发源**。
- 工具描述矛盾：model_predict 工具描述声称"每日凌晨重训"，线上无此调度 → 描述与后端不符（同类于已教训的 rotation dry_run 声明与实现不符）。
- 旁证：model_gate 自 8/20 起恒 degraded（test_accuracy 0.548），正因模型 16 天未重训无改善。

### E-5 ⚠️ M7 opponent_behavior 数据源断供 = 诚实空转

- 工具真实降级输出（散户/机构 unknown、博弈机会 0、`数据降级: true`），非假数据——良好。
- 但供给端：opponent_behavior_snapshot 停更 2026-06-27（106 行，2.5 月死数据），且资金流数据源（akshare）不可用 → 模块空转无输入，博弈维度长期失效。P2 已知。

### E-6 ⚠️ M3-3 signal_track：真记录但 schema 滞留 + 统计被测试数据污染

- 落库在 **public.signal_tracking**（18 行，最新 09-03），而 v2 业务表全在 quant schema；`adapters/outbound/repositories/signal_tracking_repository.py` INSERT 无 schema 前缀 → 默认 public。quant 下无 signal_tracking 表。半迁移残留（signal_tracking 是唯一仍在活跃写入 public 的表）。
- 18 条信号中 11 条 source 为 test*（test_suite/test_duplicate/testClient/testAttribution/testIntegration），如 `600519 测试A级信号@1850`（id=7）—— **假 A 级混入统计**，A 级 5D 胜率 33.3% 因此失真。生产信号仅约 7 条。

### E-7 ❌ M1 催化剂关联未实现（文档自认项）

- market_theme.catalyst 列存在但全 None（09-03/09-04 行）。overview 已自注"M1 catalyst empty"。设计上由盘后例程 LLM + web_search 回写，无落库实现。

### E-8 遗留死表（低危，代码面确认）

- quant.trading_signals / signal_executions：0 行且全仓无 INSERT 写入方 → 遗留表。signal_test_log 51 行停在 2026-05-21。均不影响主链路（主链路 signals 表在跑）。

## 三、良性质检（防误伤的对照面）

- **假回测已真拆除**：backtest_async_engine 显式 NotImplementedError + 注释"绝不产出占位 fitness"（对照 agent-os A 链 0.05×i 假实现的同类教训被落实）。
- **evolution 引擎是真实引擎**：evolution_strategy_runs 09-05 03:41 仍产生 run（配合 agent-os A 链删除决策闭环正确）。
- **signal_generate → signals 落库**链路完整真实（HeatmapRepository 宇宙 → PoolSignalScanner 扫描 4 策略 → SignalORMRepository.create_signal，51-53/日）。
- **M1 每日快照 job 含推理文本**（非模板化 success）："情绪60, 量能9.5..." 说明 regime/情绪判定非占位。
- **M4/M8 门禁**（circuit_breaker、model_gate 0.50/0.55 阈值）均在 agent-dh 工具层真实执行并诚实报 degraded。
- **pool_battlefield/regime_position_limit/model_predict/signal_track/data_quality_report** 五个工具本次全部运行时抽验通过（真实返回、非硬编码、非恒等）。

## 四、修复建议（按业务伤害排序）

1. **[P0] E-1 池刷空转**：删除/下线 `trading_jobs.PoolRefreshDailyJob` 旧版，统一到 `scheduler_tasks.handle_pool_refresh_daily`（正确版），并修 `refresh_pool` 依赖注入（None.batch_get_quarterly_margins 的 provider）；加"dynamic 池连续 N 天 last_refreshed 未变即告警"。修复后补一次手动触发验证 3 个 dynamic 池刷新。
2. **[P0] E-4 M8 重训调度**：向 scheduler_tasks 注册 model_train（如 cron 每日 05:30）+ 加入 daily_jobs_bootstrap；或修正工具描述为"人工/周度触发"。注册后验证 ml_models 出新模型、model_gate 离开恒 degraded。
3. **[P1] E-2 僵尸任务**：把 financial_timeliness_check 注册进 executor JobRegistry（与 job_executor 注册源对齐），或从任务表删除——二选一，杜绝每 09:00 必失败的僵尸。
4. **[P1] E-3 数据质量 job 事务**：修 job 内事务 abort（异常路径 rollback），并核对 stats 写入路径与 job 关系。
5. **[P2] E-6 signal_tracking 迁移 quant schema + 清测试数据**（保留 test 前缀数据的隔离或删除），统计前过滤 test* 源。
6. **[P2] E-5/E-7**：M7 数据源恢复（snapshot job 重启或换源）；M1 catalyst 回写若短期不做，把 overview 的"已实现"表述改为"待实现"。

## 五、审计边界（诚实声明）

- 未逐条重放 RFC 005 的 26 条验收命令；本报告以"四路证据 + 5 工具运行抽验"判定，深色地带（e.g. M6 归因准确率、M5 滑点实盘精度）需真实交易周期后另行验证。
- M0 因子新鲜度 job、M2 create_from_scan 建池、M5 algo 拆单等未逐一跑验收，列为"代码在、未抽验"。
- 调度双轨（Agent OS webhook JOB_HANDLERS vs v2 executor JobRegistry）是 E-2 与多处注册混乱的**系统性根因**，建议独立成债跟踪。
