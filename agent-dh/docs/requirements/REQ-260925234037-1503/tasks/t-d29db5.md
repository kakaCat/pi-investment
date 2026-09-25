# t-d29db5 从 tools/index.ts 移除已删除工具的导出

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
从 tools/index.ts 移除已删除工具的导出

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
运行命令 `grep -E '(DecomposeTool|MoveTool|TaskMoveTool)' packages/web/dsh-pmboard/src/tools/index.ts || echo "No references found"`，返回"No references found"，证明已删除工具的导出已移除。

## 实施方案（implementation）
1. 编辑 packages/web/dsh-pmboard/src/tools/index.ts
2. 删除以下 3 行：export { DecomposeTool } from './DecomposeTool'; export { MoveTool } from './MoveTool'; export { TaskMoveTool } from './TaskMoveTool';
3. 保存文件
4. 验证：grep -E '(DecomposeTool|MoveTool|TaskMoveTool)' packages/web/dsh-pmboard/src/tools/index.ts || echo "No references found"

## 上游产出摘要（dependsSummary）
- 删除 DecomposeTool/MoveTool/TaskMoveTool 目录

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T16:54:13.442Z，窗口 session-4211950d-3f6f-40c3-90b8-7903a76208a8）

已从 tools/index.ts 移除三个工具的导出

### 完成项

- 删除 defineMoveTool 导出
- 删除 defineDecomposeTool 导出
- 删除 defineTaskMoveTool 导出
- 验证：grep 命令返回 "No references found"

### 改动文件

- `packages/web/dsh-pmboard/src/tools/index.ts`

### 下一步

继续执行 T4（修复 accepting 配置）

---
