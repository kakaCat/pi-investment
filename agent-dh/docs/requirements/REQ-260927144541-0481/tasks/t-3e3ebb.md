# t-3e3ebb 先定契约：任务/链工具的入参与返回长什么样

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
先定契约：任务/链工具的入参与返回长什么样

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts：defineAdvanceTool 用例绿（3 个未声明键补齐）、新 TaskTreeTool 构造不抛。

## 实施方案（implementation）
按 design/interfaces I-1/I-2/I-3/I-4 改 AdvanceTool/TaskExecuteTool/TaskStatusTool 的 parameters 与 output.schema；新建 TaskTreeTool 壳的参数与输出 schema（先定形状，不填实现）。

## 上游产出摘要（dependsSummary）
- （无依赖）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-27T07:01:19.332Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

四个任务/链级工具的契约先钉死：task_run 声明真实返回键（job_id/run_id/running/next_ready/chain），删掉已不返回的 subtask_executed/blocked/stopped；新增 TaskTreeTool 的参数与输出 schema（壳）；output-contract 的响应源映射补全（TaskTree/RunStatus/ClearPause），门禁第一次真正覆盖全工具。

### 完成项

- AdvanceTool 参数改 task_id/requirement_id 并重写 output.schema 为 I-1 契约（12 键）
- TaskExecuteTool 输出 schema 对齐 I-2（去掉 stopped）
- TaskStatusTool 输出 schema 改 I-4（run/report/workflow）
- 新增 src/tools/TaskTreeTool/{TaskTreeTool.ts,prompt.ts,index.ts} 三段式壳
- tests/output-contract.test.ts 补 3 条响应源映射（TaskTree/RunStatus/ClearPause）

### 改动文件

- `agent-dh/packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`
- `agent-dh/packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts`
- `agent-dh/packages/web/dsh-pmboard/src/tools/TaskStatusTool/TaskStatusTool.ts`
- `agent-dh/packages/web/dsh-pmboard/src/tools/TaskTreeTool/TaskTreeTool.ts`
- `agent-dh/packages/web/dsh-pmboard/src/tools/TaskTreeTool/prompt.ts`
- `agent-dh/packages/web/dsh-pmboard/src/tools/TaskTreeTool/index.ts`
- `agent-dh/packages/web/dsh-pmboard/tests/output-contract.test.ts`

### 下一步

t2 链入口收口：task_run 的 requirement_id 分支与 autoRun 副作用、task_execute 真委托

---
## 汇报 2（2026-09-27T07:10:19.572Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

契约卡复验通过：四个任务/链级工具的「入参 + 返回」形状已钉死并被门禁覆盖——task_run 声明并真实返回 job_id/run_id/running/next_ready/chain（删掉已不返回的 subtask_executed/blocked/stopped）、task_execute 与 task_run 同源（同参数/同返回/同副作用）、task_status 声明 run/report 且 workflow 键改挂真实 run 摘要、task_tree 新增且可构造。复验命令全绿。

### 完成项

- 复跑验收命令：output-contract.test.ts + tools-schema.test.ts = 2 files / 66 tests 全绿（含 defineAdvanceTool 未声明键补齐、defineTaskTreeTool 构造不抛）
- 复跑契约行为测试：task-run-contract / task-tree / task-status-ledger / task-move-role = 4 files / 20 tests 全绿
- 逐条对账 design/interfaces I-1..I-4 与实现：AdvanceTool 12 键与 I-1 一致；TaskExecuteTool 复用同一 factory；TaskStatusTool 读台账 lastRun/lastReport；TaskTreeTool 参数 parent_id/requirement_id + parents schema 与 I-3 一致
- 尝试按轻档路由推进 t-3e3ebb → in_review：被拒（父卡不允许 in_progress→in_review），台账收口受阻于 D17

### 改动文件

- `packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskStatusTool/TaskStatusTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/TaskTreeTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/prompt.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/index.ts`
- `packages/web/dsh-pmboard/tests/output-contract.test.ts`

### 下一步

台账收口受阻（两条，均非本卡源码问题）：①D17 父卡收口只认「链自己认领后改过的文件」，本轮已裁定代码交付为准、台账由人处理；②本包 dist(06:07) 早于源码(06:55~07:00)，线上仍是旧契约（缺 reqboard_task_tree、仍声明 subtask_executed），需在合适时机 pnpm build + 重启 DSH 才生效。需人工裁决后继续。

---
## 汇报 3（2026-09-27T07:27:40.216Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

部署上线完成：dsh-pmboard 新契约产物已落盘并随服务重启生效——reqboard_task_tree 现为可用工具（线上核验通过），reqboard_task_run 从「start_failed: ...session」恢复为真实可执行（子卡 workflow 实跑 52s）。同时发现两处需人工裁决的跨窗口冲突。

### 完成项

- pnpm build 重建 dsh-pmboard dist（15:15），确认产物含 reqboard_task_tree 且 node 直接 import 成功
- quick_restart 部署（15:16 新进程 44634）；重启后核验 reqboard_task_tree 已注册为可用工具
- 复跑验收命令：output-contract.test.ts + tools-schema.test.ts = 2 files / 66 tests 全绿
- 实跑 reqboard_task_run：链不再 start_failed，子卡 t-c42bc0 workflow 真实执行（52s），部署修好了「链起不来」
- 定位跨窗口冲突①：他窗口把 AdvanceTool timeoutMs 改回 timeoutInteractiveMs（=HEAD 值），与 FR-6 冲突；根因是 deps.jobs 不可用→链走同步兼容路径，30s 写档确实会掐断
- 定位线上缺陷②：reqboard_run_status 声明 snapshot.runId:string 但无 active run 时返回 null → 工具拒收回执 invalid output

### 改动文件

- `packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskStatusTool/TaskStatusTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/TaskTreeTool.ts`
- `packages/web/dsh-pmboard/tests/output-contract.test.ts`
- `packages/web/dsh-pmboard/dist/index.mjs`

### 下一步

待人工裁决：①FR-6（timeoutWriteMs）与他窗口的链可用性冲突——需决定是接线 ctx.jobs（DshJobsAdapter）还是修订 FR-6 保留长超时；②reqboard_run_status 的 runId 可空契约缺口（归属 FR-7/t-5e64cd）。另：t-3e3ebb 台账收口仍受阻于子卡凭证门（既有手工交付无「开工后改动」→ REQBOARD_SUBTASK_GATE），按此前裁定由人处理。

---
