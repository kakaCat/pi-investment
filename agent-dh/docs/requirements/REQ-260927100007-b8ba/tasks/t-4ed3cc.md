# t-4ed3cc 阶段推进加任务完整性守卫

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
阶段推进加任务完整性守卫

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run tests/advance-task-completeness-guard.test.ts 通过：计划 14 张/台账 0 张 → 拒绝且错误含修复指引；空计划放行。

## 实施方案（implementation）
新增 application/internal/task-completeness.ts（taskCompletenessGap，已在 t2 里先用上）并在 confirm-settle 推进前与 MoveRequirement 处共用；只拦「计划有卡而台账 0 张未取消任务」。

## 上游产出摘要（dependsSummary）
- 补 agent 侧需求/任务流转工具

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T03:29:32.254Z，窗口 session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8）

拆分没落库就进不了实施：阶段推进加了任务完整性守卫——计划里有卡、台账却 0 张时照样放行，现在会被拒并明确告诉你「调 reqboard_decompose 落库」。

### 完成项

- taskCompletenessGap 接入 MoveRequirement（预检 + mutate 内复查），拒绝码 REQBOARD_TASK_INCOMPLETE
- 新增 advance-task-completeness-guard.test.ts（3 例：有卡无库→拒绝且含修复指引；空计划/非 implementing/已落库/存量需求→放行）

### 改动文件

- `packages/web/dsh-pmboard/src/application/internal/task-completeness.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
- `packages/web/dsh-pmboard/tests/advance-task-completeness-guard.test.ts`

### 下一步

无。

---
