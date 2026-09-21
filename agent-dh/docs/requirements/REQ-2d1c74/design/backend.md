---
req: REQ-2d1c74
kind: design
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 后端实施设计（REQ-2d1c74）

## 1. 文件改动清单（serves: FR-1, FR-2, FR-3, FR-5）

| 文件（相对 packages/pages/dsh-pmboard/） | 动作 | 要点 |
|---|---|---|
| src/application/internal/category-doc-sets.ts | 改 | ConditionalDesignDoc + designDocPolicyFrom + missingCategoryDocs 扩展 |
| src/application/internal/content-gates.ts | 改 | 新增 detectDecompositionFeatures（剥围栏代码块后判定） |
| src/application/internal/content-gate-wiring.ts | 改 | 新增 checkDesignCompletenessGate / checkDesignDecompositionGate / assertArtifactOpenable |
| src/application/internal/artifact-gates.ts | 改 | GateFailure 扩两码；design 门改"全部确认"判定 |
| src/application/use-cases/ConfirmArtifact.ts | 改 | kind=design 成组落章 + 落章前扫描 |
| src/application/use-cases/AskConfirm.ts | 改 | 落章前扫描 + 成组落章 + 推进块补完整性闸门（现状不过任何产物闸） |
| src/application/use-cases/MoveRequirement.ts | 改 | 转移前调完整性闸门 |
| src/application/use-cases/SubmitArtifact.ts | 改 | 两入口登记前调 assertArtifactOpenable |
| src/adapters/ArtifactSync.ts | 改 | 登记路径形态过滤（防御） |
| src/http/routers/requirements.ts | 改 | 看板确认/移动两入口同样接线 |
| tests/ 新增 5 个测试文件 | 增 | 见 test-cases.md §1 |

## 2. 接线细节（serves: FR-2, FR-3）

- **转移四路径**：MoveRequirement 与 http 移动入口在 assertArtifactGates 之外再调
  checkDesignCompletenessGate；AskConfirm 推进块与看板确认后推进块**现状不过闸**，
  本次两处都补上两道校验（先完整性、后走原 transitionRequirement）。判定顺序：
  内容扫描（确认时）→ 成组落章 → 转移时完整性复核（防确认后新增未确认文档）。
- **确认三通道**：ConfirmArtifact（文字证据）、AskConfirm（弹框）、http handleArtifactConfirm
  （看板）在写 confirmedAt 之前统一调 checkDesignDecompositionGate；命中即 reject，
  不落章、不推进、只留评论留痕。
- 状态字面量比较只出现在 application 层（本仓 INV 约束），tools/http 壳只调用。

## 3. 迁移与兼容（serves: FR-6）

- **无台账 schema 变更、无迁移版本**：全部新逻辑是"读取既有字段 + 新增校验"。
- **isLegacy 豁免语义不变**：artifacts 空/undefined 的需求，新闸门与既有闸门同样放行。
- **在途 feature 需求的过渡**：文档集从 4 份扩到 5 份+条件必交后，处于 design/decomposing 的
  在途需求会被新要求命中——官方逃生口 = 在 requirement.md front-matter 补 design_exempt
  声明（或补交文档）；上线时由本需求的实施任务给在途需求逐一核查并代录豁免。
- **decomposing 既有门禁不回退**：missingCategoryDocs 新参数可选，plan_submit 调用点
  只增传 sides/exempt，原有断言不动。
- **回滚路径**：纯代码 revert 即回退；无数据回填、无开关残留。

## 4. 提示词与指南修正（serves: FR-4）

- `src/domain/prompt/fragments/design/heavy/overrides.md`：覆盖 1/3/5 删除
  "submit(kind=plan) / ask_confirm(target=plan)" 表述，改写为"落盘 design/*.md →
  ask_confirm(target=artifact, kind=design)"（与 light/heavy 主档的 2026-09-21 裁定语义对齐）；
  覆盖 2（不含最终任务 DAG）保留并强化"任务表属拆分阶段"。
- `docs/guides/reqboard-workflow.md`：第 18 行闸门边（G2=确认设计文档 design>decomposing、
  G3=批准拆分计划 decomposing>implementing）、第 38 行设计步骤（删"拆分计划 → submit(kind=plan)"）、
  第 50 行硬要求（拆分计划只在 decomposing 提交）三处改写；第 23-24 行过时更正注记一并更新。
- 修正后跑 `node scripts/inline-prompt-fragments.mjs`，以 `check-prompt-fragments.mjs` 字节级同步门禁收口。
