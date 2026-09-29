# t-c65b1a 推错状态要说清：报错带上角色与合法边，验收标准能当场改·研发

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
推错状态要说清：报错带上角色与合法边，验收标准能当场改·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

## 汇报 1（2026-09-27T10:39:26.283Z，窗口 0b9d498f-1591-492a-a0aa-737209a04902）

FR-5 交付核验通过：reqboard_task_move 角色感知报错（含父卡/子卡/存量卡与全部合法边）+ acceptance 参数接线已落盘，23 项定向测试全绿、5 个契约门禁 76 项全绿，无本卡新增红。

### 完成项

- TaskStatus.ts：新增 TASK_ROLE_LABELS（parent=父卡/subtask=子卡/legacy=存量卡）与 legalEdgesFor(role)（按 TASK_STATUS_ORDER 输出该角色全部合法边）；assertTaskTransition 非法转移文案改为『{角色}不允许 {from}→{to}；该角色合法边：{edges}』，错误码仍为 invalid_transition（分流契约不变）。
- MoveTask.ts：transitionTask 抛 invalid_transition 时在用例边界补『reqboard_task_move 未执行：』前缀后同码重抛——调用方一眼知道哪个工具拒绝、角色是谁、正确边是什么。
- TaskMoveTool.ts：新增 acceptance 参数（≤2000），接线 amendTaskAcceptanceIfRequested（台账 task.acceptance 落库 + 卡文档「## 得到什么结果」同步）；仅有 acceptance、无 to 时仅修订不改状态并返回 {success,acceptance}；两者皆缺返回 REQBOARD_INVALID_INPUT；output.schema 补齐 version/subtasks_created/task_card/acceptance。
- 测试证据：npx vitest run tests/task-move-role.test.ts tests/task-move-snapshot.test.ts tests/amend-acceptance.test.ts tests/acceptance-executable.test.ts → 4 files / 23 tests 全绿（含 TC-10 legacy 边推父卡报错含『父卡』+『合法边』+『in_progress→in_review』且零副作用、TC-11 仅 acceptance 后台账更新+卡文档同步+状态不变、空话 acceptance 被 REQBOARD_INVALID_INPUT 拒）。
- 契约门禁：npx vitest run tests/tools-schema.test.ts tests/output-contract.test.ts tests/tools-dispatch.test.ts tests/task-status-integration.test.ts tests/task-status-ledger.test.ts → 5 files / 76 tests 全绿。
- 新鲜度核验：四份改动文件 mtime 1790492114/1790492422/1790492416/1790492261，均 ≥ 链出身 chainSince=1790491541695（requirement.createdAt 2026-09-27 14:45:41，support.ts:141-148 取 requirement/父卡/子卡 createdAt 最小值），过写入族子卡凭证门。
- 归属核验（无本卡新增红）：全量 vitest run 23 files/44 tests 红，逐一核对失败断言均指向本卡未触碰的 HEAD 契约缺口——decompose-tools 期望 task_card.acceptance / requirement_status / blockers（HEAD 版 MoveTask.ts:109 与返回体均无这些键，本卡 diff 未改这些行）；size-budget/layer-boundary/message-hygiene 超限文件与 domain Date.now() 均不在本卡三文件内。tsc --noEmit 全包 113 错误，grep 本卡四文件 0 命中。

### 改动文件

- `packages/web/dsh-pmboard/src/domain/task/TaskStatus.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts`
- `packages/web/dsh-pmboard/src/tools/TaskMoveTool/TaskMoveTool.ts`
- `packages/web/dsh-pmboard/tests/task-move-role.test.ts`

### 下一步

交 integrate 子卡（t-061657）：线上工具实调 reqboard_task_move —— 反例（legacy 边推父卡/子卡进 testing）确认报错原文含角色与合法边；正例（仅 acceptance）确认台账与卡文档同步。

---
