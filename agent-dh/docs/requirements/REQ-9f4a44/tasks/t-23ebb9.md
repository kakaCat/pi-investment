# t-23ebb9 移除流程图与分类档案中的 done 节点

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
移除流程图与分类档案中的 done 节点

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：frontend

## 验收标准
conversation-progress.ts 的 FLOW 不含 done（流程止于归档）；CATEGORY_FLOW_PROFILES 各分类 stages/confirmGates 不含 done；单测遍历分类断言

## 上游产出摘要（dependsSummary）
- 状态机改造：新增 accepting→archived、移除 done 相关转移与门

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-16T16:57:02.940Z，窗口 session-24ded829-8d22-4e59-9318-bad027351335）

t3 流程图与分类档案去 done

### 完成项

- conversation-progress FLOW 去 done 格
- stage-panel STAGE_LABELS/StageRenderers/stageHeadSummary 去 done
- CATEGORY_FLOW_PROFILES 各分类 stages 去 done

### 下一步

见 t6

---
