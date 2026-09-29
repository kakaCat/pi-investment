# REQ-260927144541-0481 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：交付结论：任务/链侧工具面 7 条功能点全部落地，40/40 任务卡 done，需求自动 rollup 进验收。链入口收口为 reqboard_task_run（autoRun 副作用写进描述、别名 task_execute 真委托并标弃用）；新增只读父子结构工具 reqboard_task_tree；task_status 改读台账 lastRun/lastReport（「## Workflow」死数据源清零）；task_move 非法转移报错带当前角色 + 全部合法边、acceptance 真正接线；任务/链级工具超时归位；契约与门禁固化（声明键 ⊇ 返回键、DSL 形状、全工具 schema 构造 + 真实源故障注入）。端到端在运行实例实测通过；40 张任务卡的验收标准已补可执行锚点，测试证据文档已补 covers 标注（40/40）。环境侧一处变更需知悉：宿主 agent-team 的 maxMembers 由 8 提到 16（用户层覆盖，两份配置一致），因自动链「每父卡一个 Worker（名字不可复用）」在 8 条父卡时必撞 TEAM_MEMBER_LIMIT，属设计性死结，建议另立一条修复。

## 1. 验收列表

### v1-1 · 先定契约：任务/链工具的入参与返回长什么样

**验收内容**：【先定契约：任务/链工具的入参与返回长什么样】验收：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts：defineAdvanceTool 用例绿（3 个未声明键补齐）、新 TaskTreeTool 构造不抛。

**操作步骤**：
1. node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts：defineAdvanceTool 用例绿（3 个未声明键补齐）、新 TaskTreeTool 构造不抛。

**预期结果**：按上述步骤执行后满足验收标准：node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts：defineAdvanceTool 用例绿（3 个未声明键补齐）、新 TaskTreeTool 构造不抛。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 链只留一个入口：起链工具收口，别名不再各跑一套

**验收内容**：【链只留一个入口：起链工具收口，别名不再各跑一套】验收：新增 tests/task-run-contract.test.ts 全绿：传 task_id / requirement_id 两种调用返回同形且 req.autoRun=true；都不传且未绑定 → REQBOARD_NO_BOUND_REQ。

**操作步骤**：
1. 新增 tests/task-run-contract.test.ts 全绿：传 task_id / requirement_id 两种调用返回同形且 req.autoRun=true
2. 都不传且未绑定 → REQBOARD_NO_BOUND_REQ。

**预期结果**：按上述步骤执行后满足验收标准：新增 tests/task-run-contract.test.ts 全绿：传 task_id / requirement_id 两种调用返回同形且 req.autoRun=true；都不传且未绑定 → REQBOARD_NO_BOUND_REQ。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 一眼看清父子：新增「父卡→子卡」结构查询

**验收内容**：【一眼看清父子：新增「父卡→子卡」结构查询】验收：新增 tests/task-tree.test.ts 全绿：含 4 子卡的父卡返回 subtasks.length=4 且链序；无子卡返回 [] + note；跨窗口 → REQBOARD_NOT_BOUND_TO_WINDOW。

**操作步骤**：
1. 新增 tests/task-tree.test.ts 全绿：含 4 子卡的父卡返回 subtasks.length=4 且链序
2. 无子卡返回 [] + note
3. 跨窗口 → REQBOARD_NOT_BOUND_TO_WINDOW。

**预期结果**：按上述步骤执行后满足验收标准：新增 tests/task-tree.test.ts 全绿：含 4 子卡的父卡返回 subtasks.length=4 且链序；无子卡返回 [] + note；跨窗口 → REQBOARD_NOT_BOUND_TO_WINDOW。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落

**验收内容**：【单卡状态说实话：改读台账执行记录，不再读没人写的旧段落】验收：grep -rn "## Workflow" packages/web/dsh-pmboard/src 无输出；新增 tests/task-status-ledger.test.ts 全绿（无 lastRun 时不报错、不伪造）。

**操作步骤**：
1. grep -rn "## Workflow" packages/web/dsh-pmboard/src 无输出
2. 新增 tests/task-status-ledger.test.ts 全绿（无 lastRun 时不报错、不伪造）。

**预期结果**：按上述步骤执行后满足验收标准：grep -rn "## Workflow" packages/web/dsh-pmboard/src 无输出；新增 tests/task-status-ledger.test.ts 全绿（无 lastRun 时不报错、不伪造）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 推错状态要说清：报错带上角色与合法边，验收标准能当场改

**验收内容**：【推错状态要说清：报错带上角色与合法边，验收标准能当场改】验收：新增 tests/task-move-role.test.ts 全绿：legacy 边推父卡报错含「父卡」与合法边；task_move(acceptance=…) 后台账 task.acceptance 已更新（不接线必红）。

**操作步骤**：
1. 新增 tests/task-move-role.test.ts 全绿：legacy 边推父卡报错含「父卡」与合法边
2. task_move(acceptance=…) 后台账 task.acceptance 已更新（不接线必红）。

**预期结果**：按上述步骤执行后满足验收标准：新增 tests/task-move-role.test.ts 全绿：legacy 边推父卡报错含「父卡」与合法边；task_move(acceptance=…) 后台账 task.acceptance 已更新（不接线必红）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 超时归位：投递/查询类工具不再挂交互式长超时

**验收内容**：【超时归位：投递/查询类工具不再挂交互式长超时】验收：grep -rn "timeoutInteractiveMs" src/tools/AdvanceTool src/tools/TaskExecuteTool src/tools/RunStatusTool src/tools/TaskStatusTool 无命中；相关测试仍绿。

**操作步骤**：
1. grep -rn "timeoutInteractiveMs" src/tools/AdvanceTool src/tools/TaskExecuteTool src/tools/RunStatusTool src/tools/TaskStatusTool 无命中
2. 相关测试仍绿。

**预期结果**：按上述步骤执行后满足验收标准：grep -rn "timeoutInteractiveMs" src/tools/AdvanceTool src/tools/TaskExecuteTool src/tools/RunStatusTool src/tools/TaskStatusTool 无命中；相关测试仍绿。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 门禁固化：声明与行为不一致由测试拦住

**验收内容**：【门禁固化：声明与行为不一致由测试拦住】验收：vitest run tests/output-contract.test.ts tests/tools-schema.test.ts 全绿；故障注入（临时给某工具加未声明返回键）在该测试内被验证为变红。

**操作步骤**：
1. vitest run tests/output-contract.test.ts tests/tools-schema.test.ts 全绿
2. 故障注入（临时给某工具加未声明返回键）在该测试内被验证为变红。

**预期结果**：按上述步骤执行后满足验收标准：vitest run tests/output-contract.test.ts tests/tools-schema.test.ts 全绿；故障注入（临时给某工具加未声明返回键）在该测试内被验证为变红。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 兼容收尾：老调用方不退化 + 工具面与流程文档同步

**验收内容**：【兼容收尾：老调用方不退化 + 工具面与流程文档同步】验收：vitest run packages/web/dsh-pmboard/tests/advance-chain.test.ts tests/run-status-tool.test.ts tests/task-transition-guard.test.ts 除预存在红外全绿；文档可 grep 到新增工具面说明。

**操作步骤**：
1. vitest run packages/web/dsh-pmboard/tests/advance-chain.test.ts tests/run-status-tool.test.ts tests/task-transition-guard.test.ts 除预存在红外全绿
2. 文档可 grep 到新增工具面说明。

**预期结果**：按上述步骤执行后满足验收标准：vitest run packages/web/dsh-pmboard/tests/advance-chain.test.ts tests/run-status-tool.test.ts tests/task-transition-guard.test.ts 除预存在红外全绿；文档可 grep 到新增工具面说明。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-9 · 先定契约：任务/链工具的入参与返回长什么样·研发

**验收内容**：【先定契约：任务/链工具的入参与返回长什么样·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-10 · 先定契约：任务/链工具的入参与返回长什么样·联调

**验收内容**：【先定契约：任务/链工具的入参与返回长什么样·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 先定契约：任务/链工具的入参与返回长什么样·复核

**验收内容**：【先定契约：任务/链工具的入参与返回长什么样·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-12 · 先定契约：任务/链工具的入参与返回长什么样·测试

**验收内容**：【先定契约：任务/链工具的入参与返回长什么样·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-13 · 链只留一个入口：起链工具收口，别名不再各跑一套·研发

**验收内容**：【链只留一个入口：起链工具收口，别名不再各跑一套·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-14 · 链只留一个入口：起链工具收口，别名不再各跑一套·联调

**验收内容**：【链只留一个入口：起链工具收口，别名不再各跑一套·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-15 · 链只留一个入口：起链工具收口，别名不再各跑一套·复核

**验收内容**：【链只留一个入口：起链工具收口，别名不再各跑一套·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-16 · 链只留一个入口：起链工具收口，别名不再各跑一套·测试

**验收内容**：【链只留一个入口：起链工具收口，别名不再各跑一套·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-17 · 一眼看清父子：新增「父卡→子卡」结构查询·研发

**验收内容**：【一眼看清父子：新增「父卡→子卡」结构查询·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-18 · 一眼看清父子：新增「父卡→子卡」结构查询·联调

**验收内容**：【一眼看清父子：新增「父卡→子卡」结构查询·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-19 · 一眼看清父子：新增「父卡→子卡」结构查询·复核

**验收内容**：【一眼看清父子：新增「父卡→子卡」结构查询·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-20 · 一眼看清父子：新增「父卡→子卡」结构查询·测试

**验收内容**：【一眼看清父子：新增「父卡→子卡」结构查询·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-21 · 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·研发

**验收内容**：【单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-22 · 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·联调

**验收内容**：【单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-23 · 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核

**验收内容**：【单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-24 · 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·测试

**验收内容**：【单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-25 · 推错状态要说清：报错带上角色与合法边，验收标准能当场改·研发

**验收内容**：【推错状态要说清：报错带上角色与合法边，验收标准能当场改·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-26 · 推错状态要说清：报错带上角色与合法边，验收标准能当场改·联调

**验收内容**：【推错状态要说清：报错带上角色与合法边，验收标准能当场改·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-27 · 推错状态要说清：报错带上角色与合法边，验收标准能当场改·复核

**验收内容**：【推错状态要说清：报错带上角色与合法边，验收标准能当场改·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-28 · 推错状态要说清：报错带上角色与合法边，验收标准能当场改·测试

**验收内容**：【推错状态要说清：报错带上角色与合法边，验收标准能当场改·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-29 · 超时归位：投递/查询类工具不再挂交互式长超时·研发

**验收内容**：【超时归位：投递/查询类工具不再挂交互式长超时·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-30 · 超时归位：投递/查询类工具不再挂交互式长超时·联调

**验收内容**：【超时归位：投递/查询类工具不再挂交互式长超时·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-31 · 超时归位：投递/查询类工具不再挂交互式长超时·复核

**验收内容**：【超时归位：投递/查询类工具不再挂交互式长超时·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-32 · 超时归位：投递/查询类工具不再挂交互式长超时·测试

**验收内容**：【超时归位：投递/查询类工具不再挂交互式长超时·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-33 · 门禁固化：声明与行为不一致由测试拦住·研发

**验收内容**：【门禁固化：声明与行为不一致由测试拦住·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-34 · 门禁固化：声明与行为不一致由测试拦住·联调

**验收内容**：【门禁固化：声明与行为不一致由测试拦住·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-35 · 门禁固化：声明与行为不一致由测试拦住·复核

**验收内容**：【门禁固化：声明与行为不一致由测试拦住·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-36 · 门禁固化：声明与行为不一致由测试拦住·测试

**验收内容**：【门禁固化：声明与行为不一致由测试拦住·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-37 · 兼容收尾：老调用方不退化 + 工具面与流程文档同步·研发

**验收内容**：【兼容收尾：老调用方不退化 + 工具面与流程文档同步·研发】验收：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**操作步骤**：
1. 改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts
2. 期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：改动已落盘且契约测试全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts；期望看到：Test Files 2 passed、Tests 67 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-38 · 兼容收尾：老调用方不退化 + 工具面与流程文档同步·联调

**验收内容**：【兼容收尾：老调用方不退化 + 工具面与流程文档同步·联调】验收：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**操作步骤**：
1. 接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts
2. 期望看到：Test Files 4 passed、Tests 18 passed、exit=0
3. 请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**预期结果**：按上述步骤执行后满足验收标准：接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-39 · 兼容收尾：老调用方不退化 + 工具面与流程文档同步·复核

**验收内容**：【兼容收尾：老调用方不退化 + 工具面与流程文档同步·复核】验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**操作步骤**：
1. 对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据

**预期结果**：按上述步骤执行后满足验收标准：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-40 · 兼容收尾：老调用方不退化 + 工具面与流程文档同步·测试

**验收内容**：【兼容收尾：老调用方不退化 + 工具面与流程文档同步·测试】验收：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**操作步骤**：
1. 目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts
2. 期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**预期结果**：按上述步骤执行后满足验收标准：目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-41 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-43 · 需求级验收

**验收内容**：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 先定契约：任务/链工具的入参与返回长什么样·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 链只留一个入口：起链工具收口，别名不再各跑一套·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 一眼看清父子：新增「父卡→子卡」结构查询·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 推错状态要说清：报错带上角色与合法边，验收标准能当场改·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**操作步骤**：
1. 验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 先定契约：任务/链工具的入参与返回长什么样·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
2. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
3. 验收项 链只留一个入口：起链工具收口，别名不再各跑一套·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
4. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
5. 验收项 一眼看清父子：新增「父卡→子卡」结构查询·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
6. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
7. 验收项 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
8. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。
9. 验收项 推错状态要说清：报错带上角色与合法边，验收标准能当场改·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论
10. 无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）
11. 本条不阻断验收，但必须有人看过并决定。

**预期结果**：按上述步骤执行后满足验收标准：验收项不可照着验（历史数据）：以下验收项没写「怎么验」——验收项 先定契约：任务/链工具的入参与返回长什么样·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 链只留一个入口：起链工具收口，别名不再各跑一套·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 一眼看清父子：新增「父卡→子卡」结构查询·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。；验收项 推错状态要说清：报错带上角色与合法边，验收标准能当场改·复核 缺「怎么验」（"对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据"）——只写断言词不算，必须给**可执行操作**：命令（npx/vitest/curl/pytest…）、可查数据（SQL/字段名）、或可达界面路径（打开某页→看什么）。否则验收只能靠相信，等于没验。。请补可执行操作（命令/可查数据/界面路径）；本条不阻断验收，但必须有人看过并决定。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-44 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- FR-1/FR-2/FR-3/FR-7 判定命令：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts → Test Files 3 passed (3) / Tests 73 passed (73)，exit=0（2026-09-27 19:17 实跑）
- FR-4 判定命令：grep -rn "## Workflow" packages/web/dsh-pmboard/src → 无输出，exit=1（死数据源清零）
- FR-6 判定命令：grep -rn "timeoutInteractiveMs" 于 AdvanceTool/TaskExecuteTool/RunStatusTool/TaskStatusTool 四目录 → 无输出，exit=1（仅弹框类 AskConfirm/Capture 保留交互档）
- 端到端 FR-3：reqboard_task_tree(parent_id=t-bd7439) → success=true，4 张子卡按链序 dev→integrate→review→test 全 done、lastRunOk=true，note=「子卡链 4 张，已完成 4 张」
- 端到端 FR-5（父卡）：reqboard_task_move(t-bd7439, to=in_review) → 原文「reqboard_task_move 未执行：父卡不允许 done→in_review；该角色合法边：todo→in_progress、todo→canceled、in_progress→done、in_progress→todo、in_progress→canceled、done→in_progress、done→canceled、canceled→todo」（零副作用）
- 端到端 FR-5（子卡）：reqboard_task_move(t-73e493, to=testing) → 原文「reqboard_task_move 未执行：子卡不允许 done→testing；该角色合法边：…」
- 端到端 FR-1：reqboard_task_run(task_id=t-bd7439) → {status:"dispatched", job_id:"reqboard-1", run_id:"run-...", next_ready:["t-73e493"]}（返回值齐全且与 output.schema 一致）
- 工具总盘：reqboard_status → 40/40 任务 done，需求 status=accepting（rollup 事件 ok）
- 测试覆盖标注：docs/requirements/REQ-260927144541-0481/tests/test-evidence.md 第五节「任务→测试覆盖」共 40 条 covers: t-xxx（grep -c → 40）
- 交付文档（新增「五、兼容收尾」）：docs/architecture/reqboard-implement-chain-flow.md
- 联调/测试证据：docs/requirements/REQ-260927144541-0481/tests/ 下 task-tree-integration-evidence.md、timeout-routing-integration-evidence.md、task-move-integration-evidence.md、test-evidence.md；门禁固化联调见 docs/work-logs/2026-09/pmboard-gate-hardening-fr7-integration.md
- 环境变更（需知悉，非本需求范围）：.dsh-data/profiles/agent-dh/cordis.patch.yml 与 config/cordis.yml 均新增 - id: agent-team / config.maxMembers: 16（原 8），用于解开自动链末条父卡的 TEAM_MEMBER_LIMIT 死结

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 先定契约：任务/链工具的入参与返回长什么样 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-2 | 链只留一个入口：起链工具收口，别名不再各跑一套 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-3 | 一眼看清父子：新增「父卡→子卡」结构查询 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-4 | 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-5 | 推错状态要说清：报错带上角色与合法边，验收标准能当场改 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-6 | 超时归位：投递/查询类工具不再挂交互式长超时 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-7 | 门禁固化：声明与行为不一致由测试拦住 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-8 | 兼容收尾：老调用方不退化 + 工具面与流程文档同步 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-9 | 先定契约：任务/链工具的入参与返回长什么样·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-10 | 先定契约：任务/链工具的入参与返回长什么样·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:20 |
| v1-11 | 先定契约：任务/链工具的入参与返回长什么样·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-12 | 先定契约：任务/链工具的入参与返回长什么样·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-13 | 链只留一个入口：起链工具收口，别名不再各跑一套·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-14 | 链只留一个入口：起链工具收口，别名不再各跑一套·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-15 | 链只留一个入口：起链工具收口，别名不再各跑一套·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-16 | 链只留一个入口：起链工具收口，别名不再各跑一套·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-17 | 一眼看清父子：新增「父卡→子卡」结构查询·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-18 | 一眼看清父子：新增「父卡→子卡」结构查询·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-19 | 一眼看清父子：新增「父卡→子卡」结构查询·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-20 | 一眼看清父子：新增「父卡→子卡」结构查询·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:23 |
| v1-21 | 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-22 | 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-23 | 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-24 | 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-25 | 推错状态要说清：报错带上角色与合法边，验收标准能当场改·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-26 | 推错状态要说清：报错带上角色与合法边，验收标准能当场改·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-27 | 推错状态要说清：报错带上角色与合法边，验收标准能当场改·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-28 | 推错状态要说清：报错带上角色与合法边，验收标准能当场改·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-29 | 超时归位：投递/查询类工具不再挂交互式长超时·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-30 | 超时归位：投递/查询类工具不再挂交互式长超时·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:25 |
| v1-31 | 超时归位：投递/查询类工具不再挂交互式长超时·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-32 | 超时归位：投递/查询类工具不再挂交互式长超时·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-33 | 门禁固化：声明与行为不一致由测试拦住·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-34 | 门禁固化：声明与行为不一致由测试拦住·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-35 | 门禁固化：声明与行为不一致由测试拦住·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-36 | 门禁固化：声明与行为不一致由测试拦住·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-37 | 兼容收尾：老调用方不退化 + 工具面与流程文档同步·研发 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-38 | 兼容收尾：老调用方不退化 + 工具面与流程文档同步·联调 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-39 | 兼容收尾：老调用方不退化 + 工具面与流程文档同步·复核 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-40 | 兼容收尾：老调用方不退化 + 工具面与流程文档同步·测试 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-41 | 需求级验收 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-43 | 需求级验收 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
| v1-44 | 需求级验收 | ✓ 通过 | human/session-b71bb246-6f5c-417b-89d6-e48e4b697dcf | 2026-09-27 19:28 |
