# t-e783cc 验收裁决只记录，不再自动打回

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
验收裁决只记录，不再自动打回

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
新建路由用例并 cd agent-dh/packages/pages/dsh-pmboard && npx vitest run tests/verdicts-and-rework.test.ts 全绿：POST /req/verdicts 带 1 项 failed 后，需求 status 仍返回 accepting、任务总数不变、返回 note 包含"退回返工"字样（按新语义更新既有断言）。

## 实施方案（implementation）
改 src/http/routers/verdicts.ts 的 handleVerdicts：删掉"有 failed 即自动打回并建卡"的分支，改为只写验收单并返回指引 note；src/application/internal/verdicts.ts 的 applyVerdicts 同步"不改状态"；src/application/use-cases/AcceptSheet.ts 的自动打回与文案同步。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-19T16:35:15.805Z，窗口 session-054044c2-507e-48ec-96ff-8f582605b2e2）

这一步做完：逐项验收里打"不通过"只是记在验收单上，需求留在验收态、按钮都还在；要不要打回实施由人点「退回返工」决定。看板与 agent 弹框两条通道统一到这一条规则（裁决只记录）。

### 完成项

- handleVerdicts 删掉"有 failed 即自动打回 + 批量建卡"分支，只写验收单并返回指引 note；rework_tasks 恒为空数组
- internal/verdicts.ts applyVerdicts 同步"裁决不改状态"，模块文档改写为新语义
- AcceptSheet.ts 两处 note 改成如实描述（不再宣称"已打回"）
- tests/verdicts-and-rework.test.ts 改语义断言（仍在 accepting、任务数不变、note 指向退回返工），并去掉对 reqboard_verify_submit 的依赖（直接播种台账，顺带摆脱与本卡无关的模块）
- tests/accept-sheet-tool.test.ts 期望改为"不自动打回"——**未执行**：该文件依赖 src/tools/index.ts，而同事窗口未提交的 Decompose.ts:221 有语法错误（await 在非 async 回调内），见 t5 卡阻塞说明

### 改动文件

- `packages/pages/dsh-pmboard/src/http/routers/verdicts.ts`
- `packages/pages/dsh-pmboard/src/application/internal/verdicts.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/AcceptSheet.ts`
- `packages/pages/dsh-pmboard/tests/verdicts-and-rework.test.ts`
- `packages/pages/dsh-pmboard/tests/accept-sheet-tool.test.ts`

### 下一步

t3 承接"退回返工时建卡"；t5 收口回归。

---
