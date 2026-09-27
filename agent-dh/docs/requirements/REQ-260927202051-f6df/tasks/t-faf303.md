# t-faf303 实现 v8→v9 迁移变换与 CLI

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 v8→v9 迁移变换与 CLI

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① `--dry-run` 后 `md5 <ledger>` 与执行前一致且无 queue.json 生成（TC-6.1/6.2）；② `--apply` 后 `jq '.schemaVersion' <ledger>` 返回 9、`grep -c '"tasks"' <ledger>` 返回 0、migrations 末条断言为 {from:8,to:9}（TC-6.3/6.4）；③ `--verify` 退出码 0（TC-6.6）；④ `--rollback` 后台账 `jq '.schemaVersion'` 返回 8 且本次生成的 queue.json 已被清理（TC-6.8）；⑤ 日志断言先写全部 queue.json 再改台账（D-7 先于 D-8）。

## 实施方案（implementation）
在 scripts/migrate-ledger.ts 追加 v8→v9 变换 migrateV8toV9（纯函数，内部 structuredClone）与 CLI 四态：--dry-run（默认，报告不落盘）/--apply/--verify/--rollback。按 requirementId 分组 tasks → 构造 QueueFile（schemaVersion:9）→ computeLayers/Edges/Ready → validateQueueFile → 写各需求 queue.json（D-7）→ 再改台账：删 tasks、schemaVersion=9、migrations 追加留痕（D-8）→ 原子替换（D-9）。顺序固定，反序会产生双向丢失。

## 上游产出摘要（dependsSummary）
- 实现队列仓储与原子写入
- 台账 schema v9：移除 tasks

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
