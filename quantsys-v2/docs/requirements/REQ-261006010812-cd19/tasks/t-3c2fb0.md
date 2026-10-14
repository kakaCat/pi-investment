# t-3c2fb0 实现一致性矩阵（面 B，逐条落点）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现一致性矩阵（面 B，逐条落点）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：analysis
- 端侧：doc

## 得到什么结果
evidence/a2-impl-matrix.md 存在且矩阵行数 ≥ design.md §1~§11 的落点数；每行证据列匹配 ^\[L[1-4]\]；判定词只用四档（grep -cE '基本一致|大致符合|疑似|应该没问题' 命中 0）；判为「未实现」的行同行给出搜索命令与命中数；判为「已实现但语义偏离」的行写出设计侧与实现侧两个取值。

## 实施方案（implementation）
以 t1 的条目清单为输入，逐条在代码与配置里定位落点并核对语义：按符号检索 RunOutcome、FailureSink、report_failure、should_have_run、trading_day_resolver、SOURCE_CALENDAR、skipped_off_hours、expired、oversell_blocked、V13_CHAIN_STRICT、build_cron_trigger、misfire_grace_time_seconds、select_channels、AgentChannel.supports、REBALANCE 与 RISK_ALERT formatter；对每条读实现（文件:行）比对设计声明的字段名/取值/默认值/错误语义/开关名，落四档判定之一。产出 docs/requirements/REQ-261006010812-cd19/evidence/a2-impl-matrix.md（表：设计条目 / 判定 / 证据 / 说明）。

## 上游产出摘要（dependsSummary）
- 设计文档自洽性 + 版本面取证

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-10-06T01:29:35.414Z，窗口 session-6a58ec8c-8f25-44a6-9be1-a02c4a16d94f）

t2 完工：26 个设计落点全部落四档判定（一致 12 / 语义偏离 8 / 未实现 5 / 无法判定 1），每条带 [L] 强度标注；三张子卡（取数/分析/复核）均已走完。

### 完成项

- 产出 evidence/a2-impl-matrix.md：26 个落点逐条四档判定
- 12 条已实现且一致（含 §3 日历链、§4 宽限语义、§5 配置单源、§6 未接线链路、§8 盘点器、§9 兜底）
- 8 条语义偏离（含 M-06 休市日仍记 success、M-23 超卖仍 4 行、M-20 supports 仍恒真）
- 5 条未实现（M-05 _last_error、M-12 pending-orders-match 任务行、M-22 pool_scan TODO、M-24 git 回滚、M-25 V13_CHAIN_STRICT 开关）
- 1 条无法判定（M-11 missed 落库：代码在但全库 0 行，禁止生产造事件）
- 新增库面事实 6 条（含 task 249 最近一次 run 是 10-05 休市日）

### 改动文件

- `docs/requirements/REQ-261006010812-cd19/evidence/a2-impl-matrix.md`

### 下一步

t3：库表事实 + 验收命令复跑（实跑结果已在 /tmp/cd19 落地，待成文）。

---
