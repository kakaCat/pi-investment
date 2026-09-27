# t-e96a0c 实现队列仓储与原子写入

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现队列仓储与原子写入

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① `npx vitest run src/repositories/QueueRepository.test.ts` 全绿（TC-3.1~TC-3.6）；② save 后 `jq . <queue.json>` 退出码 0，且 `ls <dir> | grep -c tmp` 输出 0（无残留临时文件）；③ load 不存在的需求断言返回 undefined（非抛错）；④ 损坏 JSON 后断言目录下存在 `.corrupt-*` 隔离文件；⑤ 校验失败路径断言 queue.json 不存在；⑥ `grep -c "persistAtomic" src/repositories/QueueRepository.ts` 命中 ≥ 1（复用未自造）。

## 实施方案（implementation）
新建 src/repositories/QueueRepository.ts。load(requirementId)：读 docs/requirements/<REQ>/queue.json → JSON 解析 → validateQueueFile；不存在/解析失败/校验失败均返回 undefined（解析失败时隔离改名为 .corrupt-<ts> 并告警）。save(requirementId, file)：先 validateQueueFile，通过才调 adapters/JsonLedgerRepository.ts 已导出的 persistAtomic 原子写（temp+fsync+rename），失败抛 QUEUE_VALIDATION_FAILED 且不落盘。pathOf 返回队列文件路径。

## 上游产出摘要（dependsSummary）
- 定义队列类型与任务契约
- 实现 DAG 拓扑分层与派生视图
- 实现队列数据校验 V-1~V-6

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
