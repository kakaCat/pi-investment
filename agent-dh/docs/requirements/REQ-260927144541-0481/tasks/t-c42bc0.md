# t-c42bc0 先定契约：任务/链工具的入参与返回长什么样·研发

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
先定契约：任务/链工具的入参与返回长什么样·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

## 汇报 1（2026-09-27T11:18:06.005Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

研发：按 design/interfaces I-1~I-4 落定任务/链工具的入参与返回形状——reqboard_task_run 参数改 task_id/requirement_id、output.schema 12 键对齐；reqboard_task_execute 改为真委托；reqboard_task_status 对齐 I-4；新建 TaskTreeTool 三段式壳；tools/index.ts 登记导出。本卡文档为「验收前置 9 类文档」门禁补登（原始汇报见台账 lastReport，reportIndex=2，卡状态 done / lastRun.ok=true）。

### 完成项

- AdvanceTool（reqboard_task_run）：参数改 task_id/requirement_id，output.schema 对齐 design I-1（12 键），删除已不返回的 subtask_executed/blocked/stopped
- TaskExecuteTool（reqboard_task_execute）：改为 defineAdvanceTool 真委托（同参数/同返回/同 autoRun 副作用），描述标已弃用 —— design I-2
- TaskStatusTool（reqboard_task_status）：parameters=task_id(required)，output.schema 对齐 design I-4
- 新建 TaskTreeTool 三段式壳（TaskTreeTool.ts + prompt.ts + index.ts）：参数 parent_id/requirement_id，节点含 id/title/status/role/stageKind/dependsOn/attempt/lastRunOk/reportSummary/cardDoc
- tools/index.ts 登记导出 defineTaskTreeTool（新工具进入工具集与门禁覆盖）
- output-contract 响应源映射补 TaskTree/RunStatus/ClearPause，声明键 ⊇ return 键门禁首次覆盖全工具
- 原始证据（台账留存）：vitest output-contract+tools-schema → 2 files / 66 tests passed；task-run-contract+task-tree+task-status-ledger+task-move-role → 4 files / 20 tests passed

### 改动文件

- `packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`
- `packages/web/dsh-pmboard/src/tools/AdvanceTool/prompt.ts`
- `packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskStatusTool/TaskStatusTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/TaskTreeTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/prompt.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/index.ts`
- `packages/web/dsh-pmboard/src/application/use-cases/TaskTree.ts`
- `packages/web/dsh-pmboard/src/tools/index.ts`
- `packages/web/dsh-pmboard/tests/output-contract.test.ts`
- `packages/web/dsh-pmboard/tests/tools-schema.test.ts`
- `packages/web/dsh-pmboard/tests/task-run-contract.test.ts`
- `packages/web/dsh-pmboard/tests/task-tree.test.ts`

### 下一步

已收口（卡文档补登，服务验收前置文档门禁）

---
