# t-0fad87 证据路径确认后同调用内推进（已实现，补回归）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
证据路径确认后同调用内推进（已实现，补回归）

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：test
- 端侧：backend

## 得到什么结果
npx vitest run tests/confirm-evidence.test.ts 8/8 通过（含 advanced=true 与 kind 不匹配不推进两条）。

## 实施方案（implementation）
ConfirmArtifact.ts 落章后按 advanceTargetFor 推进（含 kind 与门的匹配护栏）——已在本次实现并线上验证；补 tests/confirm-evidence.test.ts 的两条断言与回归。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T03:29:32.704Z，窗口 session-52f725ef-eeda-4458-8c6d-cb15b10ad5b8）

证据路径确认后能真的推进（FR-13 已在前序实现，本卡补回归）：文字确认落章成功后同一调用内推进，不再出现「已落章但推不动」的死锁。

### 完成项

- confirm-evidence.test.ts 8/8 通过（含 advanced=true 与 kind 不匹配不推进两条断言）

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/ConfirmArtifact.ts`
- `packages/web/dsh-pmboard/tests/confirm-evidence.test.ts`

### 下一步

无。

---
