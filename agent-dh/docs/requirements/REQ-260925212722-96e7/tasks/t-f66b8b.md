# t-f66b8b 扩展数据结构

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
扩展数据结构

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：fullstack

## 得到什么结果
1. 编译通过：cd packages/web/dsh-pmboard && pnpm build
2. 类型检查通过：grep "dive?: RequirementDive" src/shared/protocol.ts
3. 字段定义完整（包含 phase/activation/currentStage 等）

## 实施方案（implementation）
修改 protocol.ts：新增 RequirementDive 接口（phase/activation/currentStage 等字段），扩展 Requirement 接口添加 dive?: RequirementDive 字段。确保类型定义完整且兼容现有代码。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-25T14:09:37.769Z，窗口 session-4211950d-3f6f-40c3-90b8-7903a76208a8）

已完成数据结构扩展：新增 RequirementDive 接口，扩展 RequirementRecord.dive 字段，编译通过

### 完成项

- 新增 RequirementDive 接口定义（phase/activation/roundsInStage/maxRoundsPerStage/currentStage/pausedReason/lastActiveAt）
- 扩展 RequirementRecord 接口添加 dive?: RequirementDive 可选字段
- 编译验证通过：cd packages/web/dsh-pmboard && pnpm build
- 类型检查通过：grep "dive?: RequirementDive" 确认字段存在

### 改动文件

- `packages/web/dsh-pmboard/src/shared/protocol.ts`

### 下一步

推进任务到 testing 状态，准备开始下一个任务

---
