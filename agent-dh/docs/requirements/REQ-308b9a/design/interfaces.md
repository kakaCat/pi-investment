---
req_id: REQ-308b9a
doc: design/interfaces
serves: FR-7, FR-8, FR-9
status: design
---

# REQ-308b9a 设计 · 接口

## 1. Agent 工具接口  `serves: FR-7, FR-9`

### 1.1 `reqboard_submit(kind='verification')`（现状扩展，签名不变）  `serves: FR-7, FR-9`
**输入**：`requirement_id?, summary(必填), evidence[](必填，≥1)`
**新增行为**：
- 生成结构化 `verification.md`（AC-7.1~7.3）；
- 文档完整性检查（AC-7.4）；缺项 → **拒绝**（AC-7.5）。

**新增错误码**：

| 错误码 | 触发 | 消息要点 |
|---|---|---|
| `REQBOARD_DOC_INCOMPLETE` | 9 类文档缺项 | 列出缺失文档与应补位置 |

**输出**（增量字段）：`doc_check: { passed: boolean, missing: string[] }`。

### 1.2 `reqboard_accept_sheet`（裁决新增枚举值）  `serves: FR-8, FR-9`
**输入**：`requirement_id?, batch_size?, version?`；弹框选项新增「不可验收」。
**行为**：
- 选「不可验收」→ `status='not_verifiable'` + 必填原因，否则拒绝；
- 出现 `failed` → 自动回退（FR-8），返回体反映 `status='implementing'`；
- 全项已裁决（无 pending）→ 走最终「验收通过」确认（AC-9.3）。

**新增/复用错误码**：`REQBOARD_OPINION_REQUIRED`（failed/not_verifiable 缺原因）。

## 2. 域内接口（纯函数，新增）  `serves: FR-7, FR-8, FR-9`

```ts
// domain/workflow/AcceptanceSheetSpec.ts（扩展）
type ItemStatus = 'pending' | 'passed' | 'failed' | 'not_verifiable'

/** 通过判据：无 pending 即可放行（原 isAllPassed 的语义替代） */
function isFullyDecided(sheet: SheetLike): boolean

/** 应用裁决；not_verifiable 与 failed 一样必填 opinion，否则抛 invalid_input */
function applyVerdicts(
  sheet: SheetLike,
  verdicts: readonly { itemId: string; status: ItemStatus; opinion?: string }[],
  actor: ActorRef, nowTs: number, tasks: readonly TaskLike[],
): { pending: number; passed: number; failed: number; notVerifiable: number }

// domain/workflow/VerificationDoc.ts（新增，纯渲染）
interface VerificationDocInput {
  requirementId: string
  title: string
  sheet: SheetLike
  tasks: readonly { id: string; title: string; acceptance: string }[]
  requirementCriteria: readonly string[]      // 需求级 AC（FR-x）
  testReport: readonly string[]
  docCheck: DocCheckResult
}
function renderVerificationDoc(input: VerificationDocInput): string

// domain/workflow/DocCompleteness.ts（新增，纯判定）
interface DocCheckResult { passed: boolean; missing: string[] }
function checkDocCompleteness(files: ReadonlySet<string>): DocCheckResult
```

## 3. 看板 HTTP 接口  `serves: FR-8`

| 端点 | 变更 |
|---|---|
| `POST /dashboard/api/reqboard/req/verify/pass` | 判据改"无 pending"；有 pending → 400 |
| `POST /dashboard/api/reqboard/req/verify/rework` | 保留为**等价入口**（复用自动回退 use-case），避免双实现 |

## 4. 迁移与兼容路径  `serves: FR-9`

- **数据回填**：无（枚举超集）。
- **开关/灰度**：无（无外部依赖）。
- **回滚步骤**：本需求不改文件格式版本号；回滚 = `git revert` 代码提交 +
  重启（`launchctl kickstart -k gui/$(id -u)/com.pi-investment.dsh`）。
  台账中若已写入 `not_verifiable` 项，回滚后读路径需容忍该值（读路径不校验枚举 → 天然容忍）。
- **契约冻结**：`VerificationItem.status` 四值联合与两个新错误码在实现前冻结。
