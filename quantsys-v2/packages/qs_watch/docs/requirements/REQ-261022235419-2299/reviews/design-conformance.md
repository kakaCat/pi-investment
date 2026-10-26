---
req_id: REQ-261022235419-2299
doc: review
title: V2 实施与设计一致性复核
created: 2026-10-23
---

# V2 实施与设计一致性复核

## 复核范围

对照 `design/` 六份文档逐条核对 `watch_engine/v2/` 实现。

## 文件边界（backend.md「独立文件边界」）

| 设计约束 | 实现核查 | 结论 |
|---|---|---|
| V2 全部新代码在 v2/ 子包 + tests/v2/ | 10 个模块 + 7 个测试文件全部落在这两处 | ✅ |
| 不改 V1 逻辑 | V1 `watch_engine/core/` 零改动；仅在宿主层加 V2 分支 | ✅ |
| 仅 3 处接入点只加不改 | ①main.py lifespan 加 V2 块 ②daily_jobs/registry.py 加 1 条 JobDef ③新建迁移 | ✅ |

## 黑盒复用（backend.md 复用清单）

| 复用项 | 实现方式 | 结论 |
|---|---|---|
| 规则加载 | `rule_repo.list_by_state('active')` 注入，不读实现 | ✅ |
| 实时取价 | `quote_service.get_realtime_quote(symbol)` 注入 | ✅ |
| 条件求值 DSL | `from ..rules.conditions import evaluate` 只调接口 | ✅ |
| 通知发送 | sender 回调注入（生产接 qs_notification facade），未接线不伪造成功 | ✅ |

## 接口契约（interfaces.md）

| 接口 | 实现 | 错误语义 | 结论 |
|---|---|---|---|
| IF-1 load_active_rules | engine.py | 异常→空集 | ✅ |
| IF-2 fetch_quotes | engine.py | 单票失败→None fail-open | ✅ |
| IF-3 check_invalidation | invalidation.py | 无价/缺阈值→跳过 | ✅ |
| IF-4 position_engine.evaluate | position_engine.py | 状态不可知→止损 fail-open | ✅ |
| IF-5 unpositioned_engine.evaluate | unpositioned_engine.py | 同上 | ✅ |
| IF-6 route_trigger | router.py | 读失败→按首发 | ✅ |
| IF-7 notify_agent.send | notify_agent.py | False + 补发 | ✅ |
| IF-8 notify_feishu.send | notify_feishu.py | False + 补发 | ✅ |
| IF-9 reset_daily_cycles | router.py + repo.reset_all_cycles | 部分失败记日志继续 | ✅ |

## 偏离与处理

| 偏离 | 原因 | 处置 |
|---|---|---|
| `staged_break` 条件 V2 暂不评估 | 有状态条件需 StagedBreakManager 驱动，V1 亦在引擎 tick 内拦截 | 标 `degraded=True` 不误判；后续卡接入 |
| `watch_triggers.engine` 列迁移时漏加 | 初次只加 watch_rules.engine | 已在迁移补 `ALTER TABLE watch_triggers`，双库 apply 验证 |
| 判定链 ctx 缺省构造 | engine 调用时未传 EvalContext | 两个 engine 内统一构造最小 ctx（cost_price 转 float 避 Decimal 运算错误） |

## 结论

设计与实现一致；三处偏离均已处置或标 degraded，无未记录行为。
