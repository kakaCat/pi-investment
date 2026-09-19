# t-111acb 返工任务改由「退回返工」生成

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
返工任务改由「退回返工」生成

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
在 tests/verdicts-and-rework.test.ts 新增用例并 npx vitest run tests/verdicts-and-rework.test.ts 全绿：调 POST /req/verify/rework（带 note）后断言需求 status 返回 implementing、新增任务数等于 failed 项数、卡内含验收意见原文；状态已不在验收态时再次调用被拒绝（状态不变）。

## 实施方案（implementation）
改 src/http/routers/verdicts.ts 的 handleVerifyDecision(pass=false)：先按当前验收单的 failed 项批量建返工任务（沿用现有卡规格：title=返工：{原标题/判据}、implementation 带验收意见、acceptance=判据、scope/phase/side 承接原任务），再置 implementing 并写状态事件。

## 上游产出摘要（dependsSummary）
- 验收裁决只记录，不再自动打回

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-19T16:35:15.838Z，窗口 session-054044c2-507e-48ec-96ff-8f582605b2e2）

这一步做完：人点「退回返工」时，系统按验收单里已判不通过的项逐条建返工卡（数量=不通过项数，卡里带当时写的意见）。返工卡跟着人的决定走，不再抢在人表态之前建。

### 完成项

- domain/workflow/AcceptanceSheetSpec.ts：抽出 reworkSpecFor / reworkSpecsFor —— 返工卡规格单点，裁决路径与退回路径共用
- internal/verdicts.ts：新增 materializeReworkFromSheet（按当前验收单的 failed 项建卡）
- handleVerifyDecision(pass=false)：先建卡再置 implementing，评论附上卡号
- 新增用例：退回后 implementing、新增任务数=不通过项数、卡含验收意见原文、状态不在验收态时重复调用被拒（不会二次建卡）
- 验证：npx vitest run tests/verdicts-and-rework.test.ts → 6 passed

### 改动文件

- `packages/pages/dsh-pmboard/src/domain/workflow/AcceptanceSheetSpec.ts`
- `packages/pages/dsh-pmboard/src/application/internal/verdicts.ts`
- `packages/pages/dsh-pmboard/src/http/routers/verdicts.ts`
- `packages/pages/dsh-pmboard/tests/verdicts-and-rework.test.ts`

### 下一步

t5 收口。

---
## 汇报 2（2026-09-19T16:39:14.016Z，窗口 session-054044c2-507e-48ec-96ff-8f582605b2e2）

补充记录：给本卡的用例文件补了仓库约定的 serves 声明（design/test-cases.md 点名的用例文件必须在文件头声明覆盖条款，否则验收期会被判「孤儿用例」）。

### 完成项

- tests/verdicts-and-rework.test.ts 头部补 serves: FR-2；补后该文件 6 例仍全绿

### 改动文件

- `packages/pages/dsh-pmboard/tests/verdicts-and-rework.test.ts`

### 下一步

关闭本卡。

---
