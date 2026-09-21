---
req: REQ-2d1c74
kind: design
requirement_refs: FR-1, FR-2, FR-3, FR-6
---

# 数据模型设计（REQ-2d1c74）

## 1. 文档集契约（serves: FR-1）

`category-doc-sets.ts` 的 `CategoryDocDelta` 扩一个可选字段（向后兼容，旧类型不受影响）：

```ts
export interface ConditionalDesignDoc {
  /** 文件名（位于 design/ 目录），目前只有 frontend.md / backend.md */
  name: string
  /** 触发条件：需求声明的端侧 */
  side: 'frontend' | 'backend'
}
export interface CategoryDocDelta {
  category: string
  rootSectionsDelta: readonly string[]
  requiredDesignDocs: readonly string[]
  /** 条件必交：需求声明含对应端侧改动时才要求 */
  conditionalDesignDocs?: readonly ConditionalDesignDoc[]
}
```

feature DELTA 改为：requiredDesignDocs = [architecture.md, data-model.md, interfaces.md,
test-cases.md, **use-cases.md**]，conditionalDesignDocs = [frontend.md→frontend, backend.md→backend]。

**refactor 等其他类型的评估结论（FR-1 尾款）**：本轮不增补——refactor 的行为不变式由
architecture.md + migration.md 承载，不引入新用例；bug/spike/doc/chore 无代码端侧概念。
若后续实证需要，走独立需求增补，不在本需求夹带。

## 2. 需求文档 front-matter 契约（serves: FR-1）

端侧声明与豁免声明放在 **requirement.md 的 front-matter**（机器可读；parseDocument 已解析），
「边界」节只写人读理由，不做解析源——双载体必漂移（本仓"两份真相"教训）。

```yaml
---
req: REQ-xxxxxx
sides: frontend, backend            # 可选；声明后对应 frontend.md/backend.md 变为必交
design_exempt: use-cases.md=纯内部工具无用户场景; frontend.md=不改前端   # 可选；豁免须给理由
---
```

字段约束：sides 值域 {frontend, backend}，逗号分隔；design_exempt 为 `文件名=理由` 的
分号分隔表，键必须命中该类型（必交 ∪ 条件必交）文档名，理由非空。未知键/空理由 = 豁免无效，
按未豁免处理并在缺失清单中注明。

## 3. 台账与产物模型（serves: FR-2, FR-6）

- **StageArtifact 零 schema 变更**：confirmedAt/confirmedBy/confirmedVia/confirmedEvidence
  字段沿用，成组确认只是"对 kind=design 的全部产物条目都写确认章"，不动数据结构，
  不需要台账迁移版本（v7 不变）。
- **成组确认语义**：确认 kind=design = 该需求全部 design 产物一次性落章；落章后新自动发现的
  design 产物无确认章 → G2 重新拦截，需再次确认（与"重写需求文档作废旧确认"同族语义）。
- **GateFailure.code 新增两枚**（artifact-gates.ts 的字面量联合）：
  `design_doc_incomplete`（文档集未交齐/未全确认，gaps=缺口清单）与
  `design_contains_decomposition`（设计文档含拆分内容，gaps=命中特征清单）。
