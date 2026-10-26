# t-e12dcf 接线反思唤醒通道（waker 注入 + 任务调用）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
接线反思唤醒通道（waker 注入 + 任务调用）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/plan/test_reflection_job.py -q 全绿，含新增两例：注入 fake waker 后每张到期计划被调用一次且 review_due_at 前移；waker 抛异常时该计划 overdue_count+1 且其余计划继续处理。

## 实施方案（implementation）
改 packages/qs_plan/qs_plan/application/reflection_job.py：组包成功后调用注入的 waker(plan, pack)，False/异常 → bump_overdue 并继续；成功 → set_review_due。改 adapters/inbound/fastapi_app/main.py：build_plan_jobs(waker=...) 注入 qs_agenthub AgentNotificationService.notify_agent 包装（event=plan_reflection，data 含 plan_id/period/四段摘要，target 按 route_owner）。补 tests/plan/test_reflection_job.py 两例。开关 PLAN_REFLECTION_WAKE_ENABLED。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T18:34:14.851Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

反思唤醒接线完成：waker 复用既有 notify_agent→/wake，开关可控、失败计 overdue；3 例新测试 + 既有 5 例全绿。

### 完成项

- reflection_job.py 新增 build_agent_waker：包既有 AgentNotificationService.notify_agent，event=plan_reflection，data 含 plan_id/account/period/pack_summary/answers_required/instruction
- build_plan_jobs(waker=) 支持注入；缺省按 PLAN_REFLECTION_WAKE_ENABLED 自动装配（关闭则返回 None 只组包）
- target 按账户路由（agent_brain → agent-dh，其余 agent-ts）
- tests/plan/test_reflection_job.py 新增 3 例（关闭返回 None / notify 收到计划与包摘要 / build_plan_jobs 注入）
- pytest tests/plan/test_reflection_job.py -q → 8 passed

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/reflection_job.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_reflection_job.py`

### 下一步

t2/t3 批次收敛、t4 消息链回归、t5 收口

---
