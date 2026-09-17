# t-6c6dff P0 落位：文本搬迁 + 注入点切换 + 删除直取

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
P0 落位：文本搬迁 + 注入点切换 + 删除直取

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：fullstack

## 验收标准
tests/prompt-baseline.test.ts 全绿：对 6 个 stage 的解析结果与 t1 快照逐字一致（含空白与换行）；tests/stage-prompts.test.ts 断言未改动且全绿；grep 全仓 STAGE_PROMPTS[ 直取命中数 = 0、stagePromptFor( 调用点 = 0；npx tsc --noEmit -p packages/pages/dsh-pmboard/tsconfig.json 返回 0 错误。验证命令：npx vitest run tests/prompt-baseline.test.ts（在 packages/pages/dsh-pmboard 下）；不通过则本卡不完成。

## 实施方案（implementation）
把 STAGE_PROMPTS 六段文本逐字搬成 src/domain/prompt/fragments/<stage>/default.md（兜底档，id=<stage>/*）；capture-section.ts 与 CaptureHook.ts 两处注入改调 resolveStagePrompt；删除 StagePromptSpec.ts 的 STAGE_PROMPTS 常量与 stagePromptFor 直取（保留类型与「下一步」派生）；跑生成器重建 generated。验证：基线测试 + 既有测试 + tsc + 直取 grep 四道一致通过。

## 上游产出摘要（dependsSummary）
- 冻结现状阶段提示词基线快照
- 实现 resolveStagePrompt 路由解析与预算

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T14:37:57.543Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

P0 落位完成且逐字等价：6 个 stage 解析结果与快照字节级一致（771/721/716/796/625/862 全 IDENTICAL），冻结测试零改动全绿。

### 完成项

- 6 份现文本搬成 fragments/<stage>/default.md 兜底档
- 两个注入点（capture-section / CaptureHook）改调 resolveStagePrompt
- STAGE_PROMPTS[ 与 stagePromptFor( 直取命中均为 0
- tests/stage-prompts.test.ts git diff 为空且 21/21 绿
- tsc 0 错误

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/stage/StagePromptSpec.ts`
- `packages/pages/dsh-pmboard/src/application/internal/capture-section.ts`
- `packages/pages/dsh-pmboard/src/adapters/CaptureHook.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/prompt-baseline.test.ts`

### 下一步

P1 迁移冻结测试后删除兼容壳（见 decomposition.md §6 裁决 a）

---
