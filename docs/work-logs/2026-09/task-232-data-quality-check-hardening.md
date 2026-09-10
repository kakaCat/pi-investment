# 任务 232「每日数据质量检查」加固（拆分/超时/去重）

- 窗口：w-23c70356（investor / PI 投资顾问）
- 日期：2026-09-11（非交易时段作业，无下单）
- 触发：用户对 232 号定时任务「成功耗时 9.7~116 分钟、失败 2.8 小时、22:00 起卡死 1.9 小时」提出处理请求
- 结论：根因不是"重复调度"，而是**参数键漂移 + 回填阶段无预算 + 失败重试放大 + 共享 Session 毒化级联**；已修复并实测。

## 一、结论先行（含对我此前判断的更正）

### 1. 「与进程内同名作业重复」= 我此前判断有误，予以更正

证据（2026-09-11 00:4x 核查）：

- quant.scheduler_tasks 中任务 232 仅 1 条；APScheduler jobstore public.apscheduler_jobs 中 task_232 仅 1 行（next_run_time=1789135200）。
- 三条派发路径最终都指向同一个 job 类，不产生重复执行：APScheduler → dispatcher → JobRegistry（application/jobs/registry_setup.py ← data_jobs.py）→ infrastructure/jobs/data_quality_check_job.DataQualityCheckJob；
  infrastructure/scheduler/scheduler.py:690 的 legacy handler；application/services/scheduler_handlers.py:84 的 webhook handler。
- infrastructure/... daily_jobs_bootstrap.py 的进程内作业表为 evening_pipeline / freshness_guard / chip_distribution / financial_statements / evolution_fitness / event_calendar_check —— **不含 data_quality_check**，即不存在"同名进程内作业"。
- 数据源：psql 查 public.apscheduler_jobs、quant.scheduler_tasks；日志 logs/launchd-stdout.log 第 1183113 行「Loaded task: 每日数据质量检查 (id=232, cron=0 22 * * *)」。

因此「去重」无需改动；此项处理为**核验结论**而非代码改动。

### 2. 耗时方差来自回填阶段，不是检查阶段（更正我先前的量级判断）

2026-09-11 全市场实跑（DB 真实参数，5689 只 × 30 天）：

- 总墙钟 901.2s；其中回填 822.86s（50 只 × 16.5s），检查阶段仅约 78s。
- 历史失败 run 3391（2026-09-03 22:00 → 09-04 00:47）：duration_ms=10076645（2.80 小时），error=InFailedSqlTransaction。
- 夜间数据源大面积超时（baostock 登录失败/服务器连接失败/Broken pipe，AkShare RemoteDisconnected），单只回填最坏要走满多 provider × 重试，失败率 100%。

即：检查阶段是廉价的库内查询；**9.7~116 分钟的方差全部由回填阶段（网络绑定 + 失败重试）×（0~100 只）决定**。

## 二、五项根因与对应修复

| # | 根因 | 证据 | 修复 |
| --- | --- | --- | --- |
| 1 | 参数键漂移：DB 配 days/stock_limit，实现读 check_days/symbols_limit → 配置静默失效 | 旧配置 {"days":365,"max_workers":8,"stock_limit":100,...}；日志「日期范围 30 天 / 股票限制: 全部」 | 作业边界加 _normalize_params：别名归一（days→check_days、stock_limit→symbols_limit）+ 钳制 + 记录 effective_params/param_notes |
| 2 | 无墙钟预算：回填可无限期空转 | run 3391 空转 2.8h | DEFAULT_MAX_RUNTIME_SEC=1800；检查阶段传 deadline（预留 MIN_BACKFILL_BUDGET_SEC=120s）；超时如实标注 timed_out/check_truncated/checked_stocks |
| 3 | 单次回填无额度：一次尝试几十只 | run 3480 回填 50 只耗时 924.87s | 额度 = min(max_backfill_symbols=50, 剩余预算 ÷ BACKFILL_SEC_PER_SYMBOL=20s)，按 missing_days_count 降序取 Top-N；额度受限时写 budget_limited + backfill_skip_reason |
| 4 | 失败重试放大：全灭后仍跑 retry_failed(max_retries=5) | 日志「回填失败率过高: 100.0% (阈值: 50%)」 | RETRY_SKIP_FAIL_RATE=0.8 熔断，失败率 ≥80% 判定数据源不可用，跳过重试轮 |
| 5 | 共享 Session 毒化级联 + 告警路径静默失败 | run 3391 的 InFailedSqlTransaction；00:31 日志「质量告警检查失败: OperationalError terminating connection due to idle-in-transaction timeout」 | 回填前释放挂起事务；告警查询前回滚 + 失败重建会话重试一次；except 内 session.rollback() 切断级联 |

附带修复：

- **告警内容从未落日志**：_send_quality_alerts 用 structlog 风格关键字参数调用 stdlib logger（本模块是 logging.getLogger），抛「Logger._log() got an unexpected keyword argument alert_count」后被外层 except 吞掉。已改标准 logging 写法并落全文。
- **孤儿 run 回收**：SchedulerRepository.recover_orphan_runs() + APScheduler start() 钩子，进程重启后把遗留 running 记录判为 failed（不再出现"卡死 1.9 小时"的僵尸行）；故障注入实测通过。
- 回填"部分失败"日志原打印「补充失败: None」，改为输出成功/失败/补充条数。
- 明细截断如实说明：服务层 stocks_with_issues 上限 50，检出 5689 只时日志提示「明细仅返回前 50 只，回填范围以此为界」。

## 三、改动文件

- quantsys-v2/infrastructure/jobs/data_quality_check_job.py（参数归一/预算/额度/熔断/会话卫生/告警日志/诚实标注）
- quantsys-v2/application/services/data_quality_service.py（deadline 参数 + check_truncated/checked_stocks/skipped_stocks；RETRY_SKIP_FAIL_RATE 熔断；构造器全依赖可注入）
- quantsys-v2/infrastructure/scheduler/scheduler.py（legacy handler 透传新增标记）
- quantsys-v2/adapters/outbound/repositories/scheduler_repository.py（recover_orphan_runs）
- quantsys-v2/domain/ports/repository_ports.py（端口新增方法，实现类唯一）
- quantsys-v2/infrastructure/scheduler/apscheduler_service.py（启动时回收孤儿 run）
- quantsys-v2/tests/test_data_quality_job_guardrails.py（新增，13 项）

## 四、验证（真实数据 + 故障注入）

1. 单测：tests/test_data_quality_job_guardrails.py 13 passed（参数别名/钳制/额度/Top-N/预算跳过/熔断/日志/truncated）。
2. 相关回归：tests/test_data_quality_job_guardrails.py + test_scheduler_inner_failure.py + test_scheduler.py + test_apscheduler_service.py + test_scheduler_duplicate_prevention.py + test_scheduler_misfire.py = 143 passed / 4 skipped。
3. 小范围真实实跑（2026-09-11 00:13）：check_days=5、30 只、max_backfill_symbols=5 → 185.2s；budget_limited=true、backfill_skip_reason 完整；熔断实测触发「回填失败率 100% ≥ 80%，跳过 5 只标的的重试」。
4. 全市场真实实跑（2026-09-11 00:16:03 起，DB 真实参数）：WALL 901.2s，checked_stocks=5689/5689，check_truncated=false，backfill_degraded=true；回填 822.86s/50 只 0 成功 → 熔断生效（若无熔断将再跑 5 轮重试）。
5. 孤儿回收故障注入：构造 running 记录（started_at=now()-3h）→ 重启后日志「♻️ 已回收孤儿 run 1 条: [3535]」，DB 该行 status=failed、duration_ms=10808810；随后 count(status=running)=0。
6. 僵尸 run 3527（2026-09-10 22:00 我重启 qv2 时遗留）已置 failed，duration_ms=7766886，error 标注「孤儿 run：进程重启遗留」。

## 五、剩余风险与后续项（未处理，供决策）

1. **告警只落日志、不外发**：infrastructure 层无 NotificationFacade 投递先例（已 grep 确认），质量告警目前不会推送到飞书。建议按 CLAUDE.md 通知架构统一设计后再接。
2. **超时是协作式预算**：不打断在途的单只回填请求，实测总时长 = 预算内耗时 + 至多 1 次在途请求；若需硬上限需进程级看门狗。本夜 901s 远低于 1800s。
3. **检查语义可疑**：5689/5689 只全部"有问题"，avg_coverage_rate 92.37%、total_missing_days 9986（23 个交易日窗口），而库内 2026-09-10 有 5499 只有数据；D 级 727 只/日的日常告警可能源于口径（停牌/上市前区间/覆盖率分母）。属既有口径问题，未在本次改动范围内。
4. **拆分建议（可选）**：若希望覆盖更长窗口，建议"周度全市场（check_days=90，非交易日跑）+ 日度热门子集（symbols_limit=300）"双任务，而非把日检窗口拉长——现参数已支持，可一句话启用。

## 六、留痕

- 决策审计：decision_audit(record) —— 参数归一 + 孤儿回收。
- 记忆：memory_write（namespace=experience）。
- 通知：feishu_notify（R-010，normal/reports）。
- 提交：仅上述 7 个文件（不含他人改动）。
