# t-4dae3e 规则自愈

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
规则自愈

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
运行 python -m pytest tests/application/test_self_heal.py 通过；断言超阈值后新触发 suppressed=true 且不建 todo；断言修规则 todo 存在；断言改用户账户规则返回 403

## 实施方案（implementation）
NoiseSelfHealService：按日聚合统计→抑噪（suppress_until + P3）→建修规则 todo；POST /api/watch/rules/{id}/repair 落 watch_rule_changes；授权校验按账户

## 上游产出摘要（dependsSummary）
- TodoService 与仓储端口

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T18:01:46.311Z，窗口 session-9b2b54f3-a3f4-4087-84f4-d1038fd1dd98）

规则自愈闭环落地：noise_policy 纯函数判据（单日≥8 或 连续≥3日日均≥4）+ 抑噪三件套（置抑噪态/建修规则待办/写审计）+ 授权修复接口 + 触发摄入路径抑噪短路（suppressed=true 且不建 todo）。主 agent 独立探针复核通过。

### 完成项

- domain/watch/services/noise_policy.py（新增）：should_suppress（阈值=模块常量且可覆写）、REPAIR_ACTIONS、suppress_until/is_suppressed（now 注入、不读时钟不读库）、日聚合纯计算
- domain/watch/ports.py：IWatchRuleChangeRepository + IWatchRuleNoiseRepository + 5 个领域异常
- adapters/outbound/repositories/watch_rule_change_repository.py（新增）：审计追加写（reason 空→响亮拒绝）+ 日幂等查询；watch_rule_noise_repository.py（清单外新增，已批准）：noise 列读写 + watch_triggers 按日聚合
- application/services/watch_engine/noise_self_heal_service.py（新增）：scan 抑噪三件套（置态+建 P1/rule_change 待办+写 system 审计）；apply_repair 授权校验（用户账户规则 agent 变更→403）+ 动作白名单 + reason 必填 + 清抑噪；日幂等
- adapters/inbound/fastapi_app/routes/watch_rule_repair_async.py（新增）：GET /noise、POST /repair（200/400/403/404），不注册 main.py
- 【偏差1 已补齐·第二轮】watch_rule_repository.py 补 noise_state/suppress_until/suppressed 列映射 + record(suppressed=...)（位置参数未动，零破坏）；engine.tick 抑噪短路口——不升级/不进摘要队列/不建待办/不记介入账本，只落 suppressed=true + auto_observed + 理由
- 测试：tests/domain/test_noise_policy.py（35）+ tests/application/test_self_heal.py（45）= 80 passed，含 3 个真库端到端用例（不建 todo 以 watch_todos 计数不变为机械证据）
- 子代理变异测试 5 处（阈值 8→7 / 抹授权校验 / 抹日幂等 / 抑噪短路 if False / suppressed 写 False）均能变红，改回全绿 → 用例有牙
- 主 agent 独立探针（不依赖其测试）：抑噪期 notify=0、落库 suppressed=True、disposition=auto_observed、理由含「抑噪期/修规则」、事件 suppressed=True；抑噪过期与无抑噪态均恢复推送 → 缺口确已堵上
- 主 agent 复核：门槛回归 311 passed（排除两个已知脆弱文件）；批准保留其 3 处超范围（策略账户也判 403、trigger_days 口径、清单外新增 noise 仓储）

### 改动文件

- `quantsys-v2/domain/watch/services/noise_policy.py`
- `quantsys-v2/domain/watch/ports.py`
- `quantsys-v2/adapters/outbound/repositories/watch_rule_change_repository.py`
- `quantsys-v2/adapters/outbound/repositories/watch_rule_noise_repository.py`
- `quantsys-v2/application/services/watch_engine/noise_self_heal_service.py`
- `quantsys-v2/adapters/inbound/fastapi_app/routes/watch_rule_repair_async.py`
- `quantsys-v2/adapters/outbound/repositories/watch_rule_repository.py`
- `quantsys-v2/application/services/watch_engine/engine.py`
- `quantsys-v2/tests/domain/test_noise_policy.py`
- `quantsys-v2/tests/application/test_self_heal.py`

### 下一步

t12 接线：①NoiseSelfHealService.scan 挂到定时任务 ②规则修复/判据路由注册 ③close 响应补 receipt ④真实 apply 收敛 172 条积压后开 WATCH_TODO_ENABLED

---
