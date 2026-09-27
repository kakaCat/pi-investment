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
