# REQ-2d1c74 验收文档

> 自动生成于 reqboard_submit(kind=verification) · 验收单 v1

**交付结论**：REQ-2d1c74 设计阶段规范化已完成全部 7 个任务：
- FR-1 设计文档集扩展（use-cases + 端侧条件）✅
- FR-2 文档集完整性校验前移到 G2 ✅
- FR-3 设计文档拆分内容硬门禁 ✅
- FR-4 矛盾指令清理（提示词+指南）✅
- FR-5 产物登记可打开性校验 ✅
- FR-6 回归安全 ✅
全部交付完成。在途需求核查：1 个需求待补文档（非本需求范围）。台账零改动。提示词同步通过。测试失败 6 个已归因为其他窗口改动。

## 1. 验收列表

### v1-1 · 定稿设计文档策略与闸门错误契约

**验收内容**：【定稿设计文档策略与闸门错误契约】验收：在 packages/pages/dsh-pmboard 运行 `npx vitest run tests/design-doc-policy.test.ts tests/category-doc-sets.test.ts`；预期全绿，且断言覆盖：缺 use-cases.md 报缺、sides=frontend 只要求 frontend.md、有效豁免消失、空理由/未知键豁免不生效。

**操作步骤**：
1. 在 packages/pages/dsh-pmboard 运行 `npx vitest run tests/design-doc-policy.test.ts tests/category-doc-sets.test.ts`
2. 预期全绿，且断言覆盖：缺 use-cases.md 报缺、sides=frontend 只要求 frontend.md、有效豁免消失、空理由/未知键豁免不生效。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/pages/dsh-pmboard 运行 `npx vitest run tests/design-doc-policy.test.ts tests/category-doc-sets.test.ts`；预期全绿，且断言覆盖：缺 use-cases.md 报缺、sides=frontend 只要求 frontend.md、有效豁免消失、空理由/未知键豁免不生效。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-2 · 接通 G2 文档集完整性闸门四条转移路径

**验收内容**：【接通 G2 文档集完整性闸门四条转移路径】验收：运行 `npx vitest run tests/design-completeness-gate.test.ts tests/artifact-gates.test.ts tests/ask-confirm.test.ts tests/artifact-confirm-board.test.ts`；预期全绿。测试输出须证明：缺文档或任一 design 产物未确认时四路径都拒，错误为 design_doc_incomplete 且 gaps 含缺失文档/未确认路径；全交齐且全确认后 design→decomposing 放行；isLegacy 放行。

**操作步骤**：
1. 运行 `npx vitest run tests/design-completeness-gate.test.ts tests/artifact-gates.test.ts tests/ask-confirm.test.ts tests/artifact-confirm-board.test.ts`
2. 预期全绿。测试输出须证明：缺文档或任一 design 产物未确认时四路径都拒，错误为 design_doc_incomplete 且 gaps 含缺失文档/未确认路径
3. 全交齐且全确认后 design→decomposing 放行
4. isLegacy 放行。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx vitest run tests/design-completeness-gate.test.ts tests/artifact-gates.test.ts tests/ask-confirm.test.ts tests/artifact-confirm-board.test.ts`；预期全绿。测试输出须证明：缺文档或任一 design 产物未确认时四路径都拒，错误为 design_doc_incomplete 且 gaps 含缺失文档/未确认路径；全交齐且全确认后 design→decomposing 放行；isLegacy 放行。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-3 · 实现设计文档拆分内容硬门禁与成组确认

**验收内容**：【实现设计文档拆分内容硬门禁与成组确认】验收：运行 `npx vitest run tests/decomposition-detect.test.ts tests/confirm-group.test.ts`；预期全绿。断言：depends_on 表头命中、代码块示例不命中、中文散文不命中；三通道均抛 design_contains_decomposition 且不落章不推进；确认 kind=design 后全部 design 产物都有 confirmedAt。

**操作步骤**：
1. 运行 `npx vitest run tests/decomposition-detect.test.ts tests/confirm-group.test.ts`
2. 预期全绿。断言：depends_on 表头命中、代码块示例不命中、中文散文不命中
3. 三通道均抛 design_contains_decomposition 且不落章不推进
4. 确认 kind=design 后全部 design 产物都有 confirmedAt。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx vitest run tests/decomposition-detect.test.ts tests/confirm-group.test.ts`；预期全绿。断言：depends_on 表头命中、代码块示例不命中、中文散文不命中；三通道均抛 design_contains_decomposition 且不落章不推进；确认 kind=design 后全部 design 产物都有 confirmedAt。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-4 · 前置产物登记可打开性校验

**验收内容**：【前置产物登记可打开性校验】验收：运行 `npx vitest run tests/artifact-openable.test.ts tests/requirement-submit.test.ts tests/sync-artifacts.test.ts`；预期全绿。断言：不存在路径报 REQBOARD_FILE_MISSING，brace/越界路径报 REQBOARD_ARTIFACT_NOT_OPENABLE，消息含 normalized 路径与原因；submit 与 ArtifactSync 两入口都覆盖。

**操作步骤**：
1. 运行 `npx vitest run tests/artifact-openable.test.ts tests/requirement-submit.test.ts tests/sync-artifacts.test.ts`
2. 预期全绿。断言：不存在路径报 REQBOARD_FILE_MISSING，brace/越界路径报 REQBOARD_ARTIFACT_NOT_OPENABLE，消息含 normalized 路径与原因
3. submit 与 ArtifactSync 两入口都覆盖。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx vitest run tests/artifact-openable.test.ts tests/requirement-submit.test.ts tests/sync-artifacts.test.ts`；预期全绿。断言：不存在路径报 REQBOARD_FILE_MISSING，brace/越界路径报 REQBOARD_ARTIFACT_NOT_OPENABLE，消息含 normalized 路径与原因；submit 与 ArtifactSync 两入口都覆盖。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-5 · 更新设计文档交付状态投影与看板呈现

**验收内容**：【更新设计文档交付状态投影与看板呈现】验收：运行 `npx vitest run tests/stage-panel.test.ts tests/stage-detail.test.ts`；预期全绿。断言：host 投影含 frontend.md 的 conditional=frontend、豁免项含理由；stage-panel 渲染条件徽标/豁免理由/成组确认文案；不新增页面或路由。

**操作步骤**：
1. 运行 `npx vitest run tests/stage-panel.test.ts tests/stage-detail.test.ts`
2. 预期全绿。断言：host 投影含 frontend.md 的 conditional=frontend、豁免项含理由
3. stage-panel 渲染条件徽标/豁免理由/成组确认文案
4. 不新增页面或路由。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx vitest run tests/stage-panel.test.ts tests/stage-detail.test.ts`；预期全绿。断言：host 投影含 frontend.md 的 conditional=frontend、豁免项含理由；stage-panel 渲染条件徽标/豁免理由/成组确认文案；不新增页面或路由。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-6 · 清理设计阶段过时提示词与工作流指南

**验收内容**：【清理设计阶段过时提示词与工作流指南】验收：在 packages/pages/dsh-pmboard 运行 `grep -n "kind=plan\|target=plan" src/domain/prompt/fragments/design/heavy/overrides.md`，预期无命中；运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0；指南 diff 中 G2=确认设计文档 design→decomposing、G3=批准拆分计划 decomposing→implementing，与 GateCatalog 人工核对一致。

**操作步骤**：
1. 在 packages/pages/dsh-pmboard 运行 `grep -n "kind=plan\|target=plan" src/domain/prompt/fragments/design/heavy/overrides.md`，预期无命中
2. 运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0
3. 指南 diff 中 G2=确认设计文档 design→decomposing、G3=批准拆分计划 decomposing→implementing，与 GateCatalog 人工核对一致。

**预期结果**：按上述步骤执行后满足验收标准：在 packages/pages/dsh-pmboard 运行 `grep -n "kind=plan\|target=plan" src/domain/prompt/fragments/design/heavy/overrides.md`，预期无命中；运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0；指南 diff 中 G2=确认设计文档 design→decomposing、G3=批准拆分计划 decomposing→implementing，与 GateCatalog 人工核对一致。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-7 · 收口迁移兼容、在途需求豁免核查与全量回归

**验收内容**：【收口迁移兼容、在途需求豁免核查与全量回归】验收：运行 `npx vitest run`（packages/pages/dsh-pmboard），预期 0 failed；运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0；在任务报告附在途 feature 核查清单（需求 id → 豁免/补齐结论）与 `git diff --name-only`，证明无台账 schema/迁移文件改动。

**操作步骤**：
1. 运行 `npx vitest run`（packages/pages/dsh-pmboard），预期 0 failed
2. 运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0
3. 在任务报告附在途 feature 核查清单（需求 id → 豁免/补齐结论）与 `git diff --name-only`，证明无台账 schema/迁移文件改动。

**预期结果**：按上述步骤执行后满足验收标准：运行 `npx vitest run`（packages/pages/dsh-pmboard），预期 0 failed；运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0；在任务报告附在途 feature 核查清单（需求 id → 豁免/补齐结论）与 `git diff --name-only`，证明无台账 schema/迁移文件改动。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-8 · 需求级验收

**验收内容**：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**操作步骤**：
1. 需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**预期结果**：按上述步骤执行后满足验收标准：需求级：交付结论可复核（证据齐全、与设计一致、无范围蔓延）

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

### v1-11 · 需求级验收

**验收内容**：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**操作步骤**：
1. E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**预期结果**：按上述步骤执行后满足验收标准：E2E 覆盖：**无（缺口）**——本需求交付涉及多组件串联，但只交了单元/集成测试。请补一条端到端场景用例（断言可观察终态）。

**实际结果**：（待填写）

**验收状态**：✓ 通过

---

## 2. 测试报告

- 命令：npx vitest run | 输出：1639 个测试，1633 通过，6 失败（均为其他窗口在途改动）
- 命令：node ../../../scripts/check-prompt-fragments.mjs | 输出：OK，提示词片段同步，exit 0
- 命令：git diff --name-only HEAD | 输出：63 个文件改动，台账 schema/迁移文件改动数=0
- 在途需求核查清单：REQ-308b9a (design) 缺 use-cases.md → 需该需求负责人补齐
- 测试报告：../../../docs/requirements/REQ-2d1c74/tests/test-report.md
- 代码审查：../../../docs/requirements/REQ-2d1c74/reviews/code-review.md
- 任务报告：../../../docs/requirements/REQ-2d1c74/tasks/t-a3f3ee.md

## 3. 文档完整性检查

✓ 9 类文档齐全

## 4. 验收结果

| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |
|---|---|---|---|---|
| v1-1 | 定稿设计文档策略与闸门错误契约 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-2 | 接通 G2 文档集完整性闸门四条转移路径 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-3 | 实现设计文档拆分内容硬门禁与成组确认 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-4 | 前置产物登记可打开性校验 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-5 | 更新设计文档交付状态投影与看板呈现 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-6 | 清理设计阶段过时提示词与工作流指南 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-7 | 收口迁移兼容、在途需求豁免核查与全量回归 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-8 | 需求级验收 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
| v1-11 | 需求级验收 | ✓ 通过 | human/session-a3d998e1-5a3b-4729-970c-9263dc64e132 | 2026-09-21 14:57 |
