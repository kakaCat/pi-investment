# t-2ff7ca 成交收敛端到端场景

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
成交收敛端到端场景

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
pytest tests/scenarios/test_watch_fill_converge.py -q 退出码 0；五条断言逐条通过（待办 handled、触发 handled、exit 规则退役、position_state=none、时延只写一次）。

## 实施方案（implementation）
新增 tests/scenarios/test_watch_fill_converge.py：用组合根装配 + 假件，覆盖清仓四收敛、买入转持有、部分成交不收敛、重复成交幂等、持仓读失败 fail-closed；必要时只改测试，不改生产代码。

## 上游产出摘要（dependsSummary）
- 真实成交落库后发事件

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:37:04.517Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

场景卡完成：五条端到端闭环断言全绿（真实收敛器 + 假件）。

### 完成项

- 新增场景文件：真实 FillSyncService + 假件端口，五条闭环语义各一例
- 用例覆盖：清仓四收敛、买入转持有、部分成交不收敛、重复成交幂等、持仓读失败 fail-closed
- 验收命令 pytest tests/scenarios/test_watch_fill_converge.py -q → 5 passed

### 改动文件

- `../../tests/scenarios/test_watch_fill_converge.py`

### 下一步

联调：确认场景与生产收敛器同一入口

---
## 汇报 2（2026-10-21T12:37:23.311Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

测试通过：场景 5 例与既有收敛器回归共 43 例全绿。

### 完成项

- 验收读数：场景 5 例全绿（清仓四收敛/买入转持有/部分不收敛/重复幂等/读失败 fail-closed）
- 相邻回归：既有 fill_sync_service 38 例全绿，合计 43 例
- 场景与生产收敛器同一入口（FillSyncService.on_fill）

### 改动文件

- `../../tests/scenarios/test_watch_fill_converge.py`

### 下一步

复核：五条断言与设计逐条对照

---
## 汇报 3（2026-10-21T12:37:28.006Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：五条断言与设计一致，无偏离。

### 完成项

- 五条断言与设计逐条对照：待办 handled、触发 handled、exit 退役、状态 none、时延只写一次
- 边界对照：部分成交不收敛、读失败 fail-closed 与设计一致
- 断言口径注明「买入不收敛」是设计行为，非缺陷

### 改动文件

- `../../tests/scenarios/test_watch_fill_converge.py`

### 下一步

本卡关闭，进入执行统计端点卡

---
