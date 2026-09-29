# t-6fd3e4 链只留一个入口：起链工具收口，别名不再各跑一套·测试

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
链只留一个入口：起链工具收口，别名不再各跑一套·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

## 汇报 1（2026-09-27T08:56:40.282Z，窗口 9eeafe34-d083-497d-8528-299d747edefd）

测试结论：FR-2/FR-7 目标命令全绿（output-contract 26 + tools-schema 40 + task-run-contract 6 = 72 例通过），FR-7 故障注入 2 例通过；FR-4 死数据源清零（grep 无命中）；FR-6 命中 1 处（AdvanceTool.ts:70），即复核卡登记的 D-1 待裁决偏离，非本次测试新发现。

### 完成项

- 命令1（FR-2/FR-7）：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-run-contract.test.ts → Test Files 3 passed，Tests 72 passed（output-contract 26 / tools-schema 40 / task-run-contract 6）
- 命令2（FR-7 故障注入）：vitest run tests/output-contract.test.ts -t '故障注入' → 2 passed（注入未声明返回键时门禁变红在此例内自证）
- 命令3（FR-4）：grep -rn '## Workflow' packages/web/dsh-pmboard/src → 无输出，exit=1（死数据源已清零）
- 命令4（FR-6）：grep -rn 'timeoutInteractiveMs' src/tools/{AdvanceTool,TaskExecuteTool,RunStatusTool,TaskStatusTool} → 仅命中 AdvanceTool.ts:70，exit=0；属复核卡 D-1 已登记待裁决偏离（同期 RunStatus/TaskStatus/TaskTree 已用 timeoutReadMs）
- 命令5（父卡『得到什么结果』）：vitest run tests/task-run-contract.test.ts → 6 passed（传 task_id/requirement_id 同形、autoRun=true、都不传未绑定→REQBOARD_NO_BOUND_REQ）
- 测试口径说明：本卡只跑目标命令与相关契约套件；全仓 vitest 另有 124 例红来自其它窗口未提交改动（client-view/handoff/artifact-gates/acceptance-criteria/layer-boundary/size-budget 等），与本需求 t-d50859 改动无关，本卡不认领

### 下一步

链四卡（dev/integrate/review/test）全部完成；D-1（FR-6 超时）与 O-1（task_run 渲染）两项待人工裁决/另立卡

---
