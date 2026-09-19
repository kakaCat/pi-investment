---
req_id: REQ-81aabd
title: 设计 · 数据模型：产物种类、交付状态与协议字段
serves: FR-3, FR-4, FR-5
---

# 设计 · 数据模型（REQ-81aabd）

## 1. 产物种类 `ArtifactKind`（serves: FR-3）

```ts
// domain/artifact/ArtifactSpec.ts
export type ArtifactKind =
  | 'requirement' | 'design' | 'plan' | 'decomposition' | 'task_detail'
  | 'verification' | 'archive' | 'notes'
export const ALL_ARTIFACT_KINDS = [...] as const   // 'design' 在 'plan' 之前
```

**不变式**：`ALL_ARTIFACT_KINDS` 是 kind 的**唯一事实源**——
`protocol.ts` 的入参校验、`AskConfirm`/`ConfirmArtifact` 的成员判断都读它；
新增种类只改这一处 + 路径规则，不再散落硬编码。

## 2. 路径 → 种类规则（serves: FR-3）

```ts
[/^design\/.+\.md$/, 'design']   // 插在 decomposition 规则之后、notes 兜底之前
```

- 命中 `design/<anything>.md` → `design`（`design/architecture.md`、`design/ui.md`、含子目录亦命中）
- `design/token-ui.html` → 落兜底 `notes`（**只有 .md 是文档**）
- 规则表是**有序**的：新规则必须插在兜底 `return 'notes'` 之前，否则永不命中。

## 3. 阶段归因 `stageForKind`（serves: FR-3）

```ts
case 'design': return 'design'
```

归因决定制品显示在哪个阶段卡片。注意它与`STAGE_ARTIFACT_REQUIREMENTS`（必备产物）**正交**：
归因到 `design` ≠ 成为 `design` 的必备产物。

## 4. 台账字段（serves: FR-5）

同步时对既有条目只重算两个字段（其余字段——`registeredAt`、`registeredBy`、`note`——原样保留）：

| 字段 | 回填前 | 回填后 |
|------|--------|--------|
| `kind` | `notes` | `design` |
| `stage` | 原值 | `stageForKind('design', 当前状态)` |

触发条件：`autoDiscovered === true`（系统发现的）且重算结果与现值不同。
`autoDiscovered` 未设置的条目视为人工登记，**不碰**。

## 5. 交付状态 DTO（serves: FR-4）

```ts
// shared/protocol.ts
export interface DesignDocStatus {
  name: string        // 'architecture.md'
  path: string        // 'docs/requirements/<ID>/design/architecture.md'
  submitted: boolean  // 台账中已登记该路径 = true
}
export interface DesignStageBody {
  plan?: PlanRecord
  category?: RequirementCategory
  designDocs?: DesignDocStatus[]   // 可选：老协议/未知类型时不传
}
```

构造规则（`application/internal/design-docs.ts`，**纯函数、零 IO**）：
`requiredDesignDocs(category)` → 逐份比对 `artifacts[].path.endsWith('/design/' + name)`；
未知分类返回 `[]`（不拦、不猜）；`category === undefined` 时**整个字段不输出**
（而非输出空数组），让客户端区分"没有这个概念"与"要求 0 份"。

## 6. 向后兼容（serves: FR-4）

| 旧值 | 新行为 |
|------|--------|
| 协议无 `designDocs` | 客户端回退旧渲染（模板名列表），不空白 |
| 台账无 `design` 条目 | 逐份显示 ⬜ 未交（真实状态，不是错误） |
| 需求无 `category` | 不输出 `designDocs` |
| `kind='notes'` 的历史条目 | 下次同步回填为 `design` |
| 状态键 `planning`（status/statusHistory/artifacts[].stage） | 迁移脚本归一为 `design`（见 §7），读路径不认旧值 |

## 7. 台账状态键迁移（serves: FR-7）

`REQBOARD_SCHEMA_VERSION` 6 → 7。迁移只动**状态类**字段，正文（评论/证据/验收标准/执行理由）原样保留：

| 路径 | 旧值 | 新值 | 迁移项 |
|------|------|------|--------|
| `requirements[].status` | `planning` | `design` | C3 |
| `requirements[].statusHistory[].status` | `planning` | `design` | C3 |
| `requirements[].artifacts[].stage` | `planning` | `design` | **C11（新增）** |
| `tasks[].statusHistory[].status` | `planning` | `design` | C3（任务态本无该值，防御性覆盖） |

不变式：①**幂等**——`schemaVersion === 7` 即早退，重复执行零写入；②**可复核**——`--verify` 独立扫描
残留并逐条报出（`仍有 planning 状态名未归一为 design`、`仍有 artifacts[].stage=planning 未归一为 design`）；
③**零兼容**——运行时读路径不做旧值兜底，别名表只在 `src/domain/legacy/LegacyStatus.ts` 内、
且只被迁移脚本使用。
