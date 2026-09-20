# REQ-c9f899 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v2

**交付结论**：返工 v2：用户指定的 4 项已知未闭环已修完并逐项验证——①target_agent 从"物理不可达"变为"跨 agent 可达"（打桩实测 POST 到 dh:13080 / ts:3002；dh 内仍不按 target 分窗口，已如实标注）②影子起始时间落库（真库迁移 7→0 变更，库优先/env 兜底）③去重窗/事件窗/velocity 跨重启持久化（3 张新表 + 有界恢复裁剪）④测试基础设施：真门禁（不再排除任何文件）连跑 3 次 401 passed 零漂移，从零库可同步出 8 表 10 列。**返工期主 agent 另修复子代理交付中的 3 处缺陷**（dry_run 判定位置、tz-aware 泄漏致告警 TypeError、两处过时注释）。

## 1. 验收列表

### v2-1 · 新增四张表与两表加列

**验收内容**：运行 python -m pytest tests/ -k watch 零新增失败；迁移脚本连续执行两次，第二次返回 0 变更；断言 information_schema 中四张新表与新增列存在且约束一致

**操作步骤**：
1. 运行 python -m pytest tests/ -k watch 零新增失败
2. 迁移脚本连续执行两次，第二次返回 0 变更
3. 断言 information_schema 中四张新表与新增列存在且约束一致

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/ -k watch 零新增失败；迁移脚本连续执行两次，第二次返回 0 变更；断言 information_schema 中四张新表与新增列存在且约束一致

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-2 · 判据 metric 化并建立消费侧契约

**验收内容**：运行 python -m pytest tests/services/test_metric_contract.py 通过；断言 price_break 命中的 result.metric == price；误用 metric 时抛出 watch_metric_contract_violation（断言拒绝而非静默）；规则 #162 场景回归断言不含「量能异常」

**操作步骤**：
1. 运行 python -m pytest tests/services/test_metric_contract.py 通过
2. 断言 price_break 命中的 result.metric == price
3. 误用 metric 时抛出 watch_metric_contract_violation（断言拒绝而非静默）
4. 规则 #162 场景回归断言不含「量能异常」

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/services/test_metric_contract.py 通过；断言 price_break 命中的 result.metric == price；误用 metric 时抛出 watch_metric_contract_violation（断言拒绝而非静默）；规则 #162 场景回归断言不含「量能异常」

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-3 · 运行态持久化与启动恢复

**验收内容**：运行 python -m pytest tests/services/test_runtime_state.py 通过；重启进程后同一规则触发间隔 ≥ cooldown（断言不推送）；写库失败时 tick 不崩溃且返回降级标记

**操作步骤**：
1. 运行 python -m pytest tests/services/test_runtime_state.py 通过
2. 重启进程后同一规则触发间隔 ≥ cooldown（断言不推送）
3. 写库失败时 tick 不崩溃且返回降级标记

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/services/test_runtime_state.py 通过；重启进程后同一规则触发间隔 ≥ cooldown（断言不推送）；写库失败时 tick 不崩溃且返回降级标记

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-4 · 级别判定与账户路由纯函数

**验收内容**：运行 python -m pytest tests/domain/test_level_router.py 通过；真值表逐行断言一致；断言 agent 账户返回 autonomous、用户账户返回 remind_only、空账户返回数据缺陷标记

**操作步骤**：
1. 运行 python -m pytest tests/domain/test_level_router.py 通过
2. 真值表逐行断言一致
3. 断言 agent 账户返回 autonomous、用户账户返回 remind_only、空账户返回数据缺陷标记

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/domain/test_level_router.py 通过；真值表逐行断言一致；断言 agent 账户返回 autonomous、用户账户返回 remind_only、空账户返回数据缺陷标记

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-5 · TodoService 与仓储端口

**验收内容**：运行 python -m pytest tests/application/test_todo_service.py 通过；断言 ignored 缺 next_condition 时返回 400 拒绝；断言 L3 的 trade 缺 decision_audit_id 返回 400 拒绝；断言重复关闭返回 409

**操作步骤**：
1. 运行 python -m pytest tests/application/test_todo_service.py 通过
2. 断言 ignored 缺 next_condition 时返回 400 拒绝
3. 断言 L3 的 trade 缺 decision_audit_id 返回 400 拒绝
4. 断言重复关闭返回 409

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/application/test_todo_service.py 通过；断言 ignored 缺 next_condition 时返回 400 拒绝；断言 L3 的 trade 缺 decision_audit_id 返回 400 拒绝；断言重复关闭返回 409

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-6 · 到期巡检任务

**验收内容**：运行 python -m pytest tests/application/test_sla_job.py 通过；造超时待办后 1 分钟内断言 flow_state 晋升；断言已在 L3 超时则写 timeout 回执存在

**操作步骤**：
1. 运行 python -m pytest tests/application/test_sla_job.py 通过
2. 造超时待办后 1 分钟内断言 flow_state 晋升
3. 断言已在 L3 超时则写 timeout 回执存在

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/application/test_sla_job.py 通过；造超时待办后 1 分钟内断言 flow_state 晋升；断言已在 L3 超时则写 timeout 回执存在

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-7 · 升级策略收敛

**验收内容**：grep application/services/watch_engine 断言 volume_ratio/multi_rule_confluence/core_zones/触发频率 分支命中数为 0；运行 python -m pytest tests/services/test_escalation_checker.py 通过；断言宪法级不受预算限制

**操作步骤**：
1. grep application/services/watch_engine 断言 volume_ratio/multi_rule_confluence/core_zones/触发频率 分支命中数为 0
2. 运行 python -m pytest tests/services/test_escalation_checker.py 通过
3. 断言宪法级不受预算限制

**预期结果**：按上述步骤执行后满足验收标准：grep application/services/watch_engine 断言 volume_ratio/multi_rule_confluence/core_zones/触发频率 分支命中数为 0；运行 python -m pytest tests/services/test_escalation_checker.py 通过；断言宪法级不受预算限制

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-8 · 规则自愈

**验收内容**：运行 python -m pytest tests/application/test_self_heal.py 通过；断言超阈值后新触发 suppressed=true 且不建 todo；断言修规则 todo 存在；断言改用户账户规则返回 403

**操作步骤**：
1. 运行 python -m pytest tests/application/test_self_heal.py 通过
2. 断言超阈值后新触发 suppressed=true 且不建 todo
3. 断言修规则 todo 存在
4. 断言改用户账户规则返回 403

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/application/test_self_heal.py 通过；断言超阈值后新触发 suppressed=true 且不建 todo；断言修规则 todo 存在；断言改用户账户规则返回 403

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-9 · 按级别投递模板与路由修复

**验收内容**：运行 python -m pytest tests/notification/test_watch_templates.py 通过；断言四类模板首行包含「标的+现价+动作」；断言金额门与 target_agent 分支被命中

**操作步骤**：
1. 运行 python -m pytest tests/notification/test_watch_templates.py 通过
2. 断言四类模板首行包含「标的+现价+动作」
3. 断言金额门与 target_agent 分支被命中

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/notification/test_watch_templates.py 通过；断言四类模板首行包含「标的+现价+动作」；断言金额门与 target_agent 分支被命中

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-10 · 最小观测：心跳与影子超期告警

**验收内容**：运行 curl -s localhost:5001/api/watch/metrics 断言返回 heartbeat_age_sec；停写心跳 4 分钟后断言通知 sent 可见；运行 python -m pytest tests/jobs/test_heartbeat.py 通过

**操作步骤**：
1. 运行 curl -s localhost:5001/api/watch/metrics 断言返回 heartbeat_age_sec
2. 停写心跳 4 分钟后断言通知 sent 可见
3. 运行 python -m pytest tests/jobs/test_heartbeat.py 通过

**预期结果**：按上述步骤执行后满足验收标准：运行 curl -s localhost:5001/api/watch/metrics 断言返回 heartbeat_age_sec；停写心跳 4 分钟后断言通知 sent 可见；运行 python -m pytest tests/jobs/test_heartbeat.py 通过

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-11 · 迁移脚本、开关与灰度演练

**验收内容**：运行迁移脚本后断言未收敛积压数返回 0；连续执行两次第二次返回 0 变更；开关回滚演练记录写入 docs/requirements/REQ-c9f899/implementation.md

**操作步骤**：
1. 运行迁移脚本后断言未收敛积压数返回 0
2. 连续执行两次第二次返回 0 变更
3. 开关回滚演练记录写入 docs/requirements/REQ-c9f899/implementation.md

**预期结果**：按上述步骤执行后满足验收标准：运行迁移脚本后断言未收敛积压数返回 0；连续执行两次第二次返回 0 变更；开关回滚演练记录写入 docs/requirements/REQ-c9f899/implementation.md

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-12 · 引擎接线与端到端验收

**验收内容**：运行 python -m pytest tests/ -k watch 全量通过且 domain 失败集合与基线一致；场景矩阵 e2e 逐格断言通过；端到端脚本断言待办终态为 handled 或 ignored 可查

**操作步骤**：
1. 运行 python -m pytest tests/ -k watch 全量通过且 domain 失败集合与基线一致
2. 场景矩阵 e2e 逐格断言通过
3. 端到端脚本断言待办终态为 handled 或 ignored 可查

**预期结果**：按上述步骤执行后满足验收标准：运行 python -m pytest tests/ -k watch 全量通过且 domain 失败集合与基线一致；场景矩阵 e2e 逐格断言通过；端到端脚本断言待办终态为 handled 或 ignored 可查

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v2-13 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与技术设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与技术设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与技术设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 真门禁（不 ignore 任何文件）连跑 3 次：pytest tests/ -k watch -q => 401 passed ×3，逐轮零漂移（改动前同一命令 355 passed 且 run2/3 必红）
- 给定门禁（排除两个原脆弱文件）连跑 3 次：395 passed ×3
- A 线：pytest tests/notification/test_watch_target_routing.py => 15 passed；打桩 requests.post 实测 target=agent-ts → POST http://127.0.0.1:3002/wake（data.target_agent=agent-ts），agent-dh → :13080；变异两处（删 target 传递 8 failed / error 当成功 3 failed）
- BC 线：pytest tests/services/test_runtime_complete.py tests/application/test_shadow_clock_persist.py => 31 passed；变异两处（关去重窗恢复 2 failed / 不写 shadow_since 4 failed）
- 真库迁移 20260918b：第 1 次 7 变更、第 2 次 0 变更；新增 watch_runtime_dedup / watch_trigger_events / watch_price_history + digest_shadow_since 列 + 3 索引
- D 线：从零一次性库跑 sync_test_schema => tables_created 8、present 8/8 表、10/10 列、missing=[]（不依赖任何既有测试）
- D 线变异两处：关掉 e2e 清场 + 预置 7 条残留 → run2 红（assert deduped in (escalated,pending)）；sync_test_schema 改坏 → 6 errors
- tests/test_orm_db_drift.py => 6 passed（同步补上此前缺失的 t3 表与列）
- 主 agent 修复的 3 处缺陷：①dry_run 判定位置（非影子仍返回旧值）②tz-aware 出口致 evaluate_shadow_overdue 相减 TypeError（会打挂影子超期告警）③main.py / watch_metrics_async.py 两处过时注释；修后影子用例 14 passed、门槛 395 passed / 0 failed
- 诚实边界（仍在，未消失）：①dh 侧 wake-webhook 不按 data.target_agent 二次分流（跨 agent 通、dh 内不分窗口）②串行锁无法约束独立进程对同一 quant_test 的写入（共享测试库的根因无法从测试侧完全消除）③migration 测试的 converge 按设计扫描全表，会顺带收敛别的残留 ④tests/domain 有 5 个既有失败（domain/events 2 + domain/memory 3），与本需求无关、未修（超范围）

## 3. 文档完整性检查

✗ 缺失：reviews/（评审报告，非空）
✗ 缺失：tests/（测试证据，非空）

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v2-1 | 新增四张表与两表加列 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:58 |
| v2-2 | 判据 metric 化并建立消费侧契约 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:58 |
| v2-3 | 运行态持久化与启动恢复 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:58 |
| v2-4 | 级别判定与账户路由纯函数 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:58 |
| v2-5 | TodoService 与仓储端口 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:58 |
| v2-6 | 到期巡检任务 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:59 |
| v2-7 | 升级策略收敛 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:59 |
| v2-8 | 规则自愈 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:59 |
| v2-9 | 按级别投递模板与路由修复 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:59 |
| v2-10 | 最小观测：心跳与影子超期告警 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 16:59 |
| v2-11 | 迁移脚本、开关与灰度演练 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 17:00 |
| v2-12 | 引擎接线与端到端验收 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 17:00 |
| v2-13 | 需求级验收 | ✓ 通过 | human/session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98 | 2026-09-20 17:00 |
