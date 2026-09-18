# REQ-c9f899 拆分 · 变更盘点与任务卡

## 1. 变更盘点（精确到模块；对照需求 v3 + 5 份设计文档）

### 1.1 新增（New）

| 模块 | 路径 | 用途 |
|------|------|------|
| 迁移 | quantsys-v2/infrastructure/persistence/migrations/2026xxxx_watch_todo_loop.py | 四张新表 + 两表加列 |
| ORM | infrastructure/persistence/orm/models/watch_todo.py | watch_todos / watch_runtime_state / watch_rule_changes / watch_receipts |
| 领域纯函数 | domain/watch/services/level_resolver.py | 级别判定（intent × 持仓 × 宪法级 → P0..P3） |
| 领域纯函数 | domain/watch/services/owner_router.py | 账户 → owner_kind/owner_ref/autonomy |
| 领域纯函数 | domain/watch/services/noise_policy.py | 反复触发判定与自愈动作枚举 |
| 端口 | domain/watch/ports.py 扩展 | IWatchTodoRepository / IWatchRuntimeStateStore / IWatchRuleChangeRepository |
| 仓储适配 | adapters/outbound/repositories/watch_todo_repository.py | 待办 CRUD + 巡检查询 |
| 仓储适配 | adapters/outbound/repositories/watch_runtime_state_repository.py | 运行态 upsert/恢复 |
| 仓储适配 | adapters/outbound/repositories/watch_rule_change_repository.py | 规则变更审计 |
| 应用服务 | application/services/watch_engine/todo_service.py | 创建/认领/关闭 + 终态校验 |
| 应用服务 | application/services/watch_engine/receipt_service.py | 三段回执 + 幂等 |
| 应用服务 | application/services/watch_engine/noise_self_heal_service.py | 抑噪 + 修规则待办 |
| 定时任务 | adapters/inbound/fastapi_app/watch_sla_job.py | 到期巡检（唯一收敛权威） |
| 定时任务 | adapters/inbound/fastapi_app/watch_heartbeat_job.py | 心跳/影子超期告警 |
| 通知模板 | infrastructure/notification/formatters/watch_level_templates.py | P0/P1/P2/P3 四类模板 |
| 路由 | adapters/inbound/fastapi_app/routes/watch_todo_async.py | 待办/修复/指标端点 |
| 脚本 | quantsys-v2/scripts/migrate_watch_backlog.py | 172 条积压收敛 |

### 1.2 修改（Modify）

| 模块 | 路径 | 变更 |
|------|------|------|
| 判据 | application/services/watch_engine/conditions.py | EvalResult 加 metric/unit；各 handler 显式产出 |
| 引擎 | application/services/watch_engine/engine.py | tick 接 TodoService；移除摘要门调用 |
| 状态 | application/services/watch_engine/state_manager.py | 底层换持久化 store（接口保留） |
| 判据 | application/services/watch_engine/trigger_judge.py | 冷却基准读写走 store |
| 升级 | application/services/watch_engine/escalation_coordinator.py | 删除四类，保留宪法级 + 异常波动 + 显式声明 |
| 升级 | domain/watch/services/escalation_checker.py | 移除量能/共振/核心区域/频率判定 |
| 处置 | domain/watch/services/disposition.py | 改为产出 level + owner，而非「叫不叫 agent」 |
| 处置 | application/services/watch_engine/disposition_engine.py | 组装 level/owner 上下文 |
| 通知 | application/services/watch_engine/notifier.py | 按级别选模板；接回执 |
| 路由 | adapters/inbound/fastapi_app/routes/watch_async.py | digest 转只读；统计口径修复（先过滤后分页） |
| 装配 | application/services/watch_engine/factory.py | 注入 todo/自愈/运行态依赖；开关 |
| 调度 | adapters/inbound/fastapi_app/daily_jobs_bootstrap.py | 注册 SLA 巡检与心跳任务；健康检查收口到 domain |
| 通知门面 | application/notification/notification_facade.py | 注入 account_total；接通 target_agent |
| 频道策略 | domain/notification/policies/watch_channel_policy.py | 金额门生效 |
| 持仓联动 | application/services/watch_engine/position_lifecycle_service.py | 账户范围按规则归属逐账户解析（P0 修复） |
| 市场级 | application/services/watch_engine/market_watch_service.py | 并入待办通道（不再只落库不通知） |
| 仓储 | adapters/outbound/repositories/watch_rule_repository.py | 统计口径修复；抑噪字段读写 |
| ORM | infrastructure/persistence/orm/models/watch_state.py | 加列同步 |

### 1.3 删除（Delete）

| 模块 | 路径 | 理由 |
|------|------|------|
| 摘要门 | application/services/watch_engine/digest_service.py | 由 TodoService + WatchSlaJob 取代（转只读保留一版过渡） |
| 健康度死代码 | domain/watch/services/rule_health_checker.py | 线上为 inbound 内联重实现，两份真相 |
| 元触发 | application/services/watch_engine/meta_review_service.py | 并入 NoiseSelfHealService |

## 2. 批次与依赖

- **批次 A（可并行）**：t1 数据层、t2 判据 metric 化、t4 级别与路由
- **批次 B**：t3（依赖 t1）、t5（依赖 t1,t4）、t7（依赖 t2）
- **批次 C**：t6（依赖 t5）、t8（依赖 t5）、t9（依赖 t4）、t10（依赖 t3）
- **批次 D**：t11（依赖 t1,t5）、t12（依赖 t6–t11 全部）

## 3. 任务卡清单

见 plan.md 第 4 节（12 张），每张含做什么/怎么做/可证伪验收/依赖；本拆分阶段已按同 key 落库。

## 4. 风险与验证

| 风险 | 验证方式 |
|------|----------|
| 判据改造引入回归 | t2 的 #162 场景故障注入 + watch 全量测试零新增失败 |
| 强制晋升推高唤醒量 | t8 抑噪 + t12 场景矩阵观察待办规模 |
| 迁移伤到线上数据 | t11 幂等断言 + 未收敛数为 0 + 回滚演练记录 |
| 账户越权 | t8 的 403 断言 + t4 路由真值表 |
