# t-dee787 实现今日计划聚合视图

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现今日计划聚合视图

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

GET /api/plans/today 有计划时返回 targets 与 env_gate verdict；无计划 200+empty=true；P95<500ms。验证：① `./venv/bin/python -m pytest tests/plan/test_plan_today.py -q`（5 passed）；② 路由冒烟 `curl -s 'http://127.0.0.1:5001/api/plans/today?account=agent_brain'` 应返回 success=true 且含 plans/env_gate 字段；空账户返回 empty=true；③ `./venv/bin/python -m pytest tests/plan/test_plan_routes.py::TestPlanRoutes::test_today_route_empty_and_fast -q`（1 passed，断言 <500ms）。

## 实施方案（implementation）
packages/qs_plan/qs_plan/application/plan_aggregator.py 组装 today 视图（激活计划/条件就绪度/环境闸 verdict/持仓差额/未决待办）+ plan_async.py IF-10 端点。

## 上游产出摘要（dependsSummary）
- 实现 PlanService（CRUD/两步提交/纪律门/审计号强制）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:19:28.665Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

today 聚合视图落地：一屏计划/环境闸/持仓/待办，空态与缺数降级正确，6 例测试绿。

### 完成项

- 新增 plan_aggregator.py：today 视图组装（激活计划/targets/entry/exit/env_gate/持仓/待办），只列 active/holding/closing
- GET /api/plans/today 端点：无计划 200+empty=true；缺 account 400
- 数据源不可用一律 skipped/None，不用 0 冒充事实（env/持仓/待办三源 fail-open）
- tests/plan/test_plan_today.py 5 例 + 路由冒烟 1 例全绿；空账户响应 <500ms

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/plan_aggregator.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/plan_async.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_today.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_routes.py`

### 下一步

t8（成交回执闭环：execute_trade 发 FillEvent + FillSync 推进计划）

---
