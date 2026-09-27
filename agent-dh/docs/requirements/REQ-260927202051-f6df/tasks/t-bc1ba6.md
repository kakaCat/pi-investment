# t-bc1ba6 实现 TaskStore 端口与队列实现

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
实现 TaskStore 端口与队列实现

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
① `npx vitest run src/repositories/QueueTaskStore.test.ts` 全绿（TC-4.1~TC-4.8）；② createMany 5 任务后断言队列 tasks.length 等于 5 且每条 layer 已算；③ 重复 id 断言被幂等跳过（原有字段不变）；④ mutate 改 done 后断言 ready 包含下游 id 且 updated_at 已变；⑤ 无队列需求 mutate 断言拒绝并抛 QUEUE_NOT_FOUND；⑥ 写后 get 返回新值（缓存已失效）。

## 实施方案（implementation）
在 src/application/ports.ts 定义 TaskStore 端口（get/listByRequirement/readQueue/mutate/createMany/subscribe）；新建 src/repositories/QueueTaskStore.ts 实现之：按需求懒加载 queue.json + 内存缓存；写路径强制重读文件后合并（不信任缓存），重算 edges/layers/ready → 校验 → 原子写 → 失效缓存 → 广播 TaskChange。createMany 幂等（已存在 id 跳过）。

## 上游产出摘要（dependsSummary）
- 实现队列仓储与原子写入

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T13:21:07.986Z，窗口 session-3936d77f-2391-4042-8305-9b0fb5e9d2b8）

任务第一次有了唯一入口：所有读方只从这一处取任务，出口自动剥掉队列内部才需要的 layer 字段，读方代码一行都不用改；因此首页/看板拿到的响应不会多出内部字段。状态改动写回队列时会顺带重算执行批次并广播变更事件，下游任务自动解锁；同一需求内任务顺序被保住。

### 完成项

- src/application/ports.ts：新增 TaskStore 端口（I-1）+ QueueMutateContext + TaskChange；UseCaseDeps 加可选 taskStore?
- src/repositories/QueueTaskStore.ts：懒加载缓存、写路径强制重读文件（不信任缓存）、派生视图唯一来源=topology、进程内按需求 revision、subscribe 广播
- D3 落地：get/listByRequirement/listAll/mutate/createMany 出口一律 structuredClone 后 delete layer，返回 TaskRecord；readQueue 才带 layer
- D2 落地：listAll() = listRequirementIds()（已排序）依次拼接，即 requirementId 字典序 + 组内文件顺序（排序键写在 ports.ts:118 注释）
- tests/queue/QueueTaskStore.test.ts 23 用例：5 任务 layer=0/1/2 + 三层分组 + edges + ready；重复 id 幂等且全已存在时 mtime 与内容均不变；mutate done 解锁下游 + updated_at 刷新；QUEUE_NOT_FOUND；校验失败后文件 md5 完全一致；写后 get 立即可读；subscribe kind=task-moved；零读盘构造
- Lead 独立复核：23/23 通过；D2/D3 落盘确认

### 改动文件

- `packages/web/dsh-pmboard/src/repositories/QueueTaskStore.ts`
- `packages/web/dsh-pmboard/src/application/ports.ts`
- `packages/web/dsh-pmboard/tests/queue/QueueTaskStore.test.ts`

### 下一步

t-2417da 台账 schema v9：移除 tasks

---
