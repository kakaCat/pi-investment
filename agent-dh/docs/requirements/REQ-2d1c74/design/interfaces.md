---
req: REQ-2d1c74
kind: design
requirement_refs: FR-1, FR-2, FR-3, FR-5
---

# 接口设计（REQ-2d1c74）

## 1. 文档集与策略解析（serves: FR-1）

```ts
// application/internal/category-doc-sets.ts
export interface DesignDocPolicy { sides: readonly string[]; exempt: Readonly<Record<string, string>> }
/** 从 requirement.md front-matter 解析端侧声明与豁免声明（纯函数）。 */
export function designDocPolicyFrom(frontmatter: Readonly<Record<string, string>>): DesignDocPolicy

// CategoryDocCheckInput 扩展（新字段可选，旧调用点行为不变）
export interface CategoryDocCheckInput {
  category?: string; rootExists: boolean; rootText: string
  designNames: readonly string[]
  base?: readonly string[]
  sides?: readonly string[]              // 新增：端侧声明
  exempt?: Readonly<Record<string, string>>  // 新增：豁免表
}
// missingCategoryDocs 判定 = (必交 ∪ 条件必交[sides 命中]) − exempt
```

## 2. G2 完整性闸门（serves: FR-2）

```ts
// application/internal/content-gate-wiring.ts
/**
 * design→decomposing 前的完整性闸门。仅当 from=design 且 to=decomposing 时由调用方触发。
 * 校验：① 文档集交齐（含条件必交、豁免生效）；② 全部 kind=design 产物均已确认。
 * isLegacy（artifacts 空/undefined）→ undefined（放行，向后兼容）。
 */
export async function checkDesignCompletenessGate(
  docs: DocsReader, req: RequirementRecord,
): Promise<GateFailure | undefined>
// 失败 code='design_doc_incomplete'，gaps=缺失文档名 ∪ 未确认产物路径，message 含人读清单
```

`assertArtifactGates` 第二级同步修：gateKind=design 时从"find 第一份"改为
"filter 全部、任一未确认即拒"——看板/移动两条只走 assertArtifactGates 的旧路径也被兜住。

接线点（四处转移路径 + 三处确认通道，清单见 architecture.md §3）：
MoveRequirement.ts、AskConfirm.ts 推进块、http/routers/requirements.ts 两处。

## 3. 拆分内容检测（serves: FR-3）

```ts
// application/internal/content-gates.ts（纯判定，零 IO）
/**
 * 检测设计文档中的拆分内容特征，返回命中特征的人读清单（空 = 干净）。
 * 判定前剥离围栏代码块（``` 包围段不参与）——设计文档讨论本门禁时必然举例，
 * 示例只许活在代码块里，结构性特征（表格/标题）才算证据。
 */
export function detectDecompositionFeatures(doc: ParsedDoc): string[]

// application/internal/content-gate-wiring.ts
/** 扫描 req 全部 kind=design 产物；命中即拒。三通道落章前统一调用。 */
export async function checkDesignDecompositionGate(
  docs: DocsReader, req: RequirementRecord,
): Promise<GateFailure | undefined>  // code='design_contains_decomposition'
```

特征集 v1（刻意保守，宁漏勿冤——本需求自己的设计文档也要能过）：

| 特征 | 判定 | 说明 |
|---|---|---|
| 任务表表头 | 表格表头单元格含英文 depends_on，或同时含 acceptance 与 implementation | 与 normalizePlanTasks 字段同名才算；中文散文提及不命中 |
| 拆分章节标题 | H2+ 标题含「拆分计划」「任务 DAG」 | 标题级强信号；正文提及不命中 |

已知限制：手写中文表头的任务表漏检，列为后续增强（先保证零误伤）。

## 4. 可打开性校验（serves: FR-5）

```ts
// application/internal/content-gate-wiring.ts
/**
 * 产物登记前的可打开性校验（与 http/routers/artifacts.ts 的 classify 同口径的 use-case 侧版本）：
 * ① 禁空串/反斜杠/`..`/brace-通配（伪路径）；② docs.exists(normalized) 必须为真。
 * 通过 → 返回 normalized 相对路径；失败 → reject。
 */
export function assertArtifactOpenable(docs: DocsReader, rawPath: string): string
```

错误码映射：文件不存在 → 复用 `REQBOARD_FILE_MISSING`（消息补 normalized 路径与原因）；
伪路径/越界 → 新增 `REQBOARD_ARTIFACT_NOT_OPENABLE`。入口：submitRequirementArtifact
（升级既有 exists 检查）、submitPlanArtifact（**现状不查 path 存在性**，本次补上）、
verification/archive 提交同享；ArtifactSync 对扫描结果做形态过滤（防御，扫描来源本身保证存在）。

## 5. 错误码总表（serves: FR-2, FR-3, FR-5）

| 错误码 | 触发 | 消息要点 |
|---|---|---|
| design_doc_incomplete | design→decomposing 文档集未交齐或未全确认 | 缺失文档清单 + 未确认产物路径 |
| design_contains_decomposition | 确认 kind=design 时检出拆分内容特征 | 命中文件 + 特征清单 + "挪到拆分阶段"指引 |
| REQBOARD_ARTIFACT_NOT_OPENABLE | 登记伪路径/越界路径 | normalized 路径 + 拒绝原因 |
| REQBOARD_FILE_MISSING | 登记时文件不存在（复用） | normalized 路径 + "未落盘或路径错误" |
