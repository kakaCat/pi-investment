# 测试证据（REQ-261021222905-6dff）

日期：2026-10-22 · 执行环境：quantsys-v2 / quant_test 库

## 1. 计划域全量

```bash
./venv/bin/python -m pytest tests/plan -q
# 113 passed in 0.65s
```

covers: t-180c05, t-350b38, t-cced59, t-efb315, t-dc17c4, t-4876f4, t-dee787,
t-dd0616, t-60bfe8, t-d6b85d, t-155457, t-fd81c5, t-89fa50, t-07abf5, t-7f6add

## 2. 逐文件覆盖

| 测试文件 | 覆盖任务 |
|---|---|
| tests/plan/test_plan_migration_contract.py | covers: t-180c05, t-223879, t-08927d |
| tests/plan/test_plan_repository.py | covers: t-350b38 |
| tests/plan/test_plan_state_machine.py | covers: t-cced59 |
| tests/plan/test_plan_service.py | covers: t-efb315 |
| tests/plan/test_plan_compiler.py | covers: t-dc17c4 |
| tests/plan/test_plan_routes.py | covers: t-4876f4 |
| tests/plan/test_plan_today.py | covers: t-dee787 |
| tests/plan/test_plan_fill_loop.py | covers: t-dd0616 |
| tests/plan/test_plan_reflections.py（含统计） | covers: t-60bfe8, t-d6b85d |
| tests/plan/test_reflection_pack.py | covers: t-d6b85d |
| tests/plan/test_reflection_job.py | covers: t-155457 |
| tests/plan/test_plan_reflections.py（反思路由） | covers: t-d6b85d |
| agent-dh packages/tools/investment/tests/trading-plan-tool.test.ts | covers: t-fd81c5 |
| agent-ts src/infrastructure/tools/__tests__/trading-plan-tool.test.ts | covers: t-fd81c5 |
| tests/plan/test_plan_evolution_consumer.py | covers: t-89fa50 |
| tests/plan/test_core_plan_adapter.py | covers: t-07abf5 |
| tests/plan/test_plan_e2e.py | covers: t-7f6add |

## 3. watch 既有套件（回归）

```bash
./venv/bin/python -m pytest tests -k watch -q
# 791 passed / 2 failed
# FAILED tests/application/test_watch_t12_todo_creation.py::test_p2_trigger_creates_todo_l1_due_day_close
# FAILED tests/application/test_watch_t12_todo_creation.py::test_deduped_trigger_does_not_create_todo
```

covers: t-7f6add

2 例为**预存红**（先于本需求存在：市场级路由跳过 sector 规则后用例未同步），本需求未新增红。

## 4. 迁移幂等（quant_test）

```bash
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261105_trading_plan.py
# summary: 5 表 · 3 列 / 2 表 · 10 约束 · 5 索引 · changes=23（dry-run 未写库）
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261105b_plan_rules_batch.py --apply --dsn <quant_test>
# VERIFY OK: column=True pk=PRIMARY KEY (plan_id, role, symbol, batch)；重跑 changes=0
PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261105c_plan_reflect_tasks.py --apply --dsn <quant_test>
# 插入 plan_reflect_daily / plan_reflect_weekly 两行；重跑 exists（幂等）
```

covers: t-180c05, t-155457

## 5. 端到端冒烟（UC-1 / UC-2）

```bash
./venv/bin/python -m pytest tests/plan/test_plan_e2e.py -q
# 1 passed
```

covers: t-7f6add, t-4876f4, t-dd0616, t-d6b85d

剧本：建计划 → 激活（watch_rules 出现 plan_id 托管规则）→ 买入回执 → holding →
清仓回执 → closed → 反思五问落库 → 已关闭计划修改被 422 拒 → 统计可读。

## 6. 双端工具契约（TC-22）

```bash
# agent-dh
npx vitest run packages/tools/investment/tests/trading-plan-tool.test.ts
# 5 passed
# agent-ts
npx jest src/infrastructure/tools/__tests__/trading-plan-tool.test.ts
# 2 passed（plan.* 15 条路由在册；PATCH 派发）
```

covers: t-fd81c5

## 7. 结构检查

- 进化消费者源码无 trading_plan 写调用（测试内源码扫描断言）——covers: t-89fa50
- qs_plan 包内零行情轮询/零下单调用（D-8：执行归 WatchEngine）——covers: t-7f6add
