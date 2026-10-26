# t-d6b85d 实现反思材料包组装与反思写回

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现反思材料包组装与反思写回

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

材料包四段齐全且缺段标 missing；五问缺项 400、verdict=keep 无理由 400、合规落库、同周期重写 version+1。验证：① `./venv/bin/python -m pytest tests/plan/test_reflection_pack.py tests/plan/test_plan_reflections.py -q`（9 passed）；② 手工：`curl -s -X POST http://127.0.0.1:5001/api/plans/<id>/reflections -H 'content-type: application/json' -d '{"answers":{"q1":"a"},"verdict":"keep"}'` 应返回 400 且 code=REFLECTION_INCOMPLETE 并点名缺 q2..q5；③ 补全后重交 → 201，`psql -d quant_test -c "select period,version,verdict from quant.plan_reflections where plan_id=<id>"` 同周期两行 version=1,2。

## 实施方案（implementation）
packages/qs_plan/qs_plan/application/reflection_pack_service.py 组装四输入材料包（计划修改历史/错过机会/盈利/亏损，段级 missing 兜底）；IF-12 反思写回（五问校验、verdict 规则、同周期 version+1）+ IF-13 列表。

## 上游产出摘要（dependsSummary）
- 实现 PlanService（CRUD/两步提交/纪律门/审计号强制）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:22:49.014Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

反思材料包与写回落地：四段输入、五问校验、同周期版本化，9 例测试绿。

### 完成项

- 新增 reflection_pack_service.py：四输入材料包（修改历史/错过机会/盈利/亏损），段级 missing 不用空数组冒充
- IF-12 反思写回：五问必填（缺项点名 400）、verdict 枚举、keep/observe 要理由、adjust/close 要提案、同周期 version+1
- IF-13 报告列表；落库后 mark_reflected 把 overdue 清零
- tests/plan/test_plan_reflections.py 6 例 + test_reflection_pack.py 3 例全绿

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/reflection_pack_service.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/plan_async.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_reflections.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_reflection_pack.py`

### 下一步

t11 定时任务；t12 双端工具（子代理进行中）

---
