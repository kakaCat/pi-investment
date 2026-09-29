---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# 交付评审（本轮自评）（REQ-260927144541-0481）

> **性质声明**：这是**本轮实施窗口对自己交付物的自评**（设计 ↔ 实现逐条对账 + 偏离与债务清单），
> 不是独立第三方评审。独立评审若由自动链的 review 子卡产出，以那一份为准。

## 一、设计 ↔ 实现对账

| 设计条目 | 实现落点 | 判定 |
|---|---|---|
| I-1 `reqboard_task_run`：参数 + requirement_id；返回体对齐；描述补 autoRun | [AdvanceTool.ts](../../../../packages/web/dsh-pmboard/src/tools/AdvanceTool/AdvanceTool.ts)、[prompt.ts](../../../../packages/web/dsh-pmboard/src/tools/AdvanceTool/prompt.ts) | ✅ 12 键声明 vs 实际返回逐键覆盖；删 `subtask_executed/blocked/stopped` |
| I-2 `reqboard_task_execute`：真委托 + deprecated | [TaskExecuteTool.ts](../../../../packages/web/dsh-pmboard/src/tools/TaskExecuteTool/TaskExecuteTool.ts) | ✅ 复用同一 factory 产物（同参数/同返回/同副作用），无第二套实现 |
| I-3 `reqboard_task_tree`（新增，只读） | [TaskTreeTool.ts](../../../../packages/web/dsh-pmboard/src/tools/TaskTreeTool/TaskTreeTool.ts)、[TaskTree.ts](../../../../packages/web/dsh-pmboard/src/application/use-cases/TaskTree.ts) | ✅ 经 `deps.repo` 只读；跨窗口显式拒绝；无子卡 `[]` + note |
| I-4 `task_status` 换台账源 | [TaskStatusTool.ts](../../../../packages/web/dsh-pmboard/src/tools/TaskStatusTool/TaskStatusTool.ts) | ✅ 删段落解析与 `fs` 直连；`workflow` 键保留、内容换 run 摘要 |
| I-5 `task_move` 角色报错 + `acceptance` | [TaskStatus.ts](../../../../packages/web/dsh-pmboard/src/domain/task/TaskStatus.ts)、[MoveTask.ts](../../../../packages/web/dsh-pmboard/src/application/use-cases/MoveTask.ts)、[TaskMoveTool.ts](../../../../packages/web/dsh-pmboard/src/tools/TaskMoveTool/TaskMoveTool.ts) | ✅ 报错形如「reqboard_task_move 未执行：父卡不允许 in_progress→in_review；该角色合法边：…」；`acceptance` 真正落库 + 卡文档同步 |
| I-6 契约门禁：声明 ⊇ 返回 + DSL 形状 + 全工具 | [output-contract.test.ts](../../../../packages/web/dsh-pmboard/tests/output-contract.test.ts)、[tools-schema.test.ts](../../../../packages/web/dsh-pmboard/tests/tools-schema.test.ts) | ✅ 全 18 工具构造 + 源码级 DSL 形状检查 + 两条故障注入 |

## 二、偏离设计的改动（如实列出，均已自测）

1. **超出 P7 边界的三处门禁侧修复**（行为零变更）：`RESPONSE_SOURCES` 补 RunStatus / ClearPause 映射（此前门禁**看不到**这两个工具），
   TaskMoveTool 输出 schema 补 `version/subtasks_created/task_card`（用例实际返回、绑定层会拒收）。
   理由：FR-7 的判定是"全工具 + 两文件全绿"，不补则该项无法成立；补的只是**声明侧**，不改任何工具行为。
2. **两处测试清单更新**：`tools-dispatch` 目录清单（补 ClearPause/RunStatus/TaskTree，并显式留债 5 个缺 prompt.ts 的目录）、
   `apply-wiring` 注册清单（17 → 18）。不更新则新增工具必然打红——清单本身是要维护的产物。
3. **`TaskExecuteTool` 不写成 `return { … }` 包装对象**：output-contract 的静态扫描会把工具返回体的顶层键当协议响应键，
   包装对象会制造假阳性；改为 `Object.assign` 复用同一 factory 产物。

## 三、已知债务（不在本需求范围，显式登记）

| 债务 | 现状 | 归属 |
|---|---|---|
| 5 个工具目录缺 `prompt.ts` | Decompose / Move / TaskExecute / TaskMove / TaskStatus | 工具面清理（另立项） |
| `clear_pause` 旧式 `parameters.schema` | 全仓唯一；tools-schema 里显式豁免并加注释 | 需求级工具治理（P7 / 另立项） |
| 9 个 src 文件超 400 行 | AdvanceChain 497 / ports 409 / index 457… | 既存（开工前即红） |
| 消息卫生棘轮 | application 189（> 基线 140）、http 22 | 他线既存红；本次未加重（tools 47→29） |
| 全量残留红 26 files / 124 tests | 均非本需求改动引起 | 见测试证据 §二 |

## 四、未闭环（需人裁决）

**D17 结构性死路**：需求 `autoRun=true`，开一张计划卡即懒展开 4 张子卡，而子卡转 done 必须持有**真实 workflow run 证据**
（`lastRun.ok`，全仓只由 `executeSubtask` 写入）、父卡又要等子卡全 done，另有 60s 批量关闭节流——
"手工把活干完"无法通过手工推卡收口。用户已裁定：**本轮以代码交付为准，台账由人处理**。
故本需求的 `accepting` 交棒依赖台账侧决策（关闭/取消自动展开的子卡，或驱动自动链）。详见
[reqboard-implement-chain-flow.md](../../../architecture/reqboard-implement-chain-flow.md) 的 D17 追加记录。

## 五、结论

代码交付**完成且可复核**（证据见 [tests/test-evidence.md](../tests/test-evidence.md)）：7 个功能点逐条落地、
两处自有门禁 66/66 全绿、全套无新增红、类型错误零新增。剩下的只有台账收口，按用户裁定交回。
