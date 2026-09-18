# t-e334fb 任务卡说人话：非工程读者能复述

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
任务卡说人话：非工程读者能复述

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
旧卡（title=规则自愈，无三要素）→ 返回拒绝或强制改写；npx vitest run /Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/tests/task-card.test.ts 通过

## 实施方案（implementation）
新增 implementing/task-card-contract 的 floor 分片 + 门禁机械校验三要素字段缺失/为空

## 上游产出摘要（dependsSummary）
- 定稿文档标准：六类文档各写什么

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T13:43:41.864Z，窗口 session-e1fc9bb5-906c-4d20-92fc-cbd5f3e2a512）

任务卡说人话：执行侧新增三要素机械校验（缺字段/字段为空 → 硬拦；标题像工程名词堆叠 → 建议级不阻断），引导侧新增 implementing 两个难度的 floor 分片，并修掉分片生成器一个限制（原先只挂 heavy/overrides，会让 light overrides 成孤岛——被门禁 4 当场抓到）。

### 完成项

- content-gates.ts 新增 TRIAD / looksTechnical / triadFields / checkTaskCardTriad：硬拦只针对三要素缺失或为空，标题判据降为建议级（对齐"不做主观文风评判"）
- 实现细节：区分"字段缺失"与"字段在但为空"；代码块里的三要素字样不算（围栏陷阱回归）
- 新增 floor 分片 src/domain/prompt/fragments/implementing/light/overrides.md（覆盖 1-3：任务卡说人话 / 工程细节下沉 / 汇报说人话）
- implementing/heavy/overrides.md 追加「覆盖 7 · 任务卡必须说人话」（保留既有 1-6 不动）
- 修生成器 scripts/inline-prompt-fragments.mjs：overrides 路由壳由"仅 heavy"泛化为"任意难度"，与文件头约定一致——修复前新增分片是孤岛，prompt-gates 门禁 4 精确报红
- tests/task-card.test.ts：12 条（含端到端注入断言——resolveStagePrompt(implementing,light,feature) 确实含契约文本；heavy 含覆盖 7；brainstorming 不含，证明不越界）
- P1 注入基线合规更新：重跑 dump-stage-prompts.mjs，diff 精确限定为 implementing/light 与 implementing/heavy 两键，新增内容即本卡契约，无意外漂移
- 重建 client 产物（exit 0、与备份逐字节一致）；全量测试回到基线 6 个失败（全属另一窗口在途改动 + 无关文件），我的文件 tsc 0 错误

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/content-gates.ts`
- `packages/pages/dsh-pmboard/tests/task-card.test.ts`
- `packages/pages/dsh-pmboard/src/domain/prompt/fragments/implementing/light/overrides.md`
- `packages/pages/dsh-pmboard/src/domain/prompt/fragments/implementing/heavy/overrides.md`
- `packages/pages/dsh-pmboard/src/domain/prompt/generated/fragments.ts`
- `packages/pages/dsh-pmboard/scripts/inline-prompt-fragments.mjs`
- `packages/pages/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json`

### 下一步

T-12（语言强度按层）与 T-14（标记载体）同样落在空闲文件上，可继续；T-3/T-4 的接线仍等 MoveRequirement.ts 释放。

---
