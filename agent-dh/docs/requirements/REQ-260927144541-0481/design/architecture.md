---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# 架构设计（REQ-260927144541-0481）

> 读者：工程 / agent。本需求**只改任务/链级工具面**，不改状态机、凭证门与编排。

## 分层与两族边界 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 -->

三层不变：`tools/*`（薄壳：参数 + schema + 委托）→ `application/use-cases/*`（编排）→ `domain/*`（纯判定）。
任务/链族 = `task_run` / `task_execute` / `run_status` / `task_status` / `task_move` / `task_report` + 拟新增 `task_tree`；
需求族（本需求不碰）= `create/capture/status/submit/move/ask_confirm/confirm_receipt/accept_sheet/note_interruption/clear_pause/decompose`。

4 处必须耦合（有意设计，保留）：① 窗口绑定校验 `openRequirementsFor`；② `decompose` 是需求→任务的桥；
③ 停手守卫 `assertNoPendingConfirm` 跨层拦任务写路径；④ `task_run` 写 `req.autoRun` + 链尾 rollup 改 `req.status`。

## 本需求改动落点 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 -->

| 文件 | 改动 | serves |
|---|---|---|
| `src/tools/AdvanceTool/AdvanceTool.ts` | 参数支持 `requirement_id`；返回体与 schema 对齐；描述写明开 autoRun | FR-1, FR-2 |
| `src/tools/AdvanceTool/prompt.ts` | 文案补「调用即开启 autoRun」与参数语义 | FR-1 |
| `src/tools/TaskExecuteTool/TaskExecuteTool.ts` | 改为真委托（复用同用例与返回体），标 deprecated | FR-1 |
| `src/tools/TaskTreeTool/TaskTreeTool.ts`（新增）+ prompt | 只读父子结构视图 | FR-3 |
| `src/tools/TaskStatusTool/TaskStatusTool.ts` | 删 `## Workflow` 解析与直连 fs；改读台账并经端口 | FR-4 |
| `src/application/use-cases/MoveTask.ts` + `TaskMoveTool.ts` | 角色感知报错；接线 `amendTaskAcceptanceIfRequested` | FR-5 |
| 上述工具的 `timeoutMs` | 归位到 `timeoutWriteMs`/`timeoutReadMs` | FR-6 |
| `tests/output-contract.test.ts` / `tests/tools-schema.test.ts` | 契约门禁覆盖全工具 + 故障注入 | FR-7 |

## 不变量 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 -->

1. 父卡三态 / 子卡四态 / legacy 五段转移表**取值不变**；本需求只改「报错怎么说」与「参数长什么样」。
2. 子卡凭证口径（run completed + 汇报 + 文件 mtime）**不变**；父卡收尾门（子卡全 done）**不变**。
3. `expandSubtasks` 懒展开时机与幂等**不变**。
4. 非法转移仍拒绝且零副作用——只把「为什么拒」说清。

## 回滚路径 <!-- serves: FR-2, FR-4, FR-7 -->

零数据迁移（只动工具壳与两个用例的报文/参数），回滚 = 回退 dsh-pmboard 构建 + 重启；台账无 schema 变更。
