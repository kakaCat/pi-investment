# t-af0bff 接通 G2 文档集完整性闸门四条转移路径

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
接通 G2 文档集完整性闸门四条转移路径

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：implement
- 端侧：backend

## 得到什么结果
运行 `npx vitest run tests/design-completeness-gate.test.ts tests/artifact-gates.test.ts tests/ask-confirm.test.ts tests/artifact-confirm-board.test.ts`；预期全绿。测试输出须证明：缺文档或任一 design 产物未确认时四路径都拒，错误为 design_doc_incomplete 且 gaps 含缺失文档/未确认路径；全交齐且全确认后 design→decomposing 放行；isLegacy 放行。

## 实施方案（implementation）
修改 src/application/internal/content-gate-wiring.ts：新增 checkDesignCompletenessGate（读 requirement.md front-matter，校验文档集与全部 kind=design 产物 confirmedAt，isLegacy 放行）。修改 src/application/internal/artifact-gates.ts：design 门从 find 第一份改为 filter 全部、任一未确认即拒。把闸门接入 MoveRequirement.ts、AskConfirm.ts 自动推进块、http/routers/requirements.ts 的看板移动入口与看板确认后自动推进块。新增 tests/design-completeness-gate.test.ts 并更新 artifact-gates/ask-confirm/artifact-confirm-board 相关测试。

## 上游产出摘要（dependsSummary）
- 定稿设计文档策略与闸门错误契约

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-21T05:02:35.455Z，窗口 session-a3d998e1-5a3b-4729-970c-9263dc64e132）

设计阶段进拆分前多了两道代码级把门：①feature 需求的设计文档没交齐（五份必交 + 端侧条件必交，豁免须带理由）②任何一份设计文档没经人确认——design→decomposing 的四条推进路径（会话 move、会话弹框确认后自动推进、看板移动、看板确认后自动推进）都会被拦下并列出缺口清单；确认门从「第一份有章就放行」改为「全部有章才放行」，堵住了「确认后又新交一份文档却无人再看」的绕过口。存量老需求（无产物登记）不受影响照常放行。

### 完成项

- design-gates.ts 新模块：checkDesignCompletenessGate——①文档集交齐（读 requirement.md front-matter 的 sides/design_exempt 策略，以 design/ 目录实际落盘为准）②磁盘每份 design/*.md 均有确认章（含未登记的新文档）；isLegacy 放行
- artifact-gates.ts：design 确认门从 find 第一份改为 filter 全部、任一未确认即拒，未确认路径进 gaps
- 四路径接线：MoveRequirement（拒）、AskConfirm 推进块（落章保留、推进拦、gate_failure 结构化返回）、看板移动 handleReqMove（mutate 前只读两级校验）、看板确认后自动推进 handleArtifactConfirm（同弹框语义）
- routes.ts fail() 映射补 design_doc_incomplete/design_contains_decomposition → 400；AskConfirmTool 输出契约声明 gate_failure
- 新增 tests/design-completeness-gate.test.ts（16 用例：缺文档四路径全拒 / 磁盘无章新文档四路径全拒 / 成组确认门先拦 / 全交齐全确认四路径放行 / sides 条件必交 / 豁免生效与空理由无效 / isLegacy 放行）
- 更新 5 处既有测试（artifact-gates/acceptance-criteria 的 G2 夹具改为五份文档集，layer-boundary 的 'design' 字面量改从闸门定义取，size-budget 拆出 design-gates.ts 模块）
- 验收命令四文件 56 用例全绿；全量回归 131 文件 1611 用例全绿；tsc --noEmit 0 错误

### 改动文件

- `packages/pages/dsh-pmboard/src/application/internal/design-gates.ts`
- `packages/pages/dsh-pmboard/src/application/internal/content-gate-wiring.ts`
- `packages/pages/dsh-pmboard/src/application/internal/artifact-gates.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/MoveRequirement.ts`
- `packages/pages/dsh-pmboard/src/application/use-cases/AskConfirm.ts`
- `packages/pages/dsh-pmboard/src/http/routers/requirements.ts`
- `packages/pages/dsh-pmboard/src/http/routes.ts`
- `packages/pages/dsh-pmboard/src/tools/AskConfirmTool/AskConfirmTool.ts`
- `packages/pages/dsh-pmboard/tests/design-completeness-gate.test.ts`
- `packages/pages/dsh-pmboard/tests/artifact-gates.test.ts`
- `packages/pages/dsh-pmboard/tests/acceptance-criteria.test.ts`
- `packages/pages/dsh-pmboard/lib/client.js`

### 下一步

T-3（t-0553af）：设计文档拆分内容硬门禁 + kind=design 成组落章三通道

---
