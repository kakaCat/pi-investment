# REQ-c9f899 验收（verification）

> 自动生成于 reqboard_verify_submit

## 验收结论
盯盘引擎重构（触发-判据-投递-生命周期）12 个任务全部交付：判据 metric 化（根治「现价当量比」）、升级策略收敛为三条可信路径、闭环待办化（L1→L2→L3 + 到期机械晋升 + 三段回执）、4 档分级与按级别飞书模板、规则自愈（反复触发→抑噪+修规则待办）、运行态持久化（冷却跨重启有效）、最小观测（心跳+指标）。门槛回归 349 passed；累计 4 处变异测试证明用例有牙；真库 dry-run 演练识别 172 条积压全部可收敛。**已知未闭环 4 项**（诚实列出，见 evidence 末条）：target_agent 底层物理不可达（未假装接通）、影子起始时间仅 env 兜底未落库、去重窗/velocity 历史未跨重启持久化、测试基础设施欠账（共享 quant_test 导致并发漂移）。**切换动作（重启+真实 apply+翻开关+真开唤醒）有意未执行**，属不可逆操作，待用户同意。

## 证据清单
- 门槛回归：cd <worktree>/quantsys-v2 && venv/bin/python -m pytest tests/ -k watch -q --ignore=tests/e2e/test_watch_engine_flow_e2e.py --ignore=tests/migration/test_watch_backlog_convergence.py => 349 passed, 5966 deselected（基线 311 → +38）
- 各任务单测：test_metric_contract 11 passed / test_escalation_checker+metric 20 passed / test_level_router 49 passed / test_runtime_state 23 passed / test_todo_service 26 + test_watch_todo_routes 20 / test_sla_job 24 / test_noise_policy 35 + test_self_heal 45 / test_heartbeat 14 + test_watch_metrics 5 / t12 新增 36
- 变异测试（证明非烟雾）：t4 级别守卫→2+3 failed；t6 幂等/晋升→4+5 failed；t8 阈值/授权/幂等/抑噪短路/suppressed 写入→5 处均红；t12 渠道分流/总闸默认关/P3 守卫/deduped 守卫→4 处均红；全部改回后绿
- 迁移幂等：scripts 执行 20260918_watch_todo_loop.py 两次 => 首次 20 变更、第二次 0 变更；information_schema 断言 5 表 9 列 6 索引 10 约束
- 旧账收敛：真库 dry-run => scanned=172 / todos_created=172 / expired=0 / errors=0 / orphaned=172；测试库 apply => orphaned_scoped=0 且二次运行 changed=0（幂等）
- ORM↔DB 漂移：把 t1 的 5 表 9 列补建到 quant_test 后 pytest tests/test_orm_db_drift.py => 6 passed（未用白名单掩盖真漂移）
- 路由注册实证：递归 original_router 列出 /api/watch/todos、/todos/{id}/claim、/todos/{id}/close、/rules/{id}/noise、/rules/{id}/repair、/metrics；optional_route_failures=[]
- 定时任务进程外：daily_jobs_bootstrap 新增心跳 60s / SLA 60s / 自愈 600s，宿主线程独立于 watch-engine（不塞回引擎线程——否则线程死了巡检也死）
- 闭环载体：engine.tick 处置结论后 _create_watch_todo（P0/P1/P2 建、P3 与 deduped 不建、同 trigger_id 幂等、回填 watch_triggers.todo_id、异常双保险）+ test_watch_t12_todo_creation 10 passed
- 主 agent 独立探针（不依赖子代理测试）：级别路由真值表 8 项、TodoService 校验 10 项、抑噪摄入路径 3 场景、冷却窗边界 10/299/400s、心跳/告警 4 态 —— 全部与契约一致
- 回滚演练：WATCH_RUNTIME_PERSIST_ENABLED=true => 317 passed；WATCH_HEARTBEAT_ENABLED=false => 19 passed（首轮 4 红，已修用例不密封问题）；默认全关 => 317 passed
- **已知未闭环（必须让验收人看到）**：① §6-3 target_agent 真实路由底层物理不可达（Agent OS SendRequest 无 per-agent 字段），已留证据与 TODO，未假装接通 ② 影子起始时间仅进程 env 兜底（watch_runtime_meta 无该列，加列需迁移）③ 去重窗/触发事件窗口/velocity 价格历史未跨重启持久化 ④ 测试基础设施欠账：迁移测试与既有 e2e 依赖共享 quant_test 残留状态，并发跑会漂移（已记 implementation.md §5.2）
