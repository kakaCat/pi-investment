# t-ff597e W7 阶段产物边界：plan_submit 任务表改可选 + decompose 承担任务卡创作

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
W7 阶段产物边界：plan_submit 任务表改可选 + decompose 承担任务卡创作

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
不含任务表的计划可提交（技术设计一套文档）；decompose 接受创作型 tasks 并经拆分确认门确认；故障注入：planning 阶段尝试落库任务被拒

## 上游产出摘要（dependsSummary）
- PlanTask.implementation 字段 + plan_submit 校验（W5，含事故 G DAG 校验）
- decompose 薄卡拒落 + 开工任务卡送达（W5）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T10:13:25.795Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

W7 阶段产物边界落地：plan_submit 的 tasks 改可选（技术设计一套文档：架构/四视角/风险/工作流划分，不含最终 DAG）；decompose 承担任务卡创作（计划空表时必传 tasks，薄卡拒落）；未批准计划仍不得落库（planning 阶段落库被拒）。"批了 A 落库 B"由既有拆分确认门负责

### 完成项

- plan_submit：tasks 参数改可选（schema 去 required）+ execute 分支（undefined→[]），note 区分"含/不含任务表"
- decompose：两条路径——空表=创作型（必传 tasks，normalizePlanTasks 强制 implementation+可证伪 acceptance）/ 非空表=落库批准计划（key 一致性校验保留）
- REQBOARD_TASKS_REQUIRED 新错误码（空表未传 tasks 时明确指引）
- decompose tasks schema 补 implementation 字段声明（additionalProperties:false 下漏声明会 ToolArgsError——DSH schema 铁律的又一实例）
- 6 个新用例（stage-boundary.test.ts）：不含任务表计划可提交/传表仍严格校验/空表未传拒/创作型落库/创作薄卡拒/未批准拒

### 改动文件

- `packages/pages/dsh-pmboard/src/host/agent-tools.ts`
- `packages/pages/dsh-pmboard/tests/stage-boundary.test.ts`

### 下一步

t18 阶段职责规范落地（STAGE_PROMPTS 按 W7 边界重写 + workflow-stages.md 固化）

---
