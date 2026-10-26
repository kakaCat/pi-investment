# t-07abf5 实现 core_plan 批次适配器

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 core_plan 批次适配器

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

批次 4 标的生成 4 个 draft 且预算一致；重复调用 0 新增；core_plan 缺失/过期返回 422 CORE_PLAN_UNAVAILABLE。验证：① `./venv/bin/python -m pytest tests/plan/test_core_plan_adapter.py -q`（6 passed）；② 手工：`curl -s -X POST http://127.0.0.1:5001/api/plans/from-core-plan -H 'content-type: application/json' -d '{"account":"agent_brain","batch":1}'` 返回 success=true 且 created 数组长度=该批标的数；重放同请求 created=[] 且 skipped 非空；③ 不存在批次（batch=99）→ 422 且 code=CORE_PLAN_UNAVAILABLE。

## 实施方案（implementation）
packages/qs_plan/qs_plan/application/core_plan_adapter.py：读 config/core_plan.json 指定批次 → 逐标的生成 draft 计划（预算比例一致，一律 draft 不自动激活）；幂等（同批次重复调用 0 新增）；IF-15 端点。

## 上游产出摘要（dependsSummary）
- 实现 PlanService（CRUD/两步提交/纪律门/审计号强制）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:25:45.125Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

core_plan 批次适配落地：生成 draft、预算折算、幂等与不可用守卫齐备，6 例测试绿。

### 完成项

- 新增 core_plan_adapter.py：批次→draft 计划（预算比例按账户总额折算、一律 draft 不自动激活）
- 可用性守卫：文件缺失/过期（>7 天）/账户不符/批次不存在 → CorePlanUnavailable
- 幂等：同名 core-plan-b{batch}-{symbol} 已存在则跳过
- IF-15 路由 POST /api/plans/from-core-plan（422 CORE_PLAN_UNAVAILABLE）
- tests/plan/test_core_plan_adapter.py 6 例全绿

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/core_plan_adapter.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/plan_async.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_core_plan_adapter.py`

### 下一步

t12 收口；t15 全量收口测试

---
