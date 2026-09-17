# t-ceb10c 落地六条提示词门禁并故障注入验证

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
落地六条提示词门禁并故障注入验证

## 背景摘要（context）
（待补充）

## 范围
- 阶段：test
- 端侧：backend

## 验收标准
tests/prompt-gates.test.ts 正常态六条全绿；逐条故障注入后对应断言变红并记录注入方式：①删 brainstorming 兜底分片→覆盖门禁红 ②文本插 reqboard_legacy_probe→工具名门禁红 ③预算调极小且断言必须报超限→预算门禁红 ④加无人引用分片与重复 id→孤岛/唯一门禁红 ⑤删某分片「下一步」行→链声明门禁红 ⑥改 md 不跑生成→同步门禁红。六条注入记录写入任务汇报。验证命令：npx vitest run tests/prompt-gates.test.ts（在 packages/pages/dsh-pmboard 下）；不通过则本卡不完成。

## 实施方案（implementation）
新增 tests/prompt-gates.test.ts：覆盖门禁遍历 6×2×6；工具名门禁复用既有注册集合（与 tests/stage-prompts.test.ts 同源）；预算门禁用注入式小预算；孤岛门禁枚举 fragments 全部 id 反查解析命中；链声明门禁断言每节点兜底档包含「下一步：」且 next 属于状态机合法后继（复用 domain/status 既有顺序，不新写字面量）；同步门禁调用 scripts/check-prompt-fragments.mjs。

## 上游产出摘要（dependsSummary）
- 实现 resolveStagePrompt 路由解析与预算

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T14:37:57.560Z，窗口 session-41e7e4cd-4038-476c-9307-d93622a411e2）

六条提示词门禁落库，每条均经故障注入证明可变红（父窗口复核了同步门禁一条）。

### 完成项

- 六条门禁正常态 13/13 绿
- 六次故障注入全部 exit 1 变红并已恢复复绿
- 链声明走结构化表 chain.ts（裁决 b）

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/prompt/chain.ts`
- `packages/pages/dsh-pmboard/tests/prompt-gates.test.ts`

### 下一步

P1 把链声明物化进分片文本

---
