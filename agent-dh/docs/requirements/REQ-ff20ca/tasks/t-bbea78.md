# t-bbea78 新增 reqboard_requirement_submit 登记需求文档产物

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
新增 reqboard_requirement_submit 登记需求文档产物

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
调用后台账 artifacts 出现 {kind:requirement,stage:brainstorming,path}；文件不存在则报错且不写台账；同 path 幂等；单测通过。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-16T16:32:44.004Z，窗口 session-24ded829-8d22-4e59-9318-bad027351335）

新增 reqboard_requirement_submit（补需求文档产物登记入口）+ 4 条单测

### 完成项

- agent-tools.ts 新增 reqboard_requirement_submit：文件校验 → registerArtifact(requirement) → 通知请人审阅
- index.ts 注册（工具名进 apply 日志）
- tests/requirement-submit.test.ts 新增 4 用例：首次登记 / 幂等 / 文件缺失拒绝且不写台账 / 非 brainstorming 状态拒绝
- 线上验证：工具已随重启注册，调用返回状态纪律校验
- 单测全过（4/4）

### 改动文件

- `packages/pages/dsh-pmboard/src/host/agent-tools.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/requirement-submit.test.ts`

### 下一步

全部任务完成，准备提交验收

---
