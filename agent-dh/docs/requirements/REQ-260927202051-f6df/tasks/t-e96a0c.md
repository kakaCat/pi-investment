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
## 汇报 1（2026-09-27T13:21:07.835Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

队列文件落盘变成一次真正的原子操作：先写临时文件、校验通过才改名替换，断电或并发都拿不到半截 JSON，目录里也不会留下 .tmp 残渣。文件若被外部写坏，会被自动隔离成 .corrupt-时间戳 并告警，而不是让程序读到解析不了的内容；同时补了一道防"档案串号"的检查（文件内容必须属于它所在的目录）。

### 完成项

- src/repositories/QueueRepository.ts：JsonQueueRepository + 接口 + 错误码 + queueRelativePath
- 写入顺序：先校验再落盘（校验失败连 mkdir 都不做）
- 落盘复用既有 persistAtomic（temp+fsync+rename），未自造原子写
- 损坏 JSON → .corrupt-<ts> 隔离 + 告警 + 返回 undefined；校验失败不隔离（内容不合规 ≠ 文件损坏，改名会毁掉可手工修的数据）
- 新增 requirement_id 必须与写入路径一致的防串档检查（V-1~V-6 只校验文件内部自洽，检不出串档）
- 追加 listRequirementIds()：枚举 docs/requirements/REQ-* 并排序，供 listAll 与 get 兜底索引
- tests/queue/QueueRepository.test.ts 14 用例；jq 校验为真实 execFileSync 调用（非 JSON.parse 冒充）
- Lead 独立复核：14/14 通过

### 改动文件

- `packages/web/dsh-pmboard/src/repositories/QueueRepository.ts`
- `packages/web/dsh-pmboard/tests/queue/QueueRepository.test.ts`

### 下一步

t-bc1ba6 TaskStore 端口与队列实现

---
