---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
---

# 接口设计（REQ-260927144541-0481）

> 可执行契约：参数 / 返回键 / 错误码以此为准。既有返回键**只增不改**，除明确标注「删除不再返回的键」。

## 接口清单 <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7 -->

| 编号 | 接口 | 变化 | serves |
|---|---|---|---|
| I-1 | `reqboard_task_run` | 参数 + `requirement_id`；返回体与 schema 对齐；描述补 autoRun | FR-1, FR-2, FR-6 |
| I-2 | `reqboard_task_execute` | 改真委托 + deprecated | FR-1 |
| I-3 | `reqboard_task_tree` | **新增**（只读） | FR-3 |
| I-4 | `reqboard_task_status` | 数据源换台账；`workflow` 键内容换 run 摘要 | FR-4, FR-6 |
| I-5 | `reqboard_task_move` | 角色感知报错；`acceptance` 真正生效 | FR-5 |
| I-6 | 契约门禁 | 全工具 声明键 ⊇ return 键 + 参数 DSL 形状 | FR-7 |

## I-1 reqboard_task_run <!-- serves: FR-1, FR-2, FR-6 -->

```typescript
parameters: { task_id?: string; requirement_id?: string }   // 二者至少一个
// 语义：推进**该需求**当前 ready 事件（OPEN_PARENT/RUN_SUBTASK/FINALIZE_PARENT/ROLLUP），投递式立即返回
// 副作用：调用即写 req.autoRun=true（描述须显式声明）
returns: {
  success: boolean; task_id: string; requirement_id: string
  status: 'dispatched' | 'error'
  job_id?: string; run_id?: string
  running: string[]; next_ready: string[]; chain: { done: number; total: number }
  parent_status: string; error?: string; code?: string
}
// 删除不再返回的键：subtask_executed / blocked / stopped
errors: DSH_JOBS_UNAVAILABLE / REQBOARD_DISPATCH_FAILED / REQBOARD_NO_BOUND_REQ
```

## I-2 reqboard_task_execute <!-- serves: FR-1 -->

保留工具名，实现逐行委托 I-1（同返回体、同 autoRun 副作用），描述标「已弃用，等价 reqboard_task_run」。

## I-3 reqboard_task_tree（新增，只读） <!-- serves: FR-3 -->

```typescript
parameters: { parent_id?: string; requirement_id?: string }  // 缺省 = 本窗口绑定需求
returns: { success: boolean; requirement_id: string; parents: TaskTreeView[]; error?: string }
errors: REQBOARD_NO_BOUND_REQ / REQBOARD_TASK_NOT_FOUND / REQBOARD_NOT_BOUND_TO_WINDOW
// 无子卡：subtasks=[] 且 note="该父卡尚未开工展开子卡链"
```

## I-4 reqboard_task_status <!-- serves: FR-4, FR-6 -->

```typescript
parameters: { task_id: string }
returns: {
  success: boolean; task_id: string; status: string; progress: number
  run?: { ok: boolean; stopReason: string; valueNonEmpty: boolean; reason?: string }
  report?: { summary: string; completedCount: number; filesChangedCount: number }
  workflow?: unknown   // 键保留：内容换为 run 摘要（向后兼容）
  error?: string
}
// 删除：直连 fs 读 tasks/<id>.md 的 ## Workflow 解析
```

## I-5 reqboard_task_move <!-- serves: FR-5 -->

参数增 `acceptance?: string`（≤2000）：传入即修订验收标准并同步卡文档；**只传 acceptance 不传 to = 仅修订不改状态**。
非法转移错误须形如：`reqboard_task_move 未执行：{role} 卡不允许 {from}→{to}；该角色合法边：…`（role ∈ 父卡/子卡/存量卡）。

## I-6 契约门禁 <!-- serves: FR-7 -->

① 扫描 `src/tools/**` 每个工具工厂：响应源文件全部 `return` 顶层键 ⊆ `output.schema.properties`；
② `parameters` 必须是 `{ 字段名: DSL }` 形状（不得出现 `parameters.schema`）；
③ `tools-schema.test.ts` 构造**全部**已注册工具（当前 17 个）。

## 错误语义 <!-- serves: FR-1, FR-3, FR-4, FR-5, FR-7 -->

| 码 | 触发 | 处置 |
|---|---|---|
| `REQBOARD_NO_BOUND_REQ` | 未传 requirement_id 且本窗口未绑定 | 传 id 或先绑定 |
| `REQBOARD_NOT_BOUND_TO_WINDOW` | 目标不属于本窗口绑定需求 | 只动自己的 |
| `REQBOARD_TASK_NOT_FOUND` | task_id 不在台账 | 用 `task_tree` 核对 |
| `REQBOARD_INVALID_INPUT` | 参数非法 / acceptance 超长或空话 | 按提示改 |
| `REQBOARD_CONFIRM_PENDING` | 需求级确认门挂起（跨层守卫，保留） | 取回执/看板确认 |
