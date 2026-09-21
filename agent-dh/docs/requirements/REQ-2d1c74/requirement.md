---
req: REQ-2d1c74
title: 需求流水线设计阶段规范化：调研现状 + 剥离拆分职责 + 补齐技术设计文档规范
category: feature
status: brainstorming
created: 2026-09-21
window: w-a3d998e1
---

# REQ-2d1c74 需求流水线设计阶段规范化

## 1. 背景与证据（深度调研结论）

调研范围：REQ 从创建到设计完成的完整实现链路，覆盖代码层（dsh-pmboard 包
domain/application/tools）与规范层（阶段提示词片段、工作流指南）。用户诉求：设计阶段严格
遵循规范——产出技术设计与功能设计文档（架构设计 / 数据库设计 / 用例文档 / 前后端文档），
**不参与任何拆分工作**。

### 1.1 现行实现流程（实测源码）

| 阶段 | 代码层行为 | 人工闸门 |
|---|---|---|
| draft→brainstorming | `reqboard_create/capture` 立项即入 | G0 立项三问（弹框） |
| brainstorming→design | `submitRequirementArtifact`：格式门禁（FR-x 编号存在/连续/唯一）→ 登记 kind=requirement | G1 确认需求文档（`GateCatalog.ts`） |
| design→decomposing | `design/*.md` 自动发现登记 kind=design（`ArtifactSpec.kindForRelPath`）；`assertArtifactGates` 只要求"**任意一份** kind=design 产物已确认"（`ConfirmArtifact` 只确认 `find` 到的第一份） | G2 确认设计文档 |
| decomposing→implementing | `submitPlanArtifact` 硬拒非 decomposing 状态（REQBOARD_BAD_STATUS，2026-09-21 裁定已落代码）；内容门禁：编号串联/设计章节 serves/分类文档集存在性；G3 批准计划后 `reqboard_decompose` 落任务卡 | G3 批准拆分计划 |

### 1.2 发现的缺口（设计阶段为何混入拆分）

- **D1 规范层双源漂移（直接诱因）**：`design/heavy/overrides.md` 仍写着"设计阶段用
  `reqboard_submit(kind=plan)` 交棒、`ask_confirm(target=plan)` 批准"（2026-09-21 裁定前语义）；
  `docs/guides/reqboard-workflow.md` 流程表同样写"设计阶段写设计文档 + 拆分计划 → submit(kind=plan)、
  拆分计划只在 design 阶段提交"。而代码层 plan_submit 在非 decomposing 状态硬拒——**提示词让写、
  代码不让交，任务表就被塞进了设计文档**（REQ-c48f99 design.md §7 实证，本会话已手工清除）。
- **D2 G2 门只认一份**：设计文档集完整性（`CATEGORY_DELTAS.requiredDesignDocs`）的校验滞后到
  decomposing 阶段的 plan_submit；G2 不查"该交的交齐了没"。
- **D3 设计文档内容零门禁**：无任何代码检查设计文档是否含任务表/拆分内容；根级 `design.md`
  被归为 kind=notes（`NAME_TO_KIND` 只认 `design/*.md`），完全不受约束。
- **D4 文档集与诉求不齐**：feature 现为 architecture/data-model/interfaces/test-cases 四份，
  缺用户点名的**用例文档**与**前端/后端文档**视角。
- **D5 呈现与闸门脱节**：`design-docs.ts` 明确注释"不参与任何闸门"（2026-09-17 裁定选项 A
  只加呈现）——"已交/未交"只是展示。
- **D6 产物登记零校验（本需求确认环节实测）**：REQ-2d1c74 的 G1 确认弹框上用户"点看"需求文档
  报"没有找到文件"——根因是查看器按**会话工作区根**解析相对路径（`open-doc.ts` 的
  session 文件地址），本窗口工作区根在 `packages/pages/dsh-pmboard/` 而非 `agent-dh/`；
  而产物登记环节（submit / 看板自动发现）只登记路径字符串，**从不校验文件存在与可打开性**，
  于是"点看才发现没有"。看板接口 `docs/resolve` 实测该文件 openable=true——host 侧能开、
  会话侧打不开，两个基准目录不一致。

### 1.3 用户已确认的四个决策点（2026-09-21，本会话弹框）

1. **文档集**：feature 全套 6 份 + 端侧条件——architecture/data-model/interfaces/test-cases/
   use-cases 五份必交；含前端或后端改动时按端侧加 frontend.md/backend.md；小需求可在
   「边界」节声明豁免。
2. **完整性校验点前移到 G2**：design→decomposing 前代码级核验文档集齐全且全部已确认。
3. **拆分内容禁入 = 代码级硬门禁**：确认设计产物时扫描任务表特征，检出即拒绝确认。
4. **过时指令一并修正**：`design/heavy/overrides.md` 与 `guides/reqboard-workflow.md` 在本需求内修。
5. **产物登记加可打开性校验**（2026-09-21 弹框补充，针对 D6）：登记/提交产物时校验文件存在
   且可打开，不可打开即拒并明确报错——把"点看才发现没有"前移成"登记时就拦下"。
   查看器 absolute 地址兜底未选用（见边界）。

## 2. 产品定义

让需求流水线的设计阶段**职责纯净、产物规范**：设计阶段只产出按类型模板定义的技术/功能设计
文档集（架构 / 数据模型 / 接口 / 用例 / 测试策略 / 前后端），文档集完整性在进拆分前由代码级
闸门保证；设计文档中出现拆分内容（任务表/DAG）被代码级拒绝；提示词与文档规范不再与代码互相
矛盾。

## 3. 用户与角色

- **主要用户**：人类用户——设计确认门 G2 前能确信"设计文档交齐了、且里面没有越权的拆分内容"。
- **次要用户**：执行窗口 agent——提示词指令与代码门禁一致，不再被互相矛盾的规范误导。

## 4. 功能点

### FR-1: 设计文档集扩展（feature 全套 + 端侧条件）
`category-doc-sets.ts` 的 feature DELTA 扩为 architecture/data-model/interfaces/test-cases/
use-cases 五份必交；新增端侧条件机制：需求声明含前端/后端改动时（声明方式设计阶段定——
如需求文档「边界」节或 front-matter 字段），对应要求 frontend.md/backend.md；声明豁免须写理由。
refactor 等其他类型的 requiredDesignDocs 是否同步增补用例/端侧文档，设计阶段评估后定。

### FR-2: 文档集完整性校验前移到 G2
design→decomposing 转移（含 ask_confirm 自动推进路径与 reqboard_move 路径）前，代码级核验：
①该类型 requiredDesignDocs 全部存在；②**全部** kind=design 产物均已确认（修
`ConfirmArtifact` 只确认第一份、`assertArtifactGates` 只查第一份的现状——kind=design 的
确认语义改为"成组确认"或逐份确认齐全）。未交齐拒绝转移并给出缺失清单。

### FR-3: 设计文档拆分内容硬门禁
确认 kind=design 产物（会话弹框/文字证据/看板一键三通道）时扫描任务表特征
（任务表表头 depends_on/acceptance 列、批次 DAG、"拆分计划"章节等，特征集设计阶段定）；
检出即拒绝确认（新错误码如 `design_contains_decomposition`），提示把该内容挪到拆分阶段。
存量需求 isLegacy 豁免语义不变。

### FR-4: 矛盾指令清理（提示词 + 指南）
修正 `design/heavy/overrides.md`（删除"设计阶段 submit(kind=plan)/ask_confirm(target=plan)"
指令，改写为 2026-09-21 裁定后语义）与 `docs/guides/reqboard-workflow.md` 流程表
（闸门边、设计阶段动作、plan 提交阶段三处）；修正后重跑提示词片段生成器
（`scripts/inline-prompt-fragments.mjs`）并过同步门禁。

### FR-5: 产物登记可打开性校验（D6）
`reqboard_submit`（kind=requirement/plan 等）与看板自动登记（`ArtifactSync`）登记产物前，
复用 `http/routers/artifacts.ts` 的 classify 口径校验：文件存在且 openable；不存在/越界/
伪路径即拒绝登记并返回明确错误（含 normalized 路径与原因）。让"文档没落盘/路径写错"在登记时
就响亮失败，而不是等人点看才发现。

### FR-6: 回归安全
存量测试全绿；isLegacy 存量需求不被新闸门锁死；decomposing 阶段的 plan_submit 既有门禁
（编号串联/serves/文档集）行为不回退。

## 5. 边界

1. **不改状态机与五道门结构**：只在既有 G2 门上加校验，不新增/删除阶段或闸门。
2. **不改 decomposing 阶段语义**：拆分计划提交/批准/落卡的流程与门禁保持现状（校验点前移
   只做调用复用，不削弱 plan_submit 既有检查）。
3. **根级 design.md 的 notes 归类规则不动**：FR-3 门禁只管 kind=design 产物（design/*.md）；
   提示词修正后不应再产生根级 design.md（REQ-c48f99 残留已由本会话手工清理）。
4. **不动看板 UI 呈现层结构**：design-docs.ts 的"只呈现不进闸门"注释随 FR-2 作废属预期，
   但本需求不重新设计节点详情页的信息架构。
5. **查看器 absolute 地址兜底不做**（用户 2026-09-21 弹框未选用）：会话侧栏的 session 相对
   地址解析保持现状。已知限制：工作区根非 agent-dh 的会话，从会话框/看板点看文档仍可能
   打不开（host 侧 docs/resolve 与对话内文件卡片不受影响）；FR-5 的登记校验保证的是
   "产物真实存在且 host 可打开"，不解决会话侧基准目录错位。

## 6. 验收口径

1. 构造缺 use-cases.md 的 feature 测试需求：G2 确认/推进被拒，消息含缺失文档清单
   （vitest 用例 + 输出断言）；
2. 设计文档含任务表特征（depends_on 表头）时，三条确认通道均被拒并返回
   design_contains_decomposition（vitest 用例）；
3. 文档集齐全且全部确认后，design→decomposing 正常放行（vitest 用例）；
4. `grep -n "kind=plan\|target=plan" design/heavy/overrides.md` 无命中；
   reqboard-workflow.md 流程表与 GateCatalog 一致（人工核对 +  diff 留证）；
5. 登记不存在/越界路径的产物被拒，错误消息含 normalized 路径与原因（vitest 用例，
   覆盖 submit 与 ArtifactSync 两条入口）；
6. `npx vitest run`（dsh-pmboard 包）全绿，含 base-delta/gate-catalog 等既有性质测试。

## 7. 关键源码索引（调研留证）

- 状态机/闸门：`src/domain/gate/GateCatalog.ts`（G0-G4）、`src/shared/protocol.ts`
- 产物闸门：`src/application/internal/artifact-gates.ts`、`src/domain/artifact/ArtifactSpec.ts`
- 文档集：`src/application/internal/category-doc-sets.ts`（CATEGORY_DELTAS）
- 确认用例：`src/application/use-cases/ConfirmArtifact.ts`、`AskConfirm.ts`、`MoveRequirement.ts`
- 计划提交：`src/application/use-cases/SubmitArtifact.ts`（submitPlanArtifact，状态硬拒在 176-185 行）
- 提示词片段：`src/domain/prompt/fragments/design/`（heavy.md/light.md + 类型档 + overrides.md）
- 工作流指南：`docs/guides/reqboard-workflow.md`（第 18/23/38/50 行过时）
- 实证案例：`docs/requirements/REQ-c48f99/`（design.md §7 拆分任务表，已清除）
