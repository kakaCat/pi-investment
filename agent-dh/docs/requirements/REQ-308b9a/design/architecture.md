---
req_id: REQ-308b9a
doc: design/architecture
serves: FR-7, FR-8, FR-9
status: design
---

# REQ-308b9a 设计 · 架构

## 1. 现状与目标结构  `serves: FR-7, FR-8, FR-9`

**现状（代码事实）**：阶段 6 的三条链路都断在"只记录不闭环"——

| 环节 | 现状 | 文件 |
|---|---|---|
| 裁决 | 只写验收单，不改需求状态、不建返工卡 | `application/internal/verdicts.ts:133` |
| 归档放行 | 要求 `failed=0` 且全 passed（无 `not_verifiable` 概念） | `application/use-cases/AcceptSheet.ts:48-53` |
| 验收文档 | 只写"结论 + 证据清单"骨架 | `application/use-cases/SubmitVerification.ts:172-187` |

**目标结构**（沿用既有 DDD 四层，规则向内）：

```
domain/（纯规则，零 I/O）
  workflow/AcceptanceSheetSpec.ts    ← 扩展：not_verifiable 裁决 + "无 pending 即通过"判据 + 返工规格
  workflow/VerificationDoc.ts        ← 新增：verification.md 纯渲染（输入 sheet+tasks+docCheck → markdown）
  workflow/DocCompleteness.ts        ← 新增：9 类文档完整性纯判定（输入文件存在性 → 缺失清单）
        ↑
application/（用例，只依赖 ports）
  use-cases/SubmitVerification.ts    ← 生成 verification.md + 缺文档拦截（AC-7.4/7.5）
  use-cases/AcceptSheet.ts           ← 最终确认判据改"无 pending"（AC-9.3/9.5）
  internal/verdicts.ts               ← FR-8 自动回退 + 返工卡（同笔 mutate，原子）
        ↑
adapters/ · tools/ · http/ · client/  ← 薄适配（不得含领域规则）
```

**行为不变式**：需求状态集不变；`design>decomposing`、`accepting>archived` 人工门不变；
"规则单点"不变（NFR-2）。

## 2. 三条功能需求的落点  `serves: FR-7, FR-8, FR-9`

### 2.1 FR-8 自动回退（`serves: FR-8`）
`applyVerdicts` 在**同一笔 `repo.mutate`** 内完成三件事：
1. 写裁决（域内 `applySheetVerdicts`）；
2. 若存在 `failed`：`reworkSpecsFor` → 物化返工卡（复用 `materializeReworkTask`）；
3. 需求状态 `accepting → implementing`（`transitionRequirement` + 状态事件 + 快照结算）。

原子性是硬约束（AC-8.3）：任一步抛错则整笔回滚，不得出现"状态改了卡没建"。

### 2.2 FR-9 不可验收项（`serves: FR-9`）
- 枚举扩展 `VerificationItem.status += 'not_verifiable'`；
- 域内裁决：`not_verifiable` **必填意见**（与 `failed` 同规）；
- 通过判据 `isAllPassed` → 语义改为 **`isFullyDecided`（无 `pending`）**；
- `not_verifiable` **不触发**回退（AC-8.5）。

### 2.3 FR-7 验收文档（`serves: FR-7`）
- `renderVerificationDoc`：纯函数，产出四段（验收列表 / 测试报告 / 文档完整性检查 / 验收结果表）；
- 操作步骤/预期结果**派生**：复用任务的 `acceptance`（已过"怎么验"HOW_TO_VERIFY 门槛）+ 需求级 AC；
- 文档完整性：`DocCompleteness` 判定 9 类文档，缺项 → `SubmitVerification` **拒绝**（AC-7.5）；
- 裁决后**回填**结果表（AC-7.7/7.8）：裁决落地后重渲染 `verification.md`。

## 3. 与 REQ-a8d582 的冲突处理  `serves: FR-8`

REQ-a8d582（**已 archived**）FR-2 = "有不合格项时不自动打回"，其实现当前**仍在工作区未提交**。
本设计**推翻 FR-2**，保留其 FR-1（二次确认弹框）、FR-3（进入验收阶段即展示按钮）。

**落地纪律**：不触碰他人未提交改动；先确认 REQ-a8d582 的改动合入基线，再在本设计上进行。
两条路径（人点退回 / 自动回退）不得并存两套判定——统一收敛到 `applyVerdicts` 的自动回退，
看板「退回返工」改为**等价入口**（复用同一 use-case），避免双实现漂移。

## 4. 风险与缓解  `serves: FR-7, FR-8, FR-9`

| 风险 | 缓解 |
|---|---|
| 双实现漂移（弹框与看板两条裁决通道） | 统一走 `application/internal/verdicts.ts` 单实现（既有约定） |
| 回退原子性被破坏 | 回退与返工卡同一 mutate；补故障注入测试 |
| 长题干把弹框选项挤出可视区（已实测） | confirm 题干接入 `LIMITS.popupQuestionMax(220)` + `clip()` |
| 旧验收单反序列化失败 | 枚举为超集扩展，读路径不校验新值（NFR-1） |
