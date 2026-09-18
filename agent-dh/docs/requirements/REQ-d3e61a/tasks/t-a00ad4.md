# t-a00ad4 语言强度按层：技术层不硬写成散文

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
语言强度按层：技术层不硬写成散文

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
设计文档每节返回 serves 标注；npx vitest run /Users/yunpeng/pi-investment/agent-dh/packages/pages/dsh-pmboard/tests/language-layer.test.ts 通过

## 实施方案（implementation）
把「语言强度按层」写进标准并落成提示词分片约束；门禁只校验每节有 serves，不校验文风

## 上游产出摘要（dependsSummary）
- 定稿文档标准：六类文档各写什么

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T13:46:50.363Z，窗口 session-e1fc9bb5-906c-4d20-92fc-cbd5f3e2a512）

语言强度按层 + 设计章节可追溯：新增 checkDesignSectionsHaveServes（只校验每节有没有 serves，不校验文风）+ planning 两个难度的 floor 分片（含语言强度按层表：需求全业务 / 技术设计技术为主但每节标 serves / 拆分业务标题 / 实施技术为主 / 验收全业务可执行），配 7 条测试含端到端注入断言。

### 完成项

- content-gates.ts 新增 checkDesignSectionsHaveServes：H2+ 章节缺 serves 即点出（孤儿章节 → design_orphan）；刻意不校验文风（对齐"机器不判散文好坏"）
- 新增 floor 分片 src/domain/prompt/fragments/planning/light/overrides.md：覆盖 1 章节可追溯 + 覆盖 2 语言强度按层（五层语言表）
- planning/heavy/overrides.md 追加「覆盖 6 · 章节可追溯 + 语言强度按层」（保留既有 1-5 不动）
- tests/language-layer.test.ts：7 条——含"缺标注章节被精确点出""H1 文档标题不参与""代码块里的假章节不算"三个边界，以及 planning light/heavy 真注入、implementing 档不越界三条端到端断言
- P1 基线合规更新：diff 精确限定为 planning/light(1123→1750) 与 planning/heavy(8384→8603) 两键，其余 10 键零变化
- 重建 client（exit 0、verify-client OK、与备份逐字节一致）；全量 1028 passed，失败数回到基线 6 个（全属另一窗口在途改动 + 无关文件）

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/content-gates.ts`
- `packages/pages/dsh-pmboard/tests/language-layer.test.ts`
- `packages/pages/dsh-pmboard/src/domain/prompt/fragments/planning/light/overrides.md`
- `packages/pages/dsh-pmboard/src/domain/prompt/fragments/planning/heavy/overrides.md`
- `packages/pages/dsh-pmboard/src/domain/prompt/generated/fragments.ts`
- `packages/pages/dsh-pmboard/tests/fixtures/stage-prompts-baseline-p1.json`

### 下一步

T-15（提示词注入变聪明，router.ts 空闲）可继续；T-3/T-4 接线仍等 MoveRequirement.ts 释放。

---
