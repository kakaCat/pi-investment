# t-ebe92d 单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核

> 需求：REQ-260927144541-0481 对齐父卡/子卡工具面：链入口收口 + 父子结构可查 + 契约与门禁对齐

## 在做什么
单卡状态说实话：改读台账执行记录，不再读没人写的旧段落·复核

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 得到什么结果
对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

---
## 汇报 1（2026-09-27T10:36:32.387Z，窗口 43eb176c-d21f-451b-a75f-cf3621c17f63）

复核（FR-4 / I-4）：设计契约、落点、数据源、不变量、测试矩阵逐项对照实现——本卡实现与设计无偏离；另附两条口径备注（一条文档歧义、一条越出本卡范围）。

### 完成项

- 【I-4 契约】参数 {task_id} 一致；返回键 success/task_id/status/progress/run?/report?/workflow?/error? 与设计完全一致，无未声明键（output-contract 26/26 绿）
- 【落点·architecture.md L26】删 ## Workflow 解析与直连 fs：grep -rn "## Workflow" src 无输出（exit=1）；TaskStatusTool 内无 node:fs、无 parseWorkflowFromTaskCard
- 【数据源·FR-4 L113】改读台账 task.lastRun/lastReport，经 deps.repo.snapshot() 端口；workflow 键保留、内容为 run 摘要 {at,ok,stopReason,valueNonEmpty}（data-model L48 向后兼容）
- 【不变量·data-model L45】只读：工具内 grep mutate 无命中；状态→进度映射单点 domain/TASK_STATUS_PROGRESS，tools 无状态字面量（layer-boundary 该条通过）
- 【测试矩阵·test-cases L16】FR-4 单元/集成/故障注入(缺 lastRun)/回归四项均有对应用例且绿：task-status-ledger 3/3、task-status-integration 3/3、output-contract 26/26、tools-schema 40/40、tools-dispatch 4/4
- 【结论】本卡（FR-4 / I-4）实现与设计**无偏离**
- 【备注1·文档口径，非实现偏离】data-model.md L46「绑定：只允许读本窗口绑定需求下的任务」标注 serves FR-3,FR-4，但 I-4 未列任何绑定错误码、FR-4 判定与父卡方案均无绑定要求；现状不构成偏离，建议将该约束限定为 FR-3(task_tree) 或在 I-4 补错误语义，避免后续复核歧义
- 【备注2·越出本卡范围】FR-6 验收 grep 仍命中 src/tools/AdvanceTool/AdvanceTool.ts:70 timeoutInteractiveMs——属链入口收口卡（FR-6）范围，非本卡偏离

### 下一步

测试阶段：按 test-cases.md 对 FR-4 的单元/集成/故障注入/回归补执行证据（test 子卡 t-46d23f）。

---
