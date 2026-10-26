# t-efb315 实现 PlanService（CRUD/两步提交/纪律门/审计号强制）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 PlanService（CRUD/两步提交/纪律门/审计号强制）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/plan/test_plan_service.py -q 绿：版本 CAS 冲突 409 且零改动；观察窗内无说明反向修改被拒；agent 缺 decision_audit_id 被 400；合规修改 version++ 且版本行含 baseline/window_ends_at（TC-15~TC-17）。

## 实施方案（implementation）
packages/qs_plan/qs_plan/application/plan_service.py：创建/查询/暂停恢复/关闭（有持仓必须给 close_disposition）；PATCH 暂存 draft_spec + 编译预览；apply 版本 CAS（expected_version）+ 纪律门（观察窗锁定、防反复横跳、agent 修改必须 decision_audit_id）+ 单事务写版本行/事件行。

## 上游产出摘要（dependsSummary）
- 实现计划领域模型与状态机守卫

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:10:56.031Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

PlanService 落地：两步提交 + 三条修改纪律 + 状态机迁移 + 成交推进，13 例单元测试全绿。

### 完成项

- plan_service.py：create 五段校验、patch 两步提交（暂存+diff 预览）、apply 版本 CAS+纪律门、activate/pause/resume/close 状态机、on_fill 成交推进
- 纪律门三条落地：agent 缺 decision_audit_id 拒（400）、观察窗未满改同字段需 reason 或 ≥2 证据、反向修改必须写明理由
- 关闭守卫：有持仓必须给 close_disposition；草稿不能直接关
- tests/plan/test_plan_service.py 13 例全绿（创建/预览/CAS/锁定/横跳/生命周期/成交推进）

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/plan_service.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_service.py`

### 下一步

进入 t5（PlanCompiler 幂等编译）

---
