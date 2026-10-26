# t-b8d5ae 执行闭环统计端点

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
执行闭环统计端点

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/api/test_watch_exec_stats.py -q 退出码 0；空数据返回全 0；构造三类样本后 executed/declined/timeout 分别命中；分位与台账查询一致；治理类不进分母。

## 实施方案（implementation）
adapters/inbound/fastapi_app/routes/watch_async.py 新增 GET /api/watch/exec/stats（since/until 可选）；adapters/outbound/repositories/watch_todo_repository.py 增加聚合查询（三态计数 + 从 trigger detail.exec 取时延算 p50/p95，排除治理类）；新增 tests/api/test_watch_exec_stats.py。

## 上游产出摘要（dependsSummary）
- 真实成交落库后发事件

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:40:45.239Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

测试通过：统计端点 5 例全绿，空数据与异常路径均符合契约。

### 完成项

- 新增仓储聚合：三态计数 + 从触发证据取时延算 p50/p95，排除治理类；空样本返回 null
- 新增端点 GET /api/watch/exec/stats（since/until 可选），非法窗口 400、聚合失败 503
- 新增 5 例测试：计数与分位、空数据、非法窗口、仓储异常、分位函数
- 验收 pytest tests/api/test_watch_exec_stats.py -q → 5 passed

### 改动文件

- `../../adapters/outbound/repositories/watch_todo_repository.py`
- `../../adapters/inbound/fastapi_app/routes/watch_async.py`
- `../../tests/api/test_watch_exec_stats.py`

### 下一步

复核：核对统计口径与台账一致性

---
## 汇报 2（2026-10-21T12:40:49.079Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：统计口径与错误语义符合 IF-4，无实质偏离。

### 完成项

- IF-4 契约核对：三态计数 + p50/p95 + 样本数；空数据返回 0/null 不报错
- 错误码核对：窗口非法 400、仓储异常 503，均不返回半份数字
- 口径核对：分母只含执行类待办（trade/rule_change），治理类不计入
- 偏离登记：timeout 计数取回执表联表统计（与既有 SLA 台账同源），未新增列

### 改动文件

- `../../adapters/outbound/repositories/watch_todo_repository.py`

### 下一步

本卡关闭，进入组合根装配收尾

---
