# t-fdb4be 编号串联：给一个编号能查到上下游

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
编号串联：给一个编号能查到上下游

## 背景摘要（context）
（待补充）

## 范围
- 阶段：implement
- 端侧：backend

## 验收标准
给任一 TC-xxx 反查根编号 → 返回成功；serves 指向不存在编号 → 返回拒绝且 dangling 非空

## 实施方案（implementation）
实现 checkNumberChain：解析表格 id/serves 列建图，正反双向查询 + 悬空/孤儿判定

## 上游产出摘要（dependsSummary）
- 文档校验骨架：把标准变成能判的代码

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-18T14:03:16.672Z，窗口 session-e1fc9bb5-906c-4d20-92fc-cbd5f3e2a512）

编号串联接线完成：新增 collectNumberedItems（读需求条款 + 设计章节建编号图）、traceNumber（双向查询：向下列子孙 / 向上回溯到根）、checkNumberChainGate（悬空拒、孤儿只标红），接进 reqboard_plan_submit 的 mutate 之前；工具输出 schema 声明 orphan_clauses。

### 完成项

- content-gate-wiring.ts 新增三件：collectNumberedItems / traceNumber / checkNumberChainGate
- 双向查询 traceNumber：给任一 TC-xxx → up 含根编号 FR-4（满足"反查根编号→返回成功"）；给根编号 → down 列出全部子孙
- 门禁分级（FR-2 ③）：**不悬空**硬拦（dangling_reference + gaps）；**不孤儿**只标红（随 return 返回 orphan_clauses，不锁死提交）
- 接线点选中 SubmitArtifact.ts 的 submitPlanArtifact（计划提交）——放 mutate 之前，拒绝时零副作用；存量需求豁免
- DocsReader 扩展可选 list()，用于枚举 design/*.md（最小假实现不受影响）
- 补 NumberedItem.kind 字段（T-2 实现时漏了，tsc 抓到，与 design/data-model.md 模型对齐）
- 工具输出 schema 声明 orphan_clauses —— 被 output-contract 门禁抓到并修正（本仓铁律：每个 return 分支键必须已声明）
- tests/number-chain-gate.test.ts 8 条：双向查询（含未知编号返回空）、跨文档收集、悬空被拒、孤儿标红、存量豁免、端到端 FR-4 子孙连通
- 重建 client（exit 0 / 与备份一致）；全量 1063 passed，失败回到基线 6 个；tsc 改动面 0 错误

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/content-gate-wiring.ts`
- `packages/pages/dsh-pmboard/src/application/internal/content-gates.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/SubmitArtifact.ts`
- `packages/pages/dsh-pmboard/src/tools/SubmitTool/SubmitTool.ts`
- `packages/pages/dsh-pmboard/tests/number-chain-gate.test.ts`

### 下一步

T-5/T-6/T-7 依赖 T-4（已完成），可继续推进；其中 T-6/T-7 落点（ReportTask/MoveTask 等）可能仍在另一窗口占用面内。

---
