# REQ-f0579a 架构设计（审计整改）

## 修复在架构上的落点

本需求是缺陷整改，不改分层架构；五个任务的改动全部落在既有四层（domain / application / adapters+tools+http / client）内：

| 任务 | 层 | 架构要点 |
|------|-----|---------|
| FR-1 verdicts 覆盖留痕 | http/routers | 删除 confirm_override 早退分支，覆盖通过并入 91-159 行的统一校验+留痕路径（acceptanceOverride 台账/评论/状态事件三处写）。不新增路径，消灭死代码与伪造 verification 记录的可能 |
| FR-2 客户端回归 | client/views | 恢复基线归一提交丢失的三处渲染：done 需求归验收泳道（REQ-6f39b5 设计）、底部归档条（M3 起）、产物标签=种类可读名·文件名 |
| FR-3 断言精确化 | tests | 两条用户裁定合并：验收态操作条允许「立项取消」（move-req→canceled，破坏性仅人），禁止阶段推进类 move-req |
| FR-4 门禁债 | domain + tools | 状态词汇与状态**判断**单点在 domain（新增 isWorkflowRunCompleted）；工具壳只引用；两新工具 output.schema 与 return 分支键对齐 |
| FR-5 尺寸与杂项 | src 组合根 + client | index.ts 的闸门链与捕获引导段装配抽到 gate-wiring.ts（组合根的延伸，依赖方向不变）；styles 按视图归属归并；renderMarkdown 加链接协议白名单 |

## 依赖方向

- gate-wiring.ts 与 index.ts 同为组合根，允许引用 adapters + application，不反向被引用；
- domain 纯数据+纯函数约束不变（isWorkflowRunCompleted 无 import、无副作用）。