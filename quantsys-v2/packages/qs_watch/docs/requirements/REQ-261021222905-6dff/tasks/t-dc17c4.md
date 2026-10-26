# t-dc17c4 实现 PlanCompiler 幂等编译

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 PlanCompiler 幂等编译

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果

激活含 1 标的+止损+两批减仓的计划后 watch_rules 新增 4 条托管规则且 plan_id 正确；重复激活规则数不变；阈值 8%→10% apply 后规则读数=新值；注入异常时 0 条半编译规则。验证：`./venv/bin/python -m pytest tests/plan/test_plan_compiler.py -q`（6 passed，覆盖首编译/幂等/改止损/减批/持仓态/失败补偿）；真库读数：`psql -d quant_test -c "select id,plan_id,intent,conditions->0->'params'->>'pct' from quant.watch_rules where plan_id=<id>"` 应见 4 行且 plan_id 非空。

## 实施方案（implementation）
packages/qs_plan/qs_plan/application/plan_compiler.py：spec→watch_rules 的 diff 计算（create/update/retire），幂等键 (plan_id, role, symbol)；写 watch_rules 时带 plan_id/role/position_state（持仓真值）；写 trading_plan_rules 映射与 watch_rule_changes 审计（change_kind=plan_compile）；单事务，失败整批回滚。

## 上游产出摘要（dependsSummary）
- 实现五表 ORM 与 TradingPlanRepository

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:11:37.573Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

PlanCompiler 落地：spec→watch_rules 幂等 diff（含分批减仓键）、持仓态直写、审计与失败补偿，6 例测试全绿。

### 完成项

- plan_compiler.py：desired_rules 展开（entry/stop_loss/reduce 分批）+ diff(create/update/retire) + apply 补偿回滚
- 幂等键按 (role, symbol, batch) 区分同标的多批减仓（实测发现只用 symbol 会互相覆盖）
- 编译写 position_state=持仓真值；每次变更落 watch_rule_changes 审计（plan_compile）
- 失败补偿：本次已建规则全部退役，无半编译存活（TC-7 断言）
- tests/plan/test_plan_compiler.py 6 例全绿（首次/幂等/改止损/减批/持仓态/回滚）

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/plan_compiler.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_compiler.py`

### 下一步

进入 t6（路由）与 t7（today 视图）

---
