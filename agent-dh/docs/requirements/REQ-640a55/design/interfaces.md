---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5]
---

# REQ-640a55 技术设计 · 接口

## 新增：三要素门禁接线函数（serves: FR-1）

三个函数都落在 `application/internal/content-gate-wiring.ts`，与既有 `doneEvidenceAnchorFailure`
同源同风格（只做文件 IO 与组装，判定仍留在 content-gates）。

`@ts
export interface TaskCardTriadGap { taskId: string; missing: string[]; warnings: string[] }

/** 逐卡扫描三要素缺口。 */
export async function taskCardTriadGaps(
  docs: DocsReader,
  input: { requirementId: string; taskIds: readonly string[] },
): Promise<TaskCardTriadGap[]>

/** 单卡门禁（结单前）。返回缺口文案；undefined = 通过。 */
export async function taskCardTriadFailure(
  docs: DocsReader,
  input: {
    taskId: string
    to: string
    tasks: readonly { id: string; requirementId: string }[]
    boundRequirementIds: readonly string[]
  },
): Promise<string | undefined>

/** 需求级门禁（decomposing 出口）。一次扫全部卡。 */
export async function requirementTaskCardTriadFailure(
  docs: DocsReader,
  input: { requirementId: string; to: string; tasks: readonly { id: string; requirementId: string }[] },
): Promise<string | undefined>
`@

| 契约 | 值 |
|---|---|
| 读取路径 | `docs/requirements/<reqId>/tasks/<taskId>.md` |
| 返回 undefined 的条件 | 目标态不符 / 卡文件不存在 / 任务不在给定任务集合 / 任务所属需求不在绑定集合（单卡门禁） |
| 拒绝码 | `task_card_incomplete`（沿用 `artifact-gates.ts:68` 已声明的联合成员，不另造前缀码） |
| 副作用 | 无（纯读：不写台账、不写文档） |

## 修改：拆分骨架的章节契约（serves: FR-2）

| 节 | 来源字段 | 缺省兜底 |
|---|---|---|
| `## 在做什么` | `title` | 无（title 必填） |
| `## 解决什么问题` | `context` | `（未填写——开工前补充这张卡要解决的业务问题）` |
| `## 得到什么结果` | `acceptance` | `（未填写）` |
| `## 范围` / `## 实施方案（implementation）` / `## 上游产出摘要（dependsSummary）` / `## 执行方式提示（executorHint）` | 不变 | 不变 |

两条建卡路径必须同构：`Decompose.ts:297-327`（拆分时写）与 `ReportTask.ts:69-81`
（卡文件不存在时的兜底骨架头）——后者若不加三节，从该路径产出的卡结单必被拦。

## 修复：两处编号判据（serves: FR-3, FR-4）

| 修复 | 目标 | 判据 |
|---|---|---|
| `content-gates.ts:278` | 跳号可检出 | `/^([A-Z]+)-(d+)$/` → `/^([A-Z]+)-(\\d+)$/` |
| 新增 `extractClauseDefinitionOccurrences(doc)` | 重复可检出 | 与 `extractClauseDefinitions` 同源解析但**保留重复**（不去重）；`content-gate-wiring.ts:184` 的重复判定改喂它 |

## 兼容：改卡通道双标题（serves: FR-5）

`AmendTaskAcceptance.ts:77` 的定位正则 `/^##\\s*验收标准/` 改为 `/^##\\s*(?:得到什么结果|验收标准)/`。

为什么必须改：该通道在找不到该段时「不硬造」（见同文件注释），改名后若不改正则，
T-9 改卡会**静默不生效**——这属于本次改动必须一并处理的隐藏依赖。
