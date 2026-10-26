# t-3ef50b sidecar 拆盘中/盘后，盘后消息可扫

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
sidecar 拆盘中/盘后，盘后消息可扫

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
pytest tests/application/test_watch_sidecar_window.py -q 退出码 0；16:30 时钟下消息扫描执行、回填与生命周期任务不重复执行；非交易日不扫；窗外返回 scanned=False 不抛错。

## 实施方案（implementation）
packages/qs_watch/.../engine.py 把 _run_sidecar 拆成盘中段与盘后段：消息扫描在交易日 08:00–22:00 可跑，其余日频任务维持当日一次；收盘日报在盘后段触发；新增 tests/application/test_watch_sidecar_window.py。

## 上游产出摘要（dependsSummary）
- 消息→P1 待办桥（critical 建单 + 唤醒）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-21T12:40:18.130Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

研发完成：sidecar 拆盘中/盘后两段，盘后消息扫描与日报独立，5 例测试全绿。

### 完成项

- engine._run_sidecar 拆盘中/盘后：非交易时段转 _run_sidecar_offhours
- 盘后段只做消息扫描（08:00–22:00 由服务窗控）与收盘日报（一日一次）
- 盘后段不触发回填/生命周期等日频任务（保持原节奏）
- 新增 5 例用例：盘后扫描、盘中不发日报、非交易日不跑、盘后不跑回填、日报一日一次

### 改动文件

- `../../packages/qs_watch/qs_watch/application/services/watch_engine/engine.py`
- `../../tests/application/test_watch_sidecar_window.py`

### 下一步

联调与测试：确认盘后段与盘中段互不干扰

---
## 汇报 2（2026-10-21T12:40:25.265Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

测试通过：sidecar 分段 5 例与联合回归 61 例全绿。

### 完成项

- 验收读数：test_watch_sidecar_window → 5 passed
- 联合回归：工厂/桥/统计/待办/新闻共 61 passed
- 盘后段与盘中段互不干扰：盘后不跑回填、盘中不发日报

### 改动文件

- `../../tests/application/test_watch_sidecar_window.py`

### 下一步

复核：核对窗口与日频任务边界

---
## 汇报 3（2026-10-21T12:40:30.730Z，窗口 session-c0714366-6e5b-42e9-9b20-c259d58b3820）

复核结论：窗口与日频任务边界符合设计；盘中重复扫描由服务节流兜底，已登记。

### 完成项

- 窗口边界核对：交易日判据不变；08:00–22:00 由消息服务自身窗口控制
- 日频任务边界核对：盘后段只跑消息与日报，回填/生命周期/板块映射维持盘中节奏
- 兼容核对：_run_sidecar 签名与盘中行为不变，收盘日报仍一日一次
- 偏离登记：盘中段仍保留一次消息扫描（服务内部节流 15 分钟），与盘后段共用同一服务实例

### 改动文件

- `../../packages/qs_watch/qs_watch/application/services/watch_engine/engine.py`

### 下一步

本卡关闭，进入组合根装配卡

---
