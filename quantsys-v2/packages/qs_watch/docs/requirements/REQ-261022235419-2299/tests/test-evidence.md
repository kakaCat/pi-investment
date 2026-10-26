---
req_id: REQ-261022235419-2299
doc: test-evidence
title: V2 测试证据
created: 2026-10-23
---

# V2 测试证据

## 执行命令与读数（2026-10-23 实测）

| # | 命令 | 读数 | 对应 FR |
|---|---|---|---|
| 1 | `python -m pytest tests/v2 -q` | **71 passed**, 3 warnings, exit 0 | FR-1~FR-11 |
| 2 | `python -m pytest tests/api/test_watch_engine_v2_bootstrap.py -q` | **16 passed**, exit 0 | FR-1/FR-11 |
| 3 | `python -m pytest tests/ -k watch -q` | **788 passed / 3 failed**（3 项既有遗留） | 回归 |

## 逐模块覆盖

| 测试文件 | 用例数 | 覆盖点 |
|---|---|---|
| tests/v2/test_loader.py + test_quote_first.py | 8 | 激活加载、统一取价前置、取价集合==symbol 集合 |
| tests/v2/test_position_engine.py | 11 | 持仓四操作、止损空仓 fail-open、非持仓跳过 |
| tests/v2/test_unpositioned_engine.py | 6 | 买入范围触发、观察 observe_only、持仓 intent 不在此处理 |
| tests/v2/test_invalidation.py | 9 | 六边界（超阈/止损豁免/未超阈/缺阈值/持仓/未持仓同覆盖）+ 多线取最严重 |
| tests/v2/test_trigger_routing.py | 8 | 循环 1/2~9/10 次、per-rule 独立、每日重置、读失败 fail-open |
| tests/v2/test_account_routing.py | 10 | 账户→agent 路由、提示词分方案、两通道互不 import |
| tests/v2/test_message_templates.py | 13 | 六类型模板关键字段、两发群入口、互不 import |
| tests/v2/test_engine_chain.py | 6 | 端到端链路（失效短路/首发 agent/第10次直通/影子不投递/单票失败隔离） |

## 3 项失败均为既有遗留（非本次引入）

| 失败用例 | 原因 | 改造前状态 |
|---|---|---|
| test_baostock_kline_relogin::test_socket_watchdog_interrupts_blackhole | baostock 环境依赖 | 既有失败 |
| test_watch_t12_todo_creation::test_p2_trigger_creates_todo_l1_due_day_close | scope=sector 遗留（10-18 S8） | 既有失败 |
| test_watch_t12_todo_creation::test_deduped_trigger_does_not_create_todo | 同上 | 既有失败 |

## 数据层证据

```sql
-- 生产库 + quant_test 双库
select trigger_channel, process_state, cycle_count, engine from quant.watch_rules limit 1;
-- → agent / pending / 0 / v1

select column_name from information_schema.columns
 where table_schema='quant' and table_name='watch_triggers' and column_name='engine';
-- → engine
```

## 真实端到端影子跑（生产库 + 真实行情）

```
激活 53 规则 → 去重 40 symbol → 取价成功 39
判定链产出 4 条：[trigger] 300677 exit_stop / 300432 603993 600938 trend_observe
staged_break 条件标 degraded 不误判；HELD_SECTORS 伪标的 fail-open 跳过
```

## 任务覆盖矩阵（covers 标注）

- covers: t-fe91ea — 数据迁移（四列 + watch_triggers.engine），双库 apply VERIFY OK
- covers: t-b8ffa6 — v2 骨架（加载 + 统一取价前置），test_loader + test_quote_first 8 passed
- covers: t-223590 — position_engine 四操作判定，test_position_engine 11 passed
- covers: t-3fa90a — unpositioned_engine 买入/观察判定，test_unpositioned_engine 6 passed
- covers: t-443fbb — invalidation 六边界失效判定，test_invalidation 9 passed
- covers: t-5102cb — router 10 次循环 + 每日重置，test_trigger_routing 8 passed
- covers: t-33cead — notify_agent + agent_prompts，test_account_routing 10 passed
- covers: t-659001 — notify_feishu + feishu_templates，test_message_templates 13 passed
- covers: t-dc9678 — 宿主接入（bootstrap 开关 + 每日任务注册），test_watch_engine_v2_bootstrap 16 passed
- covers: t-e7ef23 — 单测补全 + 全量回归，tests/v2 71 passed + watch 全量 788 passed 无新增失败
- covers: t-999237 — 影子对比脚本 compare_v1_v2.py（灰度待上线跑一天，defer）
- covers: t-c7e0ce — 迁移研发段：migration 文件落盘 + 双库 apply（台账 6 段汇报）
- covers: t-66005a — 迁移联调段：quant_test 真实 UPDATE/SELECT 往返一致
- covers: t-1c0316 — 迁移复核段：对照 data-model.md 逐条核对无偏离（两处偏离已补）
- covers: t-a7f35a — 迁移测试段：双库 --apply 退出码 0 VERIFY OK
- covers: t-30eeaf — 骨架研发段：v2/engine.py + 两测试文件 8 passed
- covers: t-893f77 — 骨架联调段：真实 tick 53 规则 → 40 symbol → set_match=true
- covers: t-b509e4 — 骨架复核段：对照 design/ 文件边界与黑盒复用逐条无偏离
- covers: t-4b095f — 骨架测试段：终态验收两命令 8 passed exit 0
