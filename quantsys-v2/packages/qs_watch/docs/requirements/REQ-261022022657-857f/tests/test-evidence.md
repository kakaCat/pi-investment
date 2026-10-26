# 测试证据（REQ-261022022657-857f）

日期：2026-10-22 · 环境：quantsys-v2 / quant_test · 无迁移（schema 未变）

covers: t-e12dcf, t-e481c3, t-558de7, t-a5fbed, t-b65fd2, t-eec5ea, t-887e9b, t-4b43e8, t-c0b38b, t-6d5405, t-4c1d31, t-1088bf, t-1b778c, t-ebde4d, t-4d4ec2, t-46d7fb, t-077bfc, t-a779d3, t-d2e75b, t-35badf, t-c02f99, t-e5df78, t-f9b1f4, t-08f77b

## 1. 计划域全量（含本轮新增用例）

```bash
./venv/bin/python -m pytest tests/plan -q
# 139 passed in 0.77s
```

| 新增/变更文件 | 覆盖卡 | 用例数 |
|---|---|---|
| tests/plan/test_reflection_job.py（追加 3 例） | t-e12dcf, t-eec5ea, t-c0b38b | 8 |
| tests/plan/test_plan_batch_convergence.py（新增） | t-e481c3, t-558de7, t-6d5405, t-1b778c | 11 |
| tests/plan/test_news_exit_linkage.py（新增，回归既有 69b8 链路） | t-a5fbed, t-a779d3, t-c02f99 | 5 |
| tests/plan/test_metrics_ext.py（新增） | t-b65fd2, t-e5df78, t-08f77b | 3 |

## 2. watch 既有套件（回归）

```bash
./venv/bin/python -m pytest tests -k watch -q
# 791 passed / 2 failed in 172.82s
# FAILED tests/application/test_watch_t12_todo_creation.py::test_p2_trigger_creates_todo_l1_due_day_close
# FAILED tests/application/test_watch_t12_todo_creation.py::test_deduped_trigger_does_not_create_todo
```

两例与开工前基线同名同因（预存红），本轮无新增红。covers: t-b65fd2, t-08f77b

## 3. 生产读数（重启后实测）

```bash
curl -s http://127.0.0.1:5001/api/watch/metrics
# news_todos_today = 0（当日尚无 critical 命中，字段可用）
# reflection_woken_today = 0（当日尚未到 15:35 反思窗口）
# pending_todos = 2 / engine_alive = True
```

covers: t-b65fd2, t-e5df78

## 4. 三条读数样例

- 批次进度：`select detail from quant.trading_plan_events where kind='fill' order by id desc limit 5;`（detail.batch/retired）
- 消息待办：`select id, level, evidence->>'source' from quant.watch_todos where evidence->>'source'='news' order by id desc limit 5;`
- 反思唤醒：metrics 的 reflection_woken_today，或 `select result->>'woken' from quant.scheduler_runs where task_id in (select id from quant.scheduler_tasks where name like 'plan_reflect%') order by id desc limit 3;`

covers: t-b65fd2

## 5. 口径说明（如实登记）

- 批次匹配按「累计卖出比例 ≤ 有效批次比例」判定：sold_ratio=0.8 时仅退役第 1 批（第 2 批只完成 47%，不臆造退役）；原计划文本写 [0,1] 已在实施期修订验收口径。
- FR-3（消息→离场）由 REQ-261021194640-69b8 实现，本轮只补回归，未改其代码。
