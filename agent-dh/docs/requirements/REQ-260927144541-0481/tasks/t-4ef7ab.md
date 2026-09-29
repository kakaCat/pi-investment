# t-4ef7ab 链只留一个入口：起链工具收口，别名不再各跑一套·联调

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
链只留一个入口：起链工具收口，别名不再各跑一套·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

## 汇报 1（2026-09-27T08:55:45.048Z，窗口 9eeafe34-d083-497d-8528-299d747edefd）

联调通过：reqboard_task_run（唯一链入口）与兼容别名 reqboard_task_execute 在真实 factory 上逐样例对照一致——请求/响应形状、autoRun 副作用、失败错误码全部与 design/interfaces.md I-1/I-2 相符；别名 output/parameters 与 task_run 深比较相等。

### 完成项

- 样例A {task_id:'t-p'} → {success:true,status:'dispatched',job_id:'job-1',run_id:'run-1000000-*',running:[],next_ready:[],chain:{done:0,total:0},parent_status:'todo'}，且台账 req.autoRun=true
- 样例B {requirement_id:'REQ-000001'} → 与样例A 键集合完全一致（B_sameKeys=true）
- 样例C 别名 reqboard_task_execute：name=reqboard_task_execute，返回同形且同样写 autoRun=true；output/parameters/timeoutMs 与 task_run 深比较相等
- 样例D 都不传且未绑定 → {success:false,status:'error',code:'REQBOARD_NO_BOUND_REQ'}（不静默当成功）
- 样例E 后台端口不可用（同步兼容路径）→ {success:false,status:'error',code:'REQBOARD_DISPATCH_FAILED'}
- 对照 I-1 声明键：实际返回无未声明键（unexpectedKeys=[]），设计 10 键全部已声明；subtask_executed/blocked/stopped 已删除
- 回归：vitest run task-run-contract/tools-schema/tools-dispatch/output-contract/apply-wiring/contract-shapes → 6 文件 88 例全绿

### 改动文件

- `packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts`
- `packages/web/dsh-pmboard/tests/task-run-contract.test.ts`

### 下一步

review 卡按 design I-1/I-2 逐条核对实现偏离

---
