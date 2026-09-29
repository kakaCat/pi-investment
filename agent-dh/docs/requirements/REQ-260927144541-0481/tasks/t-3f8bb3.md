# t-3f8bb3 一眼看清父子：新增「父卡→子卡」结构查询·研发

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
一眼看清父子：新增「父卡→子卡」结构查询·研发

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

## 汇报 1（2026-09-27T08:59:34.364Z，窗口 7a259a2b-3735-413a-bb9d-d8ce20ed3286）

dev：TaskTree 用例 + TaskTreeTool（reqboard_task_tree）只读父子结构查询已落盘并在 src/index.ts 注册；task-tree 测试 6/6 绿，相关契约测试无 TaskTree 相关回归。

### 完成项

- src/application/use-cases/TaskTree.ts：executeTaskTree 只读视图（deps.repo.snapshot）；绑定校验（显式 requirement_id 须属本窗口绑定，否则 REQBOARD_NOT_BOUND_TO_WINDOW）；parent_id 缺省列出全部顶层父卡；子卡按 dependsOn 链序（成环/悬空回退插入序不抛）；节点投影 id/title/status/role/stageKind/dependsOn/attempt/lastRunOk/reportSummary/cardDoc；无子卡 note="该父卡尚未开工展开子卡链"
- src/tools/TaskTreeTool/{TaskTreeTool.ts,prompt.ts,index.ts}：工具壳 reqboard_task_tree，parameters={parent_id?,requirement_id?}，output.schema 与 design/data-model 视图模型一致，renderSmart 摘要
- src/tools/index.ts 导出 defineTaskTreeTool；src/index.ts 在 apply() 内 toolsCtx.tools.register(defineTaskTreeTool(useCaseDeps)) 注册
- tests/task-tree.test.ts 覆盖 TC-5（含 4 张子卡按链序 + stageKind/status/lastRunOk/摘要/cardDoc）、TC-6（无子卡 []+note）、TC-7（跨窗口 REQBOARD_NOT_BOUND_TO_WINDOW）、未绑定 REQBOARD_NO_BOUND_REQ、REQBOARD_TASK_NOT_FOUND

### 改动文件

- `packages/web/dsh-pmboard/src/application/use-cases/TaskTree.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/TaskTreeTool.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/prompt.ts`
- `packages/web/dsh-pmboard/src/tools/TaskTreeTool/index.ts`
- `packages/web/dsh-pmboard/src/tools/index.ts`
- `packages/web/dsh-pmboard/src/index.ts`
- `packages/web/dsh-pmboard/tests/task-tree.test.ts`

### 下一步

integrate 卡：用请求样例（parent_id=t-p）实测返回体与 design/interfaces I-3 期望一致

---
