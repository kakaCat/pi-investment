# t-7f6add 收口测试与端到端冒烟

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
收口测试与端到端冒烟

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
pytest tests/plan/ -q 全绿；pytest tests -k watch -q 不新增红；UC-1/UC-2 剧本走通（关键状态与落库行可查）。

## 实施方案（implementation）
补齐 tests/plan/ 全部用例（TC-1~TC-22）；跑 watch 既有套件确认不新增红；按 UC-1（建计划→激活→触发→模拟成交→回执收敛）与 UC-2（盘后反思→改止损→预览→apply→规则重编译）做端到端冒烟。

## 上游产出摘要（dependsSummary）
- 实现今日计划聚合视图
- 实现计划统计归因与被拦信号统计
- 实现反思定时任务与 overdue 兜底
- 实现 trading_plan 工具双端（agent-dh 投资脑 + agent-ts fin-agent）
- 接通进化层消费反思知识段
- 实现 core_plan 批次适配器

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T16:37:13.240Z，窗口 session-11ba604a-d626-4750-b955-7e769919277e）

收口完成：plan 套件 113 例全绿，watch 套件无新增红，UC-1/UC-2 端到端冒烟走通，补 closed 计划防改守卫。

### 完成项

- tests/plan/ 全量 113 例通过（含 TC-1~22 对应断言）
- watch 既有套件：791 passed / 2 failed——2 例为早先登记的预存红（test_watch_t12_todo_creation 与市场级路由未同步），本需求无新增红
- 新增端到端冒烟 tests/plan/test_plan_e2e.py：建计划→激活→买入回执→holding→清仓回执→closed→反思落库→已关闭计划修改被 422 拒→统计可读
- 补一处正确性守卫：closed/archived 计划禁止 patch/apply（防「关了还在改」的幽灵计划），e2e 已断言 422
- 迁移三份（五表+批列+调度任务行）在 quant_test 已 apply 且重跑幂等

### 改动文件

- `/Users/yunpeng/pi-investment/quantsys-v2/tests/plan/test_plan_e2e.py`
- `/Users/yunpeng/pi-investment/quantsys-v2/packages/qs_plan/qs_plan/application/plan_service.py`

### 下一步

提交验收材料（kind=verification），等待人工逐项验收

---
