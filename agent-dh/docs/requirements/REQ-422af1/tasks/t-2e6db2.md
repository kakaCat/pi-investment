# t-2e6db2 实现 resolveStagePrompt 路由解析与预算

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
实现 resolveStagePrompt 路由解析与预算

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
tests/prompt-router.test.ts 全绿：精确/难度档/类型档/节点兜底/全局铁律五种命中层级各一例通过；遍历 6 stage × 2 difficulty × 6 category 全部返回非空 text，出现 0 例空串；低预算时 floor 片段仍包含在结果中，若连 floor 都超预算则返回结构化超限标记而非静默丢弃；同一 id 在结果中只返回一次。验证命令：npx vitest run tests/prompt-router.test.ts（在 packages/pages/dsh-pmboard 下）；不通过则本卡不完成。

## 实施方案（implementation）
新增 src/domain/prompt/{types,router,budget,index}.ts：types 定义 StagePromptRequest/ResolvedPrompt/Fragment；router 实现回退链（①(stage,difficulty,category)→②(stage,difficulty,*)→③(stage,*,category)→④(stage,*,*)→⑤(*,*,*)，⑤ 为合并而非替代）与去重；budget 按 priority 裁剪、floor 优先保留、超限返回标记；index 导出 resolveStagePrompt 并重导出类型。全部纯函数（无 I/O、无 Date.now、无 node:）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T14:37:57.525Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

实现唯一取词入口 resolveStagePrompt：5 级回退链 + 去重 + 预算裁剪（floor 不裁、超限结构化返回）。

### 完成项

- 五种命中层级各一例通过
- 6×2×6 全组合非空
- 同 id 只出现一次
- floor 超限返回 overBudget 且 floor 仍在结果中
- domain 纯函数（layer-boundary 绿）

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/prompt/types.ts`
- `packages/pages/dsh-pmboard/src/domain/prompt/router.ts`
- `packages/pages/dsh-pmboard/src/domain/prompt/budget.ts`
- `packages/pages/dsh-pmboard/src/domain/prompt/index.ts`
- `packages/pages/dsh-pmboard/tests/prompt-router.test.ts`

### 下一步

P1 增加 light/heavy 与类型档分片

---
