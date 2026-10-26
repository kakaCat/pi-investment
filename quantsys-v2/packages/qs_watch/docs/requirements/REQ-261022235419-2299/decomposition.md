---
req_id: REQ-261022235419-2299
title: 盯盘引擎 V2 拆分计划
status: draft
created: 2026-10-23
---

# 盯盘引擎 V2 拆分计划

## 目标与做法

**目标**：按持仓驱动模型交付盯盘引擎 V2——六个独立模块（两判定 + 两通道 + 两文案）+ 主循环编排 + 数据迁移 + 测试 + 影子灰度切换，全程不改 V1 逻辑（仅 3 处接入点）。

**做法**：数据迁移先行 → 引擎骨架（加载+统一取价前置）→ 三个判定模块并行 → 路由与通道 → 宿主接入 → 单测全套 → 影子对比与灰度切换。V2 全部代码在 `watch_engine/v2/` + `tests/v2/`，黑盒复用 V1 接口（取数/仓储/facade/宿主），回滚=删目录+移除接入行。

## 任务表

| 计划 key | 任务 | phase | side | 依赖 | 验收（可执行） | 工作量 |
|---|---|---|---|---|---|---|
| t1 | 数据迁移：trigger_channel/process_state/cycle_count 三列 + engine 标记 | implement | backend | - | python 迁移 --apply 双库 VERIFY OK；psql 查三列返回 agent/pending/0 | 0.5 天 |
| t2 | v2 引擎骨架：engine.py 主循环 + load_active_rules + 统一取价前置 | implement | backend | t1 | pytest tests/v2/test_loader.py tests/v2/test_quote_first.py -q 退出码 0；取价输入集合==激活 symbol 集合断言通过 | 1 天 |
| t3 | position_engine 持仓判定（增仓/止盈/止损/减仓） | implement | backend | t2 | pytest tests/v2/test_position_engine.py -q 退出码 0：四操作各产出对应通知；止损空仓 fail-open | 1 天 |
| t4 | unpositioned_engine 非持仓判定（买入范围/观察） | implement | backend | t2 | pytest tests/v2/test_unpositioned_engine.py -q 退出码 0：买点触发/未到不触发 | 0.5 天 |
| t5 | 失效判定模块（偏离计算 + 标 invalid + 止损豁免，覆盖全激活票） | implement | backend | t2 | pytest tests/v2/test_invalidation.py -q 退出码 0：六边界（超阈标/止损豁免/未超阈/NULL/持仓/未持仓） | 1 天 |
| t6 | 触发路由：10 次循环状态机 + 每日收盘重置任务 | implement | backend | t3, t4, t5 | tests/v2/test_trigger_routing.py + test_daily_reset.py 绿：循环第1/2~9/10 次行为确定；重置生效 | 1 天 |
| t7 | notify_agent + agent_prompts（账户路由 + 按持仓×判定类型提示词） | implement | backend | t6 | pytest tests/v2/test_account_routing.py -q 退出码 0：账户 A→agent-A；两文件可 import 互不 import | 1 天 |
| t8 | notify_feishu + feishu_templates（两发群入口 + 按持仓×判定类型模板） | implement | backend | t6 | pytest tests/v2/test_message_templates.py -q 退出码 0：六类型渲染各自关键字段 | 1 天 |
| t9 | 宿主接入：watch_bootstrap V2 分支 + registry 每日任务 | implement | backend | t7, t8 | 服务重启后 V2 心跳可见（metrics）；V1 不受影响；DISABLE_WATCH_ENGINE 口径不变 | 0.5 天 |
| t10 | 单测补全 + 全量回归 | test | backend | t9 | pytest tests/v2 全绿（退出码 0）；既有 789 测试无新增失败 | 1 天 |
| t11 | 影子模式对比 + 灰度切换 | review | backend | t10 | 影子一天对比报告：判定一致率 100%（或差异逐条有解释）；灰度无异常；切换开关回滚演练 | 2 天 |

## 批次与依赖

```
批次1: t1（数据先行）
批次2: t2（骨架）
批次3: t3 ∥ t4 ∥ t5（三判定并行）
批次4: t6 → t7 ∥ t8（路由+通道）
批次5: t9 → t10（接入+测试）
批次6: t11（影子灰度）
```

## 风险

- 影子期 V1/V2 双写触发记录——engine='v2' 标记区分（t1 已含标记列）
- 统一取价性能——t2 骨架期实测 tick 耗时，超标则熔断隔离参数调优
- 循环计数并发——t6 读改写允许偶发超发（不漏判优先），行锁为备选（interfaces.md 开放问题）

## 实施方案（逐任务）

### t1 数据迁移
**改哪些文件**：新建 `infrastructure/persistence/migrations/20261023_watch_rules_v2_routing.py`（沿用 20261022 模板：ADD COLUMN IF NOT EXISTS + CHECK + 注释 + BACKFILL + VERIFY）。**步骤**：写迁移→dry-run→双库 --apply→psql 验证。**验证**：三列存在、默认值 agent/pending/0、engine 标记列就位。

### t2 v2 骨架
**改哪些文件**：新建 `watch_engine/v2/engine.py` + `tests/v2/test_loader.py` + `test_quote_first.py`。**步骤**：WatchEngineV2 类（run_forever/tick）；tick 内 list_by_state('active')→按 symbol 去重取价（复用 quote_service）；单测断言取价集合。**验证**：pytest 两文件绿。

### t3 position_engine
**改哪些文件**：新建 `v2/position_engine.py` + `tests/v2/test_position_engine.py`。**步骤**：evaluate(rule, quote, position)→四 intent 分支；止损 fail-open 留痕。**验证**：四操作单测。

### t4 unpositioned_engine
**改哪些文件**：新建 `v2/unpositioned_engine.py` + `tests/v2/test_unpositioned_engine.py`。**步骤**：evaluate→entry 买点触发/观察。**验证**：买点触发单测。

### t5 失效判定
**改哪些文件**：新建 `v2/invalidation.py` + `tests/v2/test_invalidation.py`。**步骤**：偏离计算（|现价−阈值|/阈值）比 invalidation_threshold_pct；命中标 invalid+留痕+投递（经 notify_agent，先 stub）；止损豁免。**验证**：六边界单测（沿用今日验证脚本口径）。

### t6 触发路由
**改哪些文件**：新建 `v2/router.py` + `tests/v2/test_trigger_routing.py` + `test_daily_reset.py`。**步骤**：route_trigger 读改写 cycle_count；1→agent / 2~9→skip / 10→direct 归零；reset_daily_cycles 全量清零。**验证**：循环行为单测。

### t7 notify_agent + agent_prompts
**改哪些文件**：新建 `v2/notify_agent.py` + `v2/agent_prompts.py` + `tests/v2/test_account_routing.py`。**步骤**：send() 读 prompts 注册表（持仓×判定类型）→按 WATCH_ACCOUNT_AGENT_MAP 路由→发送；处理回写 process_state。**验证**：账户路由单测 + 两文件互不 import 断言。

### t8 notify_feishu + feishu_templates
**改哪些文件**：新建 `v2/notify_feishu.py` + `v2/feishu_templates.py` + `tests/v2/test_message_templates.py`。**步骤**：send() 读模板注册表→两入口（agent 判断后 / 循环第 10 次）→复用 V1 facade 发送。**验证**：六类型渲染单测。

### t9 宿主接入
**改哪些文件**：`watch_bootstrap.py` 加 V2 分支（~5 行，WATCH_V2_ENABLED 控制）；`daily_jobs/registry.py` 加 reset 任务（1 行）；新建 `tests/api/test_watch_engine_v2_bootstrap.py`。**步骤**：照 V1 启动模式挂 V2 线程；registry 注册每日任务。**验证**：重启后 metrics 见 V2 心跳；V1 心跳并存。

### t10 单测补全 + 回归
**改哪些文件**：补 tests/v2 遗漏用例；跑全量。**步骤**：pytest tests/v2 -q；pytest tests/ -k watch 全量。**验证**：退出码 0；无新增失败。

### t11 影子 + 灰度
**改哪些文件**：新建 `scripts/compare_v1_v2.py`。**步骤**：WATCH_V2_ENABLED=false 影子跑一天；按 engine 标记对账触发记录；出对比报告；一致则切 true 灰度。**验证**：对比报告一致率；灰度一天通知正常；开关回滚演练。
