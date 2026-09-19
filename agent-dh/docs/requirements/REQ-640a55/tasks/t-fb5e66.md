# t-fb5e66 把三要素门禁接上执行链（出口与结单）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
把三要素门禁接上执行链（出口与结单）

## 解决什么问题
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
npx vitest run packages/pages/dsh-pmboard/tests/triad-gate.test.ts 全绿（13 条：接线函数 8 条 + 工具层端到端 5 条——出口拦/出口放行/卡文件不存在放行/结单拦/结单放行）；反向验证：摘掉 MoveTool 接线后该文件 1 条变红、摘掉 TaskMoveTool 接线后 1 条变红。

## 实施方案（implementation）
在 packages/pages/dsh-pmboard/src/application/internal/content-gate-wiring.ts 新增 taskCardTriadGaps / taskCardTriadFailure / requirementTaskCardTriadFailure（只做文件读取与组装，调 checkTaskCardTriad 判定，跳过规则三条）；在 tools/MoveTool/MoveTool.ts 的 execute 内、executeMoveRequirement 之前调 requirementTaskCardTriadFailure；在 tools/TaskMoveTool/TaskMoveTool.ts:112-131 现有证据锚定预检后追加 taskCardTriadFailure，命中即 reject 并带 code=task_card_incomplete。

## 上游产出摘要（dependsSummary）
- 让拆分骨架直出任务卡三要素节

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-19T11:28:09.558Z，窗口 session-98f2b4b4-cfff-4a90-baa9-214fc15d99d2）

三要素门禁真的挂上了：新增接线模块 content-gate-triad.ts，在两个时刻拦人——离开拆分态之前（一次扫全部卡）与单卡结单之前；code=task_card_incomplete，消息列出卡 id 与缺的节名。三条跳过规则防误伤。

### 完成项

- FR-1 AC1 需求出口拦：MoveTool.execute 在 executeMoveRequirement 之前调 requirementTaskCardTriadFailure（to=implementing），命中即 reject code=task_card_incomplete
- FR-1 AC2 单卡结单拦：TaskMoveTool.execute 在证据锚定之后、executeMoveTask 之前调 taskCardTriadFailure（to=done），同样 code=task_card_incomplete
- FR-1 AC3 不误伤三条：目标态不符 / 卡文件不存在 / 任务不属本窗口绑定集合 → 一律不判（各有专门用例）
- 新增 src/application/internal/content-gate-triad.ts（86 行）：只做读卡+解析+拼缺口，判定仍在零 IO 的 content-gates.checkTaskCardTriad；不塞进 content-gate-wiring.ts 是因为它已 369 行、尺寸门禁单文件 ≤400
- 本需求 5 张老骨架生成的卡全部补上三要素节（不补会被自己新接的门禁拦下），逐卡核对三节齐备且正文非空
- tests/triad-gate.test.ts 13 条：接线函数 8 条 + 工具层端到端 5 条（出口拦/出口放行/卡不存在放行/结单拦/结单放行）
- 反向验证两次：摘掉 MoveTool 接线 → 出口拦截用例变红；摘掉 TaskMoveTool 接线 → 结单拦截用例变红；还原后全绿
- 回归：npx vitest run → 99 文件 / 1278 条全绿；npx tsc --noEmit 零错误

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/content-gate-triad.ts`
- `packages/pages/dsh-pmboard/src/tools/MoveTool/MoveTool.ts`
- `packages/pages/dsh-pmboard/src/tools/TaskMoveTool/TaskMoveTool.ts`
- `packages/pages/dsh-pmboard/tests/triad-gate.test.ts`
- `docs/requirements/REQ-640a55/tasks/t-fb5e66.md`
- `docs/requirements/REQ-640a55/tasks/t-11e56a.md`
- `docs/requirements/REQ-640a55/tasks/t-ad7826.md`
- `docs/requirements/REQ-640a55/tasks/t-92e0b3.md`
- `docs/requirements/REQ-640a55/tasks/t-c8fb87.md`

### 下一步

t-11e56a：T-9 改卡通道双标题回归用例 + 存量卡零误伤实测留痕。

---
