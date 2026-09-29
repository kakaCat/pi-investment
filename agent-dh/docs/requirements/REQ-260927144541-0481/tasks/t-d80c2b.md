# t-d80c2b 超时归位：投递/查询类工具不再挂交互式长超时·联调

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
超时归位：投递/查询类工具不再挂交互式长超时·联调

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果

接口联调可复核——执行：cd /Users/yunpeng/pi-investment/agent-dh && node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts packages/web/dsh-pmboard/tests/task-status-integration.test.ts packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts packages/web/dsh-pmboard/tests/task-move-role.test.ts；期望看到：Test Files 4 passed、Tests 18 passed、exit=0；请求样例与期望响应见 docs/requirements/REQ-260927144541-0481/tests/ 下联调证据

## 汇报 1（2026-09-27T10:43:47.657Z，窗口 c811ef10-a880-432a-bff4-f15585116c0f）

FR-6 超时归位联调通过：四个任务/链级工具 timeoutMs 实取非交互档（投递类 30_000 / 查询类 15_000，无一取 3_600_000 交互档）；样例 6 用线上同款投递端口实测 task_run 立即返回 dispatched，证明 30s 写档不掐线上链。产出联调用例 tests/timeout-routing-integration.test.ts + 证据表 docs/.../tests/timeout-routing-integration-evidence.md。

### 完成项

- 请求样例→期望→实际逐项比对（联调 6 例）：task_run=30_000 ✅、task_execute（别名深比较相等）=30_000 ✅、run_status=15_000 ✅、task_status=15_000 ✅、四工具并排扫描过滤 timeoutInteractiveMs 结果 [] ✅
- 样例 6 线上路径实测（真实 factory + 内存 JobsPort）：reqboard_task_run({task_id:"t-p"}) → success=true / status="dispatched" / job_id="job-integration-1" / run_id 为字符串 / 台账 req.autoRun=true，耗时毫秒级 << 30s 写档 → 「30s 会掐断线上链」的顾虑不成立（长跑只存在于内存/嵌入调用的同步兼容路径）
- FR-6 判定命令原文口径实测：grep -rn "timeoutInteractiveMs" src/tools/{AdvanceTool,TaskExecuteTool,RunStatusTool,TaskStatusTool} → 无输出，exit=1（应非 0）✅；TaskExecuteTool 目录无 timeoutMs 行（真委托别名继承）
- 新增联调用例 packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts（4 例 TC-12a/b/c/d，93 行）
- 联调证据落盘 docs/requirements/REQ-260927144541-0481/tests/timeout-routing-integration-evidence.md（样例表 + 判定命令 + 复现命令 + 副作用核对 + 遗留项）
- 回归 8 套 97 tests 全绿（timeout-routing-integration 4 / task-run-contract 6 / run-status-tool 4 / task-status-ledger 3 / tools-schema 40 / output-contract 26 / contract-shapes 8 / task-tree 6），exit 0
- 副作用核对：联调只读工具属性 + 投递到内存端口，未触碰运行实例、未写真实台账、未 git commit、未 pnpm build
- 遗留（交复核卡 t-fc43f2 判）：内存/嵌入同步兼容路径仍可能跑过 30s 被写档掐断——FR-6 明示取非交互档后的已知取舍，非回归

### 改动文件

- `packages/web/dsh-pmboard/tests/timeout-routing-integration.test.ts`
- `docs/requirements/REQ-260927144541-0481/tests/timeout-routing-integration-evidence.md`

---
