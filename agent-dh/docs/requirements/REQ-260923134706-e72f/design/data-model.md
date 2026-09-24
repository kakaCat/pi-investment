---
requirement_refs: [FR-2, FR-4, FR-6]
sides: [frontend, backend]
---

# 数据模型（REQ-260923134706-e72f）

## 1. 结论：不改表、不改 schema、无迁移 <!-- serves: FR-6 -->

本需求不改任何持久化结构。两个留痕文件（`state/prompt-injection-log.json` / `state/node-isolation-log.json`）
为既有 ring buffer，**只读**；需求台账（dsh-reqboard.json）不写新字段。
回滚 = 删端点 + 回退 client，无数据迁移。

## 2. 复用的既有契约 <!-- serves: FR-4 -->

| 契约 | 出处 | 用途 |
|---|---|---|
| `StageOverview` / `StageDetail`（含 artifacts/timeline/tokens/enabled/pendingConfirmation） | shared/protocol.ts | 面板数据源（既有 fetchStageOverview） |
| `StageTaskExecution`（status/phase/dependsOn/executions/cardDoc/claimedBy） | shared/protocol.ts | DAG/泳道 + 任务级履行判定 |
| `InjectionInfoEntry`（stage/routeKey/hitLevel/fragmentIds/charCount/trimmed/difficultyReasons/at） | client/injection-info.ts | 提示词注入段 |
| `IsolationTraceEntry`（at/windowKey/stage/status/reason/routeKey/packageChars/range/artifactSeq/replacementSeq） | application/use-cases/IsolateNodeContext.ts | 上下文管理段（host 侧类型） |
| `VerificationRecord.sheet.items`（status pending/passed/failed） | shared/protocol.ts | 验收单统计 |

## 3. 变更点一：session progress 补字段 <!-- serves: FR-2 -->

`GET /dashboard/api/reqboard/session/:id/progress` 的 `requirement` 对象新增一个字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `promptDifficulty` | `string | null` | 否 | `null` | 立项四问之一（RequirementRecord.promptDifficulty 透传；老记录无此字段 → null） |

兼容：纯增量字段，旧 client 不读不受影响；client 对 null/缺省显示省略该行（数据诚实）。

## 4. 变更点二：isolation-log 只读端点响应契约 <!-- serves: FR-6 -->

`GET /dashboard/api/reqboard/isolation-log?window=<sessionId>&k=<1..200>` → 200：

| 字段 | 类型 | 说明 |
|---|---|---|
| `entries` | `IsolationLogEntry[]` | 写入顺序（旧→新），client 取该节点最新一条 |
| `total` | `number` | 过滤后总条数 |
| `available` | `boolean` | false = 留痕端口未装配（看板显示空态，不报错） |
| `window` | `string | null` | 回显过滤窗口 |

client 侧只读投影 `IsolationLogEntry`（不 import host 模块，与 InjectionInfoEntry 同款纪律）：
`{ at: number; windowKey: string; stage: string; status: string; reason: string; routeKey: string; packageChars: number; range?: { start: number; end: number }; artifactSeq?: number; replacementSeq?: number }`。

**口径**：replaced 必有 range（校验函数 isIsolationTraceEntry 已保证）；client 不校验，只做展示。

## 5. 变更点三：STAGE_PROCESS 对照表结构 <!-- serves: FR-6 -->

`src/client/node-panel-process.ts` 的静态表（每节点一份"规定的流程"）：

```
interface StageProcessSpec {
  /** 提示词引用：id 与注入留痕 fragmentIds 同口径；kind=file 表示 fragments/<id>.md 真实存在可点开 */
  promptRefs: { id: string; kind: 'file' | 'shell' }[]
  /** 上下文管理规定侧一句话（压缩策略/保留/下阶段注入） */
  contextPolicy: string[]
  /** 规定动作（对照表的"规定"一侧；cite 为防漂移锚点，须在该阶段片段语料中出现） */
  actions: { label: string; cite: string; check: ProcessCheck }[]
}
type ProcessCheck =
  | { kind: 'artifact-registered'; artifactKind: string }
  | { kind: 'artifact-confirmed'; artifactKind: string }
  | { kind: 'advanced-beyond' }                  // timeline 出现更靠后的节点
  | { kind: 'tasks-decomposed' }                 // decomposing 任务落库
  | { kind: 'tasks-progress' }                   // implementing 有执行/完成记录
  | { kind: 'always' }                           // 结构性必然（如立项=需求存在即 ✅）
```

求值结果：`{ done: boolean; evidence: string }` —— evidence 是出处一句话
（如「已登记 3 小时前 · 人已确认」「任务 7/12 完成」「无记录」），渲染为 ✅/⬜ + 出处。
**数据诚实**：无留痕/无产物/无任务一律显示 ⬜「未见记录」或空态，绝不伪造 ✅。

## 6. 空态与降级口径 <!-- serves: FR-6 -->

| 情况 | 面板表现 |
|---|---|
| injection-log available=false 或该节点无留痕 | 「尚无注入留痕」空态（立项节点恒为此态——draft 无阶段提示词，如实显示） |
| isolation-log available=false / 无记录 | 「尚无隔离留痕」空态 |
| 节点无产物/无任务 | 基础信息显示「尚无内容」；执行动作对照全 ⬜ |
| 分类跳过节点（enabled=false） | 面板只显示「本分类跳过」+ 跳过说明，三段不渲染 |
| progress 无 promptDifficulty | 立项节点「用户选择」省略该行 |
