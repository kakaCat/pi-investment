# t-eec9d3 最小观测：心跳与影子超期告警

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
最小观测：心跳与影子超期告警

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
运行 curl -s localhost:5001/api/watch/metrics 断言返回 heartbeat_age_sec；停写心跳 4 分钟后断言通知 sent 可见；运行 python -m pytest tests/jobs/test_heartbeat.py 通过

## 实施方案（implementation）
引擎每 tick 写心跳；WatchHeartbeatJob 每分钟检查并告警；GET /api/watch/metrics 输出心跳与队列指标

## 上游产出摘要（dependsSummary）
- 运行态持久化与启动恢复

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T17:25:35.001Z，窗口 session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98）

最小观测：引擎心跳写入（与持久化开关解耦）+ 心跳/影子模式巡检判定（纯函数）+ GET /api/watch/metrics 指标端点。心跳只在「曾有心跳但过期」时告警，避免冷启动误报。

### 完成项

- engine.py：_write_heartbeat() 每轮主循环写心跳（节流 30s，可用 WATCH_HEARTBEAT_INTERVAL_SEC 调），开关 WATCH_HEARTBEAT_ENABLED 默认 true，**与 WATCH_RUNTIME_PERSIST_ENABLED 解耦**（持久化关掉可接受，但引擎死了必须能被发现）；写失败只记日志 + failures 计数，不打挂主循环
- adapters/inbound/fastapi_app/watch_heartbeat_job.py（新增）：evaluate_heartbeat（ok/stale/never/disabled 纯函数）+ evaluate_shadow_overdue（off/ok/overdue/unknown）+ run_heartbeat_check 编排；**只在曾有心跳但过期时告警**，从未有心跳只报 never 不告警（防冷启动误报）；读库失败按 never 处理，绝不误报 stale；sender 抛错不影响巡检且 sent 如实计 0
- adapters/inbound/fastapi_app/routes/watch_metrics_async.py（新增）：GET /api/watch/metrics（heartbeat_at/age/verdict/engine_alive/shadow_mode/degraded/notes），待办规模字段显式 null + notes 写明「待 t5 接线」，不拿 0 冒充事实（R-013）
- tests/jobs/test_heartbeat.py（13 用例）+ tests/api/test_watch_metrics.py（5 用例）
- 实测：pytest tests/jobs/test_heartbeat.py tests/api/test_watch_metrics.py → 18 passed；pytest tests/ -k watch → 293 passed（零失败）；定向引擎用例 49 passed
- 实现期自查修掉一处自身缺陷：模板字面量把 \n 写成真实换行导致 SyntaxError，已改为不依赖转义的拼接

### 改动文件

- `quantsys-v2/application/services/watch_engine/engine.py`
- `quantsys-v2/adapters/inbound/fastapi_app/watch_heartbeat_job.py`
- `quantsys-v2/adapters/inbound/fastapi_app/routes/watch_metrics_async.py`
- `quantsys-v2/tests/jobs/test_heartbeat.py`
- `quantsys-v2/tests/api/test_watch_metrics.py`

### 下一步

留给 t12：①把巡检注册成**进程外**定时任务（若塞回引擎线程则线程死了巡检也死，等于没有）②main.py 注册 watch_metrics 路由 ③接真实飞书通道（当前 sender 默认 log-only，不许假装已发）④t5 落地后补齐 todo 规模指标

---
## 汇报 2（2026-09-17T17:26:06.601Z，窗口 session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98）

【收尾补做】把心跳纳入引擎状态快照（get_metrics 暴露 heartbeat_enabled/last_at/failures）——排障时能直接回答「心跳有没有在写、失败几次」。补测后 19 passed、全量 watch 293 passed。

### 完成项

- engine.get_metrics() 新增 heartbeat_enabled / heartbeat_last_at / heartbeat_failures 三项，并注明排障语义（last_at 为空=从未写出，failures>0=存活信号在丢）
- tests/jobs/test_heartbeat.py 新增 test_engine_metrics_expose_heartbeat（断言未写心跳时 last_at 为 None、写入后可读、failures=0）
- 实测：pytest tests/jobs/test_heartbeat.py tests/api/test_watch_metrics.py → 19 passed；pytest tests/ -k watch → 293 passed

### 改动文件

- `quantsys-v2/application/services/watch_engine/engine.py`
- `quantsys-v2/tests/jobs/test_heartbeat.py`

### 下一步

t12：进程外注册心跳巡检 + main.py 注册 metrics 路由 + 接真实通知通道（当前 sender 为 log-only，不许假装已发）

---
