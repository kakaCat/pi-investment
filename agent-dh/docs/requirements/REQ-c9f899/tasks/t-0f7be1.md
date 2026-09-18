# t-0f7be1 引擎接线与端到端验收

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
引擎接线与端到端验收

## 背景摘要（context）
（待补充）

## 范围
- 阶段：test
- 端侧：fullstack

## 验收标准
运行 python -m pytest tests/ -k watch 全量通过且 domain 失败集合与基线一致；场景矩阵 e2e 逐格断言通过；端到端脚本断言待办终态为 handled 或 ignored 可查

## 实施方案（implementation）
engine.tick 接入 TodoService；digest 摘要门转只读；跑场景矩阵 e2e 与验收脚本；输出验收证据清单到 docs/requirements/REQ-c9f899/verification.md

## 上游产出摘要（dependsSummary）
- 到期巡检任务
- 升级策略收敛
- 规则自愈
- 按级别投递模板与路由修复
- 最小观测：心跳与影子超期告警
- 迁移脚本、开关与灰度演练

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T18:14:45.599Z，窗口 session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98）

引擎接线与端到端验收：§6 接线清单 8/10 销项（余 2 项为物理不可达/超范围并已留痕），三路由注册实证、三个进程外定时任务、按级别模板接渠道、notifier 传金额门、metrics 补规模字段；并补齐「触发→建待办」这一闭环载体的关键一环。

### 完成项

- main.py：注册 watch_todo / watch_rule_repair / watch_metrics 三路由（optional，失败不阻断启动）；lifespan 调 ensure_shadow_since_env；路由实证 optional_route_failures=[]
- daily_jobs_bootstrap.py：新增进程外周期任务（心跳 60s / SLA 60s / 自愈 600s）+ interval_due 纯函数；宿主线程独立于 watch-engine（不塞回引擎线程）
- watch_loop_wiring.py（新）：开关读取 + 唯一装配函数（runtime store/todo/receipt/self-heal/SLA），factory 与定时任务共用；watch_channels.py（新）：心跳/回执真实 NotificationFacade sender（失败抛错不静默）；shadow_mode_clock.py（新）
- factory.py：抽出 build_watch_loop_services()（默认全 None；开关开时装配注入）；notifier.py 新增 account_total_provider 与 level 参数并透传；feishu_formatters.py 按 payload 有无 level 分流（无 level 走旧渲染，非盯盘通知不受影响）
- watch_metrics_async.py：补齐 pending_todos/by_level/by_flow_state/terminal_rate_today/suppressed_rules（失败 degraded + null，不拿 0 冒充）
- 【第二轮·补齐闭环载体】engine.tick 在处置结论后调用 _create_watch_todo：P0/P1/P2 建、**P3 不建**、deduped 不建、同 trigger_id 幂等、回填 watch_triggers.todo_id、create 抛错双保险不打挂 tick；due_at 按级别（P0+300s/P1+1800s/P2 当日 15:00）
- 测试：新增 test_watch_t12_wiring(8) / test_watch_level_channel(4) / test_watch_interval_jobs(9) / test_watch_shadow_mode_clock(5) / test_watch_t12_todo_creation(10)，更新 test_watch_metrics；门槛回归 349 passed（基线 311 → +38）
- 变异测试共 4 处（渠道分流 / 总闸默认关 / P3 守卫 / deduped 守卫）均能变红，改回全绿 → 用例有牙
- 主 agent 复核：门槛 349 passed；新增 todo 创建用例 10 passed；邻接回归 112 passed；engine 侧四道短路 + 双保险异常处理已读码确认
- 【主 agent 修的漂移】tests/test_orm_db_drift.py 基线失败（quant_test 缺 watch_receipts 等 t1 表与列）——**未用白名单掩盖**，而是把 t1 的 5 张表 + 9 列补建到 quant_test，漂移测试 6 passed
- 批准的偏差：建待办放在 notify 之后（需 trigger_id 做溯源与幂等，拆 _record 属重构）；心跳巡检挂总闸以保默认行为不变；FeishuChannel 不支持按群路由（只写频道码+urgency，未假装）

### 改动文件

- `quantsys-v2/adapters/inbound/fastapi_app/main.py`
- `quantsys-v2/adapters/inbound/fastapi_app/daily_jobs_bootstrap.py`
- `quantsys-v2/application/services/watch_engine/{watch_loop_wiring.py,watch_channels.py,shadow_mode_clock.py,factory.py,engine.py,notifier.py,dto.py}`
- `quantsys-v2/application/notification/notification_facade.py`
- `quantsys-v2/infrastructure/notification/formatters/{feishu_formatters.py,watch_level_templates.py}`
- `quantsys-v2/adapters/inbound/fastapi_app/routes/watch_metrics_async.py`
- `quantsys-v2/adapters/outbound/repositories/{watch_todo_repository.py,watch_rule_noise_repository.py,watch_rule_repository.py}`
- `quantsys-v2/tests/{application/test_watch_t12_todo_creation.py,application/test_watch_t12_wiring.py,notification/test_watch_level_channel.py,jobs/test_watch_interval_jobs.py,application/test_watch_shadow_mode_clock.py,api/test_watch_metrics.py}`

### 下一步

切换闸门（父 agent 执行、需用户同意）：重启后端 → 真实 apply 收敛 172 条 → 翻 WATCH_TODO_ENABLED/WATCH_SELF_HEAL_ENABLED → 真开唤醒（建议先只对 agent_brain）

---
