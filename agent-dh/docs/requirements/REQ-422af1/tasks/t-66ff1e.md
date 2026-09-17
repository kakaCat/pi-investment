# t-66ff1e 冻结现状阶段提示词基线快照

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
冻结现状阶段提示词基线快照

## 背景摘要（context）
（待补充）

## 范围
- 阶段：analysis
- 端侧：backend

## 验收标准
tests/fixtures/stage-prompts-baseline.json 存在且含 6 个 key（brainstorming/planning/decomposing/implementing/accepting/archived）；重跑 scripts/dump-stage-prompts.mjs 输出与该文件逐字一致（diff 为空即通过）；该文件必须早于任何取词代码改动（用 git 历史核对一致）。验证命令：npx vitest run tests/prompt-baseline.test.ts（在 packages/pages/dsh-pmboard 下）；不通过则本卡不完成。

## 实施方案（implementation）
新增 scripts/dump-stage-prompts.mjs（node + tsx，import src/domain/stage/StagePromptSpec.js），把 STAGE_PROMPTS 按 key 排序输出为 JSON（保留空白与换行，不 trim）；写入 tests/fixtures/stage-prompts-baseline.json。验证：连跑两次 diff 为空；git log 显示该文件早于取词改动。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T14:37:57.486Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

冻结 6 个 stage 的注入文本基线快照，作为 P0 等价性唯一对照物（父窗口已复核：连跑两次 diff 为空、快照先于取词改动产生）。

### 完成项

- 写 scripts/dump-stage-prompts.mjs（按 key 排序导出、保留空白不 trim）
- 产出 tests/fixtures/stage-prompts-baseline.json（6 key）
- 连跑两次输出 diff 为空

### 改动文件

- `packages/pages/dsh-pmboard/scripts/dump-stage-prompts.mjs`
- `packages/pages/dsh-pmboard/tests/fixtures/stage-prompts-baseline.json`

### 下一步

作为 t4 与 tests/prompt-baseline.test.ts 的对照物

---
