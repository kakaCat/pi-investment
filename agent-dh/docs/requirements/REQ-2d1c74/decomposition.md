---
req: REQ-2d1c74
kind: plan
requirement_refs: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
---

# 拆分计划（REQ-2d1c74）

## 1. 目标与做法（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

目标：把已确认的 7 份设计文档落成可执行任务卡，使设计阶段职责纯净——feature 设计文档集扩展为
五份必交 + 端侧条件必交；G2 前进拆分的四条路径都被文档集完整性与成组确认闸门兜住；三条确认通道
在落章前拒绝拆分内容；提示词/指南与代码恢复一致；产物登记时即拦截不存在或不可打开路径。

做法：先定契约（T-1），再按层落地后端闸门（T-2/T-3/T-4）、前端呈现（T-5）、规范层修正（T-6），
最后由迁移兼容与全量回归卡（T-7）收口。实施阶段代码改动须按仓库纪律在独立 worktree 中进行；本
计划本身只登记拆分，不产生代码副作用。

## 2. 对照设计文档的改动盘点（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

| 设计文档 | 设计结论 | 代码/文档改动 | 承接任务 |
|---|---|---|---|
| architecture.md | 五个加固件都落在既有 G2，不改状态机；转移四路径、确认三通道必须全部接线 | application/internal、use-cases、http/routers、client、prompt/guide | T-2, T-3, T-4, T-5, T-6 |
| backend.md | category-doc-sets/content-gates/wiring/artifact-gates/Confirm/AskConfirm/Move/Submit/ArtifactSync/requirements.ts 分层修改 | 后端源码 + 5 个新测试文件 | T-1, T-2, T-3, T-4, T-7 |
| data-model.md | ConditionalDesignDoc、front-matter sides/design_exempt、StageArtifact 零 schema 变更、GateFailure 两枚新码 | category-doc-sets.ts、artifact-gates.ts、protocol.ts | T-1 |
| frontend.md | DesignDocStatus 增 conditional/exempted；host 投影读 front-matter；stage-panel 徽标与成组确认文案 | design-docs.ts、QueryStageDetail.ts/stages 路由接线、stage-panel.ts | T-5 |
| interfaces.md | designDocPolicyFrom、checkDesignCompletenessGate、detectDecompositionFeatures、checkDesignDecompositionGate、assertArtifactOpenable、错误码表 | category-doc-sets.ts、content-gates.ts、content-gate-wiring.ts、artifact-gates.ts | T-1, T-2, T-3, T-4 |
| test-cases.md | 10 条单测矩阵 + 规范层验证 + 全量回归 | tests/design-doc-policy.test.ts、design-completeness-gate.test.ts、decomposition-detect.test.ts、confirm-group.test.ts、artifact-openable.test.ts，并更新既有测试 | T-1, T-2, T-3, T-4, T-5, T-7 |
| use-cases.md | UC-1~UC-6：缺文档拦截、条件/豁免、拆分内容拦截、成组确认、登记拦截、存量回归 | 后端闸门、确认通道、登记入口、兼容检查 | T-2, T-3, T-4, T-7 |

## 3. 文件级改动清单（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

### 3.1 新增

| 路径（相对 packages/pages/dsh-pmboard/） | 用途 | 任务 |
|---|---|---|
| tests/design-doc-policy.test.ts | 文档集、条件必交、豁免解析单测 | T-1 |
| tests/design-completeness-gate.test.ts | G2 完整性闸门、四转移路径、isLegacy 单测 | T-2 |
| tests/decomposition-detect.test.ts | 拆分内容特征检测与三确认通道拦截单测 | T-3 |
| tests/confirm-group.test.ts | kind=design 成组落章单测 | T-3 |
| tests/artifact-openable.test.ts | 产物登记可打开性两入口单测 | T-4 |

### 3.2 修改

| 路径 | 动作 | 要点 | 任务 |
|---|---|---|---|
| src/application/internal/category-doc-sets.ts | 改 | ConditionalDesignDoc / DesignDocPolicy / designDocPolicyFrom / sides+exempt 参与 missingCategoryDocs；feature DELTA 加 use-cases 与端侧条件 | T-1 |
| src/shared/protocol.ts | 改 | DesignDocStatus 增 conditional/exempted 可选字段（DTO 向后兼容） | T-1 |
| src/application/internal/artifact-gates.ts | 改 | GateFailure 增 design_doc_incomplete/design_contains_decomposition；design 门改全部确认判定 | T-1, T-2 |
| src/application/internal/content-gates.ts | 改 | 新增 detectDecompositionFeatures，判定前剥离围栏代码块 | T-3 |
| src/application/internal/content-gate-wiring.ts | 改 | 新增 checkDesignCompletenessGate / checkDesignDecompositionGate / assertArtifactOpenable | T-2, T-3, T-4 |
| src/application/use-cases/MoveRequirement.ts | 改 | reqboard_move 的 design→decomposing 前接完整性闸门 | T-2 |
| src/application/use-cases/AskConfirm.ts | 改 | 确认设计产物前扫描；成组落章；自动推进块补完整性闸门 | T-2, T-3 |
| src/application/use-cases/ConfirmArtifact.ts | 改 | 文字证据通道确认设计产物前扫描；kind=design 成组落章 | T-3 |
| src/http/routers/requirements.ts | 改 | 看板确认/移动两入口同样接完整性与拆分内容闸门；确认后自动推进前复核 | T-2, T-3 |
| src/application/use-cases/SubmitArtifact.ts | 改 | requirement/plan 登记前可打开性校验；plan path 存在性补齐 | T-4 |
| src/application/use-cases/SubmitVerification.ts | 改 | verification 产物登记/生成路径同享可打开性口径 | T-4 |
| src/application/use-cases/SubmitArchive.ts | 改 | archive 目录与 docs[].path 登记前校验 | T-4 |
| src/adapters/ArtifactSync.ts | 改 | 自动发现登记路径做形态过滤（防御性兜底） | T-4 |
| src/application/internal/design-docs.ts | 改 | 输出条件必交与豁免投影，头注随 FR-2 更新 | T-5 |
| src/application/query/QueryStageDetail.ts、src/http/routers/stages.ts | 改 | host 侧读取 requirement.md front-matter 并注入 DesignDocStatus 策略，client 不碰 fs | T-5 |
| src/client/stage-panel.ts | 改 | 条件徽标、豁免理由灰显、成组确认按钮文案；错误缺口沿用既有展示通道 | T-5 |
| src/domain/prompt/fragments/design/heavy/overrides.md | 改 | 删除设计阶段 submit(kind=plan)/ask_confirm(target=plan) 指令，改写为确认 design 产物后进拆分 | T-6 |
| src/domain/prompt/generated/fragments.ts | 重新生成 | 由 scripts/inline-prompt-fragments.mjs 生成，不手改 | T-6 |
| ../../../docs/guides/reqboard-workflow.md | 改 | 闸门边、设计步骤、硬要求三处与 2026-09-21 裁定和 GateCatalog 对齐 | T-6 |
| tests/category-doc-sets.test.ts、tests/artifact-gates.test.ts、tests/ask-confirm.test.ts、tests/artifact-confirm-board.test.ts、tests/stage-panel.test.ts、tests/sync-artifacts.test.ts、tests/requirement-submit.test.ts | 改 | 更新既有预期并防回归；plan_submit 既有门禁预期不回退 | T-1, T-2, T-3, T-4, T-5, T-7 |

### 3.3 删除

无。台账 schema 不迁移，ledger v7 不变；isLegacy 存量需求继续豁免。

## 4. 任务表（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

| key | title | phase | side | depends_on | implementation | acceptance |
|---|---|---|---|---|---|---|
| T-1 | 定稿设计文档策略与闸门错误契约 | implement | backend | — | 修改 src/application/internal/category-doc-sets.ts：新增 ConditionalDesignDoc/DesignDocPolicy/designDocPolicyFrom，CategoryDocCheckInput 增 sides/exempt，missingCategoryDocs 按「必交 ∪ sides 命中的条件必交 − 有效豁免」判定；feature DELTA 增 use-cases.md 与 frontend/backend 条件文档。修改 src/application/internal/artifact-gates.ts 的 GateFailure 联合，加入 design_doc_incomplete/design_contains_decomposition；修改 src/shared/protocol.ts 的 DesignDocStatus，增 conditional/exempted 可选字段。新增 tests/design-doc-policy.test.ts 并更新 tests/category-doc-sets.test.ts。 | 在 packages/pages/dsh-pmboard 运行 `npx vitest run tests/design-doc-policy.test.ts tests/category-doc-sets.test.ts`；预期全绿，且断言覆盖：缺 use-cases.md 报缺、sides=frontend 只要求 frontend.md、有效豁免消失、空理由/未知键豁免不生效。 |
| T-2 | 接通 G2 文档集完整性闸门四条转移路径 | implement | backend | T-1 | 修改 src/application/internal/content-gate-wiring.ts：新增 checkDesignCompletenessGate（读 requirement.md front-matter，校验文档集与全部 kind=design 产物 confirmedAt，isLegacy 放行）。修改 src/application/internal/artifact-gates.ts：design 门从 find 第一份改为 filter 全部、任一未确认即拒。把闸门接入 MoveRequirement.ts、AskConfirm.ts 自动推进块、http/routers/requirements.ts 的看板移动入口与看板确认后自动推进块。新增 tests/design-completeness-gate.test.ts 并更新 artifact-gates/ask-confirm/artifact-confirm-board 相关测试。 | 运行 `npx vitest run tests/design-completeness-gate.test.ts tests/artifact-gates.test.ts tests/ask-confirm.test.ts tests/artifact-confirm-board.test.ts`；预期全绿。测试输出须证明：缺文档或任一 design 产物未确认时四路径都拒，错误为 design_doc_incomplete 且 gaps 含缺失文档/未确认路径；全交齐且全确认后 design→decomposing 放行；isLegacy 放行。 |
| T-3 | 实现设计文档拆分内容硬门禁与成组确认 | implement | backend | T-1 | 修改 src/application/internal/content-gates.ts：新增 detectDecompositionFeatures，识别 depends_on 表头、acceptance+implementation 表头、H2+「拆分计划/任务 DAG」标题，并剥离围栏代码块。修改 content-gate-wiring.ts：新增 checkDesignDecompositionGate。把扫描接到 ConfirmArtifact.ts（文字证据）、AskConfirm.ts（弹框）、http/routers/requirements.ts handleArtifactConfirm（看板一键）落章前；kind=design 确认改为全部 design 产物一次性落章。新增 tests/decomposition-detect.test.ts 与 tests/confirm-group.test.ts。 | 运行 `npx vitest run tests/decomposition-detect.test.ts tests/confirm-group.test.ts`；预期全绿。断言：depends_on 表头命中、代码块示例不命中、中文散文不命中；三通道均抛 design_contains_decomposition 且不落章不推进；确认 kind=design 后全部 design 产物都有 confirmedAt。 |
| T-4 | 前置产物登记可打开性校验 | implement | backend | T-1 | 修改 src/application/internal/content-gate-wiring.ts：新增 assertArtifactOpenable（拒空串/反斜杠/../brace 或通配伪路径，docs.exists 必须为真，返回 normalized 路径）。把 SubmitArtifact.ts 的 requirement/plan 两入口、SubmitVerification.ts、SubmitArchive.ts 的登记/生成路径接入；ArtifactSync.ts 对自动发现路径做防御性形态过滤。错误分流：不存在复用 REQBOARD_FILE_MISSING，伪路径/越界新增 REQBOARD_ARTIFACT_NOT_OPENABLE。新增 tests/artifact-openable.test.ts，更新 requirement-submit/sync-artifacts 相关测试。 | 运行 `npx vitest run tests/artifact-openable.test.ts tests/requirement-submit.test.ts tests/sync-artifacts.test.ts`；预期全绿。断言：不存在路径报 REQBOARD_FILE_MISSING，brace/越界路径报 REQBOARD_ARTIFACT_NOT_OPENABLE，消息含 normalized 路径与原因；submit 与 ArtifactSync 两入口都覆盖。 |
| T-5 | 更新设计文档交付状态投影与看板呈现 | implement | frontend | T-1 | 修改 src/application/internal/design-docs.ts：基于 T-1 策略输出必交、条件必交、豁免项（conditional/exempted）。修改 src/application/query/QueryStageDetail.ts 与 src/http/routers/stages.ts：host 侧读取 requirement.md front-matter 并注入投影，client 不碰 fs。修改 src/client/stage-panel.ts：条件必交显示「条件」徽标，豁免项灰显并展示理由，kind=design 确认按钮文案写明「将确认全部 N 份设计文档」。更新 tests/stage-panel.test.ts / tests/stage-detail.test.ts。 | 运行 `npx vitest run tests/stage-panel.test.ts tests/stage-detail.test.ts`；预期全绿。断言：host 投影含 frontend.md 的 conditional=frontend、豁免项含理由；stage-panel 渲染条件徽标/豁免理由/成组确认文案；不新增页面或路由。 |
| T-6 | 清理设计阶段过时提示词与工作流指南 | implement | doc | — | 修改 src/domain/prompt/fragments/design/heavy/overrides.md：覆盖 1/3/5 删除 submit(kind=plan)/ask_confirm(target=plan)，改写为落盘 design/*.md 后 ask_confirm(target=artifact, kind=design)；覆盖 2 强化任务表归拆分阶段。修改 ../../../docs/guides/reqboard-workflow.md：闸门边、设计步骤、拆分计划硬要求三处与 GateCatalog 一致。运行 `node scripts/inline-prompt-fragments.mjs` 重新生成 src/domain/prompt/generated/fragments.ts。 | 在 packages/pages/dsh-pmboard 运行 `grep -n "kind=plan\|target=plan" src/domain/prompt/fragments/design/heavy/overrides.md`，预期无命中；运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0；指南 diff 中 G2=确认设计文档 design→decomposing、G3=批准拆分计划 decomposing→implementing，与 GateCatalog 人工核对一致。 |
| T-7 | 收口迁移兼容、在途需求豁免核查与全量回归 | test | backend | T-2, T-3, T-4, T-5, T-6 | 核查台账中处于 design/decomposing 的 feature 需求：逐条确认 front-matter 已声明有效 design_exempt 或已补齐新文档集；需要代录的只改 requirement.md front-matter 并写明理由，不改 ledger schema、不写迁移版本。补齐 isLegacy/旧调用方回归：plan_submit 既有编号串联/serves/文档集门禁预期不变，decomposing 语义不回退。执行全量测试与提示词同步门禁，汇总缺口并在任务报告中留证。 | 运行 `npx vitest run`（packages/pages/dsh-pmboard），预期 0 failed；运行 `node scripts/check-prompt-fragments.mjs`，预期 exit 0；在任务报告附在途 feature 核查清单（需求 id → 豁免/补齐结论）与 `git diff --name-only`，证明无台账 schema/迁移文件改动。 |

## 5. RTM 覆盖表（serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6）

| 根编号 | 计划 key | 任务 id | 任务标题 | 状态 |
|---|---|---|---|---|
| FR-1 | T-1 | t-892858 | 定稿设计文档策略与闸门错误契约 | todo |
| FR-2 | T-2 | t-af0bff | 接通 G2 文档集完整性闸门四条转移路径 | todo |
| FR-3 | T-3 | t-0553af | 实现设计文档拆分内容硬门禁与成组确认 | todo |
| FR-4 | T-6 | t-065810 | 清理设计阶段过时提示词与工作流指南 | todo |
| FR-5 | T-4 | t-a19c66 | 前置产物登记可打开性校验 | todo |
| FR-6 | T-2 | t-af0bff | 接通 G2 文档集完整性闸门四条转移路径 | todo |
| FR-6 | T-3 | t-0553af | 实现设计文档拆分内容硬门禁与成组确认 | todo |
| FR-6 | T-4 | t-a19c66 | 前置产物登记可打开性校验 | todo |
| FR-1 | T-5 | t-ffe568 | 更新设计文档交付状态投影与看板呈现 | todo |
| FR-2 | T-5 | t-ffe568 | 更新设计文档交付状态投影与看板呈现 | todo |
| FR-3 | T-5 | t-ffe568 | 更新设计文档交付状态投影与看板呈现 | todo |
| FR-1 | T-7 | t-a3f3ee | 收口迁移兼容、在途需求豁免核查与全量回归 | todo |
| FR-2 | T-7 | t-a3f3ee | 收口迁移兼容、在途需求豁免核查与全量回归 | todo |
| FR-3 | T-7 | t-a3f3ee | 收口迁移兼容、在途需求豁免核查与全量回归 | todo |
| FR-4 | T-7 | t-a3f3ee | 收口迁移兼容、在途需求豁免核查与全量回归 | todo |
| FR-5 | T-7 | t-a3f3ee | 收口迁移兼容、在途需求豁免核查与全量回归 | todo |
| FR-6 | T-7 | t-a3f3ee | 收口迁移兼容、在途需求豁免核查与全量回归 | todo |

## 6. 依赖与批准闸门口径（serves: FR-6）

- T-1 是接口与数据契约卡，T-2/T-3/T-4/T-5 均依赖它；T-6 是规范层修正，可与契约卡并行；
  T-7 汇总全部实现卡后再跑。
- 迁移与兼容单列为 T-7：无台账 schema 迁移、无旧数据回填脚本；只处理在途 feature 需求的
  front-matter 豁免/补齐，并用 isLegacy 回归证明旧需求不被锁死。
- 本计划提交后须经人批准；批准后 reqboard_decompose 只能落库本表 T-1~T-7，不得「批了 A 落库 B」。
