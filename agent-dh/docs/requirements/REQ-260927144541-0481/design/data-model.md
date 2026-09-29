---
requirement_refs: [FR-1, FR-3, FR-4, FR-5]
---

# 数据模型（REQ-260927144541-0481）

> 本需求**不新增台账字段**，只新增两个**只读视图模型**（工具返回体）。既有实体字段原样消费。

## 复用既有结构 <!-- serves: FR-1, FR-3, FR-4, FR-5 -->

| 实体 | 字段 | 类型 | 本需求用途 |
|---|---|---|---|
| `TaskRecord` | `id / title / status / parentId / stageKind / dependsOn / attempt` | string/枚举/string?/string[]/number | `task_tree` 节点来源；角色判定 |
| `TaskRecord` | `lastRun` | `{ ok, stopReason, valueNonEmpty, reason? }` | `task_status` 的真实数据源（替代死掉的 `## Workflow`） |
| `TaskRecord` | `lastReport` | `{ summary, completed[], filesChanged[] }` | 同上 + `task_tree` 摘要 |
| `TaskRecord` | `acceptance` | string | `task_move(acceptance=…)` 的写入目标 |
| `RequirementRecord` | `autoRun` | boolean | `task_run` 的副作用目标（显式声明） |

## 新增视图模型 <!-- serves: FR-3, FR-4 -->

```typescript
interface TaskTreeNode {
  id: string
  title: string
  status: string
  role: 'parent' | 'subtask' | 'legacy'
  stageKind?: string          // 子卡专属（dev/integrate/review/test…）
  dependsOn: string[]
  attempt?: number
  lastRunOk?: boolean         // lastRun?.ok（缺省=未跑）
  reportSummary?: string      // lastReport.summary（截断）
  cardDoc: string             // docs/requirements/<REQ>/tasks/<id>.md
}
interface TaskTreeView {
  parent: TaskTreeNode
  subtasks: TaskTreeNode[]    // 按链序；无子卡 = []
  note: string                // 未展开/未跑等如实说明
}
```

`task_status` 返回 `{ success, task_id, status, progress, run?: { ok, stopReason, valueNonEmpty, reason? }, report?: { summary, completedCount, filesChangedCount }, error? }`。

## 约束 <!-- serves: FR-3, FR-4 -->

- **只读**：`task_tree` / `task_status` 不得产生任何 `mutate`；IO 一律经 `deps.repo`/`deps.docs` 端口。
- **绑定**：只允许读**本窗口绑定需求**下的任务（解不到 → 明确拒绝，不返回空当成功）。
- **顺序**：`task_tree.subtasks` 按 `dependsOn` 链序（首卡依赖 = 父卡外部依赖）。
- **向后兼容**：`task_status` 的 `workflow` 键名保留（内容换真实 run 摘要）。
