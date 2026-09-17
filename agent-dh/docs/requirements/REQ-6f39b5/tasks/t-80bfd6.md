# t-80bfd6 创建 workflow-constants.ts

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
创建 workflow-constants.ts

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：frontend

## 验收标准
文件存在，导出 WORKFLOW_STAGES / PROGRESS_DOT_STAGES / LANE_STAGES，包含注释引用唯一事实源

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-16T18:05:17.982Z，窗口 session-b8de6c05-f09f-4304-8a71-e009e89fa48c）

创建了 workflow-constants.ts 文件（85 行），导出流程节点常量对接唯一事实源

### 完成项

- 定义 WORKFLOW_STAGES（8 个节点：label/color/order）
- 定义 PROGRESS_DOT_STAGES（8 态进度点顺序）
- 定义 LANE_STAGES（6 个泳道顺序）
- 新增 WorkflowStage 类型
- 新增 3 个辅助函数：getStageLabel / getStageColor / getStageOrder
- 添加完整 JSDoc 注释，引用唯一事实源

### 改动文件

- `packages/pages/dsh-pmboard/src/client/workflow-constants.ts`

### 下一步

开始任务 t-002（实现 buildProgressDots）和 t-003（实现 buildTabs），两者可并行

---
## 汇报 2（2026-09-16T18:05:31.182Z，窗口 session-b8de6c05-f09f-4304-8a71-e009e89fa48c）

创建了 workflow-constants.ts 文件（85 行），导出流程节点常量对接唯一事实源

### 完成项

- 定义 WORKFLOW_STAGES（8 个节点：label/color/order）
- 定义 PROGRESS_DOT_STAGES（8 态进度点顺序）
- 定义 LANE_STAGES（6 个泳道顺序）
- 新增 WorkflowStage 类型
- 新增 3 个辅助函数：getStageLabel / getStageColor / getStageOrder
- 添加完整 JSDoc 注释，引用唯一事实源

### 改动文件

- `packages/pages/dsh-pmboard/src/client/workflow-constants.ts`

### 下一步

推进到测试阶段，验证导出是否正确

---
