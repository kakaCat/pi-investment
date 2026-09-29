# t-6df9a0 看板实测回归（真实打开页面）·联调

> 需求：REQ-260927202051-f6df 实现 DAG 任务队列机制（拆分时生成 queue.json）

## 在做什么
看板实测回归（真实打开页面）·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

接口出数与磁盘真值逐项一致并可复核：① `cd agent-dh && node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080` → 退出码 0、全 passed；② `curl -s localhost:13080/dashboard/api/reqboard/state` 返回 requirements=82 / tasks=616，与 `docs/requirements/*/queue.json` 逐项一致。判据：两条命令 + 结果摘要贴进卡文档。

## 汇报 1（2026-09-27T16:03:32.371Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

联调做完：把看板/接口出的数与磁盘上的真值逐项对了一遍（51 份队列、616 条任务、82 个需求、任务顺序与 layer 出口契约），34~36 项断言全过、且证明这轮观测零写生产。这一步让「读方改造」不只停留在单测绿，而是接口数与盘上数逐项对得上。

### 完成项

- 页面/接口出数与磁盘真值逐项对齐（34~36 passed / 0 failed）：接口 tasks=616 与 Σ 各 queue.json 任务数相等；tasks 顺序 = 需求字典序分组 + 组内队列顺序（listAll 契约）逐项相同；出口剥离派生字段 layer（TaskStore D3 契约）
- 队列与需求的归属无串档：全部 616 条的 requirementId 与所在目录一一对应
- 零写证明：复跑前后 queue.json 指纹 before=after（51 份）、需求目录文件数不变、台账 rev 不变 ⇒ 本卡只读观测，未改生产数据
- 诚实降级记录：探针报 INFO「无 canceled 样本：canceled→todo 分支未验证」，不冒充满覆盖
- 以 /state 为唯一出口核对台账 requirements=82 与磁盘一致

### 改动文件

- `docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-summary.json`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-record.md`
- `docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-console.log`

### 下一步

复核卡（t-f4c9f5）独立复跑并对设计文档逐条比对。

---
