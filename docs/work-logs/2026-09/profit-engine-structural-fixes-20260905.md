# Profit Engine 结构修复报告（2026-09-05）

审计报告：[profit-engine-completion-audit-20260905.md](./profit-engine-completion-audit-20260905.md)
范围：A) 调度双轨注册收敛 + 冲突检测 + 僵尸 job 修复；B) pool_refresh 双实现合并；C) 打分 provider 注入修复；D) M8 每日重训调度注册；E) signal_tracking schema 迁移 quant + 测试污染清理；F) data_quality_check 事务修复。
署名：w-8366e526

## 实证结果（全部真机验证）

| 修复 | 验证方式 | 结果 |
|---|---|---|
| A 双轨注册 | qv2 重启启动日志 | "Registered 28 jobs to JobRegistry" 仅 1 次，无 overwriting；JobRegistry.register 同实例幂等 ×2、同名异实例 RuntimeError 均复现 |
| B pool 委托 | 注册态执行 DB 任务 258 | run 3432 success，refreshed=3、skipped=0、changed=3、failed=0（此前 0/29 假成功） |
| C provider 注入 | 同上（B 依赖 C） | 3 动态池刷新成功，无 NoneType 崩溃 |
| D M8 重训 | 注册态执行 DB 任务 320 | run 3434 success：491 只/8431 样本/32 特征/acc 0.5726 → 元数据落库 ml_models(20260905_105730) → 再跑门控跳过 age=0d |
| E schema 迁移 | repo upsert 冒烟 + 行数核查 | signal_tracking 迁 quant，test 行清零，序列随迁，9 条真实信号留存 |
| F 事务修复 | 故障注入探针 | run 3435：毒化事务后返 ok → status=success（旧代码此处必崩 InFailedSqlTransaction）；run 3436：毒化后抛错 → status=failed 干净落账 |

## 修复明细

### A) 双轨注册收敛（main.py / job_registry.py）cf376c64
- main.py 删除第二个 `register_all_jobs()` 块——曾用旧实例覆盖同名 Job（旧版覆盖新版 13 天，dynamic 池停更）。
- JobRegistry.register 幂等：同实例跳过（debug 日志）；同名不同实例抛 RuntimeError fail-fast。
- 启动实测：28 jobs 注册一次，DB 26 行任务全部加载无 Unknown-command。

### B) pool_refresh 双实现合并（trading_jobs.py）0f1247ea
- PoolRefreshDailyJob.execute 委托 `scheduler_tasks.handle_pool_refresh_daily`（asyncio.to_thread），删旧全池循环吞错假成功。
- 状态映射：failed → JobResult.fail；ok 携带 refreshed/skipped/changed/failed 计数。
- run 3432：refreshed=3 changed=3 failed=0 —— 3 个 dynamic 池恢复真刷新。

### C) 打分 provider 注入修复（service_registry/service_factory/opportunity_scoring_service）ef56bdfe
- 两处创建 `OpportunityScoringService` 的构造点（registry + factory）兜底注入 financial/fund_flow ORM repo（lazy import 防环）。
- score_stocks 在 repo 为 None 时防御降级（空 maps），杜绝 NoneType 崩溃。

### D) M8 每日模型重训落地（data_jobs/model_jobs/registry_setup/scheduler_tasks/scheduler.py）85a9b1e2
- 新增 `ModelTrainDailyJob`（name='model_train'，timeout 3600）入 MODEL_JOBS → 注册 28；DB 行 320（03:30 每日）此前被调度器 Unknown-command 拒绝。
- scheduler_tasks.handle_model_train 与 scheduler._handle_model_train（subprocess 调用不存在的 train_ml.py）统一改委托真实 `handle_model_train_auto`（model_type 默认 lightgbm）。
- 修 3 处真实缺陷：
  1. **tz 崩溃**：train_date 为 timestamptz（tz-aware），`datetime.now()` naive 减法 TypeError → 统一 astimezone。
  2. **model_path NameError**：`trainer.save_model` 返回值未捕获即引用 → 改为捕获并兜底。
  3. **create(dict) 静默吞**：`MlModelORMRepository` 无 create(dict)，`BaseORMRepository.create(obj)` 收 dict 后静默返回 None → 元数据永不落库（run "成功"但 ml_models 无新行，次日必重训）→ 改用仓库真实 `save_model()` upsert，dict 字段 json 序列化。
- run 3434 后 ml_models 出现 20260905_105730（acc 0.5726 > 旧 0.5481），重跑门控返回 (False, age=0d) —— 闭环。
- 金融时效性检查补注册 FinancialTimelinessCheckJob（data_jobs，webhook 桥保留）。

### E) signal_tracking 迁移 quant（repository/attribution/weekly_report + migration SQL）2d66cd79
- migration `infrastructure/persistence/migrations/2026-09-05_signal_tracking_to_quant.sql`（注：qv2 scripts/ 被 gitignore，SQL 惯例落点在 infrastructure/persistence/migrations/）。
- 已执行：删除 9 行 test* 源测试污染；`ALTER TABLE ... SET SCHEMA quant`（序列自动随迁）；id 默认值显式 `nextval('quant.signal_tracking_id_seq')`。
- repository/attribution/weekly_report 全部 SQL 限定 quant.signal_tracking；upsert 冒烟返回 id 21。

### F) data_quality_check 事务修复（job_executor.py）7b2601a1
- 根因：executor 会话与 Job 共享同一线程级 session，Job 内部 DB 工作中途报错留下 aborted 事务 → `complete_run` 的读写报 `Can't reconnect until invalid transaction is rolled back`（实证 run 3408/3391）。
- 修复：成功/异常两分支均先 `session.rollback()` 再 `repo.complete_run()`。
- **故障注入实证（替代 2 小时全量跑，契合"故障路径必须故障注入实测"工程纪律）**：注册探针 Job 毒化共享事务——
  - 毒化后返回 ok → run 3435 status=success（旧代码此处必崩）
  - 毒化后抛 RuntimeError → run 3436 status=failed 且 error 为干净业务消息（旧代码 complete_run 会再抛 InFailedSqlTransaction）
- 补充：当日 CLI 全量 232 因工具中断成孤儿 run 3431，已手动闭环 failed 并注明原因；232 今晚 22:00 cron（0 22 * * *）将在线上自动全量跑一次，次晨可复核自然证据。

## 遗留说明
- `application/services/ml_train_task.py` 中同名 `handle_model_train_auto` 副本（:200 同款 tz bug）零消费者（grep 空），判定死代码，未修；建议后续删除防误导。
- scheduler.py legacy 5-command 回退保留为既有债务（agent-os 兼容），JobRegistry 为 live 路径唯一事实源。
- 迁移 SQL 落点注意：qv2 `scripts/` 被 .gitignore，DB 迁移记录须放 `infrastructure/persistence/migrations/`。
