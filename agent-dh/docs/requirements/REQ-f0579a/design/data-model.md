# REQ-f0579a 数据模型（审计整改）

## 结论：本需求不新增/变更台账 schema

- acceptanceOverride 字段由 REQ-a8d582 FR-4 定义（覆盖通过的留痕结构：台账字段 + 评论 + 状态事件）。本需求（FR-1）只**补上被早退分支跳过的写入路径**，不改字段形状；
- 两工具（reqboard_task_execute / reqboard_task_status）的 output.schema 是**接口声明**而非数据模型：补齐 error/stages/next_step/workflow 四个既有返回键的声明，使 DSH 绑定层不再拒收；
- domain 新增 isWorkflowRunCompleted(status) 纯函数与既有 WORKFLOW_RUN_STATUS 常量同源，无持久化含义；
- 台账兼容：无迁移、无 schemaVersion 变化；老台账读取不受影响。