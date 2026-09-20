---
req_id: REQ-e3b6a0
doc: design/data-model.md
serves: FR-1, FR-2, FR-7, FR-9, FR-10
---

# 数据契约：闸门领域与后置链

## 1. GateSpec：单个闸门的形状 `serves: FR-10`

```ts
// domain/gate/GateSpec.ts（纯类型 + 纯函数，零 import）
export type GateId = "G0" | "G1" | "G2" | "G3" | "G4"

export interface GateSpec {
  id: GateId
  /** 进入该门之前的状态；G0 为 undefined（尚未绑定需求） */
  from?: RequirementStatus
  /** 确认后要推进到的状态 */
  to: RequirementStatus
  /** 须已确认的产物 kind；G0 为 undefined（创建即立项，无产物可落章） */
  requiredKind?: ArtifactKind
  /** 交互通道：session（pm 弹框）/ board（看板一键）/ both */
  channels: readonly GateChannel[]
  /** 答案语义族：决定答案怎么解读 */
  verdictShape: "affirmative" | "per-item" | "form"
  /** 允许自动推进的白名单转移（"from>to"） */
  advanceWhitelist: readonly string[]
  /** 问题卡文案（拒绝时给出可粘贴调用） */
  questionCard: { question: string; expr: string }
}
```

**收敛来源**（本需求把四处多份真相合并进来）：

| 现状位置 | 迁入字段 |
|---|---|
| `AskConfirm.ts:26-30` 私有 `ADVANCE_MAP` | `advanceWhitelist` |
| `ArtifactSpec.ts:38 ARTIFACT_CONFIRM_GATES` | `from` / `to` / `requiredKind` |
| `HUMAN_ONLY_REQ_TRANSITIONS` | **各存一份 + 测试锁死**（t2 实现口径）：它留在 `RequirementStatus`（状态机的断言函数要用），GateCatalog 只存 `humanOnly`；两者一致性由 `tests/gate-catalog.test.ts` 互锁。不改为派生是因为会让 `domain/gate ↔ domain/requirement` 形成**值环** |
| `support.ts:158-170 gateQuestionCard` 的问题表 | `questionCard` |

## 2. GateCatalog：五道门的唯一事实源 `serves: FR-10`

| 门 | from > to | requiredKind | channels | verdictShape |
|---|---|---|---|---|
| G0 立项门 | （unbound）> brainstorming | —（创建即立项） | session（pm 专有弹框） | form（名称/类型/难度） |
| G1 确认需求文档 | brainstorming > design | requirement | session + board | affirmative |
| G2 批准拆分计划 | design > decomposing | plan | session + board | affirmative |
| G3 确认拆分清单 | decomposing > implementing | decomposition | session + board | affirmative |
| G4 验收通过即归档 | accepting > archived | verification | session + board | per-item（逐项）+ affirmative（最终） |

非确认动作（取消需求 `*>canceled`）**不在表内**：它不是"确认"，agent 无权发起。

## 3. ConfirmContext：链的输入契约 `serves: FR-1, FR-2`

```ts
export interface ConfirmContext {
  windowKey: string            // 作答窗口（agent id）
  gate: GateId                 // 哪道门
  from: RequirementStatus      // 作答前状态
  to: RequirementStatus        // 按白名单推导的目标状态
  requirementId?: string       // G0 由 H1 产出；其余为既有需求
  verdict: "affirmative" | "negative"   // 肯定项 / 非肯定项
  answers: readonly AskAnswer[]         // 作答原文（进留痕与续跑摘要）
  decidedAt: number                     // 幂等键的一半
}
```

## 4. PendingGate：两相之间的登记表 `serves: FR-2`

**只在内存**（与既有 `pendingCapture` 同款：瞬态信号，不进台账）。

```ts
export interface PendingGate { ctx: ConfirmContext; enqueuedAt: number }
// 键 = windowKey（同窗口只保留最新一条；重复信号覆盖，不排队）
Map<string, PendingGate>
```

**幂等键** = `(windowKey, gate, decidedAt)`。同一次作答只跑一轮链；重复信号按此键去重（AC-1.2 / AC-9.3）。

## 5. 留痕契约 `serves: FR-6`

复用既有两条留痕，**不新增第三种格式**：

| 留痕 | 写入时机 | 关键字段 |
|---|---|---|
| 注入留痕 `<dshHome>/state/prompt-injection-log.json` | H3 注入成功 | 十字段（`injectionLogInputFromResolved` 产出） |
| 隔离留痕 `<dshHome>/state/node-isolation-log.json` | H2 每次尝试（replaced/skipped/rejected/fallback **都记**） | `status` / `reason` / `range` / `packageChars` |
| 台账评论 | H1 落章与推进 | `[确认弹框]` / `[自动推进]` / `[产物确认]`（来源区分 session/board） |

## 6. 立项三问的答案映射契约 `serves: FR-7`

| 问题 id | 问题 | 取值规则 | 落到 create 参数 |
|---|---|---|---|
| `req_name` | 需求名称 | `custom` 优先，否则 `selected[0]` | `title` |
| `req_category` | 需求类型 | `selected[0]`（六枚举） | `category` |
| `req_difficulty` | 提示词难度 | `selected[0]`（四档） | `prompt_difficulty` |

**缺失处置**：任一缺失 → 走既有默认值，且**在工具回执里显式说明缺失了什么**（不静默猜，AC-7.4）。

## 7. 难度取词映射 `serves: FR-4`

| `promptDifficulty`（四档） | 取词档位（两档） |
|---|---|
| simple / standard | light |
| advanced / expert | heavy |

**冲突处置（取重不取轻）**：当"声明档位"与"文本推断档位"不一致时，取 heavy，并把不一致写进 `difficultyReasons`（留痕可查）。

## 8. 看板通道 B 的响应契约 `serves: FR-9`

| 场景 | 落章 | 推进 | 投递 | 响应附加字段 |
|---|---|---|---|---|
| 窗口在线 | ✔ board | ✔ | ✔ | — |
| 窗口离线 | ✔ board | ✘ | ✘ | `note: "窗口不在线，请回会话推进"` |
| 已是确认态（重复点击） | 幂等 | ✘ | ✘ | `note: "该产物已确认"` |

## 9. 兼容与迁移 `serves: FR-10`

- **无台账 schema 变更**：本需求不新增台账字段，`SCHEMA_VERSION` 不动（避免又一次停机迁移）；
- `ArtifactSpec.ARTIFACT_CONFIRM_GATES` 迁入 `GateCatalog` 后**原处改为再导出**，保持既有调用点与测试不变（零破坏）；
- 既有 `autoContinue` 桩（`UserQuestionsAdapter` + `ports.ts`）**由本需求接管**：`onAnswered` 语义并入 `GateAwareQuestions`，旧桩删除，不留两套。
