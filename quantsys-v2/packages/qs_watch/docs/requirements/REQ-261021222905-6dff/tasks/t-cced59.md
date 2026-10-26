# t-cced59 实现计划领域模型与状态机守卫

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现计划领域模型与状态机守卫

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/plan/test_plan_state_machine.py -q 绿：全部合法边通过；≥3 条非法边（draft→closed、closed→activate、closed→patch）拒绝且状态不变（TC-1~TC-3）。

## 实施方案（implementation）
packages/qs_plan/qs_plan/domain/plan/ 实现 TradingPlan 值对象、退出策略（stop_loss/reduce_plan）、状态机 evaluate_plan_transition 纯函数（draft/active/holding/closing/closed/archived/paused 全部合法边 + 非法边拒绝并给原因）。

## 上游产出摘要（dependsSummary）
- 实现五表 ORM 与 TradingPlanRepository

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:10:15.658Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

计划领域层落地：状态机（合法边/非法边/条件边）与 spec 校验，27 例纯逻辑测试全绿。

### 完成项

- state_machine.py：7 状态 + 11 条合法边；非法迁移给可读中文原因（草稿不能直接关/关闭不能重激活/归档终态）
- 条件边守卫：有持仓关闭必须给处置方案；反思连续缺席时禁止归档
- spec.py：五段必填校验 + 值域（exit 至少 stop_loss 或 reduce_plan、sell_ratio (0,1]、interval_sec 正整数、combinator 枚举）
- tests/plan/test_plan_state_machine.py 27 例全绿（合法边参数化 + 6 条非法边 + 条件边 + spec 校验）

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/domain/plan/__init__.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/domain/plan/state_machine.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/domain/plan/spec.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_state_machine.py`

### 下一步

进入 t4（PlanService）与 t5（编译器）

---
