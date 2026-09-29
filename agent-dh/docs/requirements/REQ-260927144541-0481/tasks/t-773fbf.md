# t-773fbf 超时归位：投递/查询类工具不再挂交互式长超时·测试

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
超时归位：投递/查询类工具不再挂交互式长超时·测试

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

目标命令输出全绿——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/output-contract.test.ts packages/web/dsh-pmboard/tests/tools-schema.test.ts packages/web/dsh-pmboard/tests/task-tree.test.ts；期望看到：Test Files 3 passed、Tests 73 passed、exit=0

## 汇报 1（2026-09-27T10:44:30.295Z，窗口 c811ef10-a880-432a-bff4-f15585116c0f）

FR-6 测试阶段全绿：特性用例与同族回归 5 文件 23 tests、契约门禁与工具壳纪律 4 文件 78 tests 全部通过；FR-6 验收 grep 0 命中（exit=1）；并做故障注入证明该 grep 门禁非空转（注入回归的副本被立刻抓出）。

### 完成项

- [1] FR-6 特性用例 + 同族回归：vitest run timeout-routing-integration(4) / task-run-contract(6) / run-status-tool(4) / task-status-ledger(3) / task-tree(6) → Test Files 5 passed / Tests 23 passed，exit 0
- [2] 契约门禁 + 工具壳纪律：vitest run output-contract(26) / tools-schema(40) / contract-shapes(8) / tools-dispatch(4) → Test Files 4 passed / Tests 78 passed，exit 0（返回键 ⊆ schema、全工具构造 0 抛错、工具壳不得比较状态字面量）
- [3] FR-6 验收判定：grep -rn "timeoutInteractiveMs" src/tools/{AdvanceTool,TaskExecuteTool,RunStatusTool,TaskStatusTool} → 无输出，grep_exit=1（应非 0）✅ TC-12 通过
- [4] 故障注入（证明门禁非空转）：把 AdvanceTool.ts 复制到 mktemp 临时目录并 sed 回注 timeoutInteractiveMs，grep 立刻命中该行（injected_grep_exit=0 = 抓得住），证明 [3] 的「0 命中」是真实检测结果而非正则失效；临时目录已清理，未触碰仓库文件
- 合计：9 个套件文件 / 101 tests 全绿（23 + 78），另有 1 条静态判定命令通过；无红项
- 本卡未改任何仓库文件（结论族凭证形态），filesChanged 留空，不以凑文件充数

---
## 汇报 2（2026-09-27T10:51:51.403Z，窗口 session-b71bb246-6f5c-417b-89d6-e48e4b697dcf）

测试：超时归位验收通过——四个任务/链级工具目录 grep timeoutInteractiveMs 零命中，AdvanceTool 取 timeoutWriteMs(30s)、RunStatus/TaskStatus 取 timeoutReadMs(15s)；相关测试 70 passed / exit 0（2026-09-27 18:51 本机实跑）。

### 完成项

- FR-6 判定：grep -rn timeoutInteractiveMs 于 AdvanceTool/TaskExecuteTool/RunStatusTool/TaskStatusTool → 0 命中（exit=1）
- 取值核对：AdvanceTool.timeoutMs=LIMITS.timeoutWriteMs；RunStatusTool=TaskStatusTool=LIMITS.timeoutReadMs
- 仅剩 AskConfirmTool/CaptureTool 取交互档（弹框类，需求明示允许保留）
- vitest run timeout-routing-integration + output-contract + tools-schema → Test Files 3 passed / Tests 70 passed，exit 0

### 下一步

父卡 t-507969 汇总收尾

---
