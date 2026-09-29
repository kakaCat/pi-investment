# t-b079ef 链只留一个入口：起链工具收口，别名不再各跑一套·研发

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
链只留一个入口：起链工具收口，别名不再各跑一套·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

## 汇报 1（2026-09-27T08:55:03.622Z，窗口 9eeafe34-d083-497d-8528-299d747edefd）

链入口收口落地并复验：AdvanceTool 参数支持 requirement_id（与 task_id 至少其一）、描述显式声明「调用即写 autoRun」、返回体与 output.schema 逐键对齐（subtask_executed/blocked/stopped 已删除）；TaskExecuteTool 改为复用 defineAdvanceTool 同一 factory 产物（同 parameters/output/execute）并标注已弃用。相关契约测试 88 例全绿。

### 完成项

- AdvanceTool.parameters 增 requirement_id，task_id 改为可选（二者至少其一，缺省取本窗口绑定需求）
- ADVANCE_PROMPT 补「调用即写 req.autoRun=true（开启自动链）」副作用声明
- AdvanceTool output.schema 与返回体逐键对齐（additionalProperties:false；删 subtask_executed/blocked/stopped）
- TaskExecuteTool 改为 Object.assign({}, defineAdvanceTool(deps), {name:'reqboard_task_execute', description:已弃用}) 真委托，不再各跑一套
- 复验 tests/task-run-contract.test.ts（6 例）及 tools-schema/tools-dispatch/output-contract/apply-wiring/contract-shapes 共 88 例全绿

### 改动文件

- `packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`
- `packages/web/dsh-pmboard/src/tools/AdvanceTool/prompt.ts`
- `packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts`
- `packages/web/dsh-pmboard/tests/task-run-contract.test.ts`

### 下一步

integrate 卡复验别名与 task_run 的同形回执后进 review/test

---
