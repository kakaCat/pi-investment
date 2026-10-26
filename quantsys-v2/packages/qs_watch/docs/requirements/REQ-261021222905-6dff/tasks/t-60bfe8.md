# t-60bfe8 实现计划统计归因与被拦信号统计

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现计划统计归因与被拦信号统计

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
计划内/外成交分组计数正确（TC-19）；被拦归档触发到回填日后统计接口给出 5/10/20 日涨跌幅与拦对/拦错计数（TC-18）；pytest tests/plan/test_plan_stats.py -q 绿。

## 实施方案（implementation）
IF-14 计划统计（命中率按版本分组、计划内/外盈亏、执行时延 p50/p95）+ IF-16 watch 侧被拦/抑制触发走势统计（build_blocked_stats，基于既有 outcome 回填表）。

## 上游产出摘要（dependsSummary）
- 接通成交回执：execute_trade 发 FillEvent + FillSync 推进计划状态

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:21:42.909Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

计划统计与被拦信号统计落地：IF-14/IF-16 可用，计划内/外口径与拦对拦错口径有测试断言。

### 完成项

- 新增 plan_stats_repository.py：plan_stats（计划内成交/盈亏/胜率/版本数/计划外计数）+ blocked_stats（被拦抑制触发走势：拦对/拦错/不可判，方向缺失不进分母）
- IF-14 GET /api/plans/{id}/stats 与 IF-16 GET /api/watch/outcomes/blocked-stats 落地
- tests/plan/test_plan_reflections.py 含统计用例：插入 SELL 成交后 sells/wins/pnl/win_rate/outside 断言全过
- 口径诚实：无成交/无样本返回 null 或 0 样本，不用假 0 冒充

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/outbound/repositories/plan_stats_repository.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/adapters/inbound/fastapi_app/routes/plan_async.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_reflections.py`

### 下一步

t10 反思材料包与写回（同批实现），随后 t11 定时任务

---
