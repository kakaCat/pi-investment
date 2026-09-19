---
req_id: REQ-308b9a
doc: design/data-model
serves: FR-8, FR-9
status: design
---

# REQ-308b9a 设计 · 数据模型

## 1. 验收项（VerificationItem）  `serves: FR-9`

唯一变更点：`status` 枚举**超集扩展**。

| 字段 | 类型 | 变更 | 约束 |
|---|---|---|---|
| `id` | string | 不变 | `v{version}-{index}` |
| `source` | `{kind:'requirement'} \| {kind:'task',taskId}` | 不变 | 判别联合 |
| `criterion` | string | 不变 | 业务结果 + 怎么验 |
| `evidence` | string[] | 不变 | — |
| **`status`** | `'pending' \| 'passed' \| 'failed' \| 'not_verifiable'` | **扩展** | 新增 `not_verifiable` |
| `opinion` | string? | 语义扩展 | `failed` **与** `not_verifiable` 必填（原因） |
| `decidedAt` / `decidedBy` | number / ActorRef | 不变 | — |

**数据契约（`shared/protocol.ts:540`）**：由三值联合扩为四值联合。
**迁移**：无——超集扩展，存量 `pending/passed/failed` 记录原样可读（NFR-1）。
**写入点**：仅域内 `applySheetVerdicts`（规则单点）。

## 2. 通过判据  `serves: FR-9`

| 判据 | 现状 | 目标 |
|---|---|---|
| 函数 | `isAllPassed(sheet)`（无 failed 且无 pending） | `isFullyDecided(sheet)`（**无 pending**） |
| 语义 | "全过才放行" | "全部已裁决才放行"（`passed + not_verifiable` 构成放行态） |
| 含 failed 时 | 可能停在验收态 | 由 FR-8 自动回退，**到不了放行** |

> 关键不变量：**只要存在 `pending` 项，就拒绝通过**（AC-9.5）——防"未验项静默消失"。

## 3. 需求状态迁移（新增触发者）  `serves: FR-8`

| 迁移 | 触发者 | 变更 |
|---|---|---|
| `accepting → implementing` | 原：人点「退回返工」 | 新增：**裁决出现 `failed` 即自动触发** |
| `accepting → archived` | 人点「验收通过」 | 不变（人工门） |

**原子性**：状态迁移、状态事件（`statusHistory`）、token 快照结算、
返工任务（`tasks[]` 新增 `status=todo`）必须在**同一次 `repo.mutate`** 内落库。

## 4. 返工任务规格（复用，不新增）  `serves: FR-8`

复用 `domain/workflow/AcceptanceSheetSpec.ts` 的 `reworkSpecsFor(sheet, tasks)`；
物化仍由 `materializeReworkTask` 负责（id 冲突重试、`recordStatus` 留痕）。

## 5. verification.md 的数据来源  `serves: FR-7`

| 段落 | 数据源 |
|---|---|
| 验收列表（含操作步骤/预期结果） | sheet.items + 任务 `acceptance` + 需求级 AC |
| 测试报告 | 提交时 `evidence` 中的测试输出 + 需求文档测试策略表（已有 `e2eCoverageOf` 读数） |
| 文档完整性检查（9 类） | `DocCompleteness` 对需求目录 + tasks 的实际存在性判定 |
| 验收结果表 | sheet.items 的 `status/decidedBy/decidedAt`（裁决后回填） |
