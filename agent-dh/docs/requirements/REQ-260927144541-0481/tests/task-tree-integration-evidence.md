# reqboard_task_tree 联调证据（t-4b44d7 / 父卡 t-acd60f）

> serves: REQ-260927144541-0481 FR-3 · design/interfaces **I-3** · design/data-model「新增视图模型」
> 卡阶段：integrate（联调）—— 验收标准「接口联调通过：给出请求样例与期望响应，实际返回与预期一致」
> 证据时点：2026-09-27（工作区根 = `/Users/yunpeng/pi-investment/agent-dh`，本文件为写入族阶段要求的文件系统证据）

## 1. 被验对象

| 层 | 位置 | 说明 |
|----|------|------|
| 工具壳 | `packages/web/dsh-pmboard/src/tools/TaskTreeTool/TaskTreeTool.ts` | 工具名 `reqboard_task_tree` |
| 用例 | `packages/web/dsh-pmboard/src/application/use-cases/TaskTree.ts` | 只读，经 `deps.repo.snapshot()` |
| 注册 | `packages/web/dsh-pmboard/src/index.ts`（`toolsCtx.tools.register(defineTaskTreeTool(useCaseDeps))`） | 线上实例已可调用（见 §2） |

## 2. 契约对照（design/interfaces I-3）

```typescript
parameters: { parent_id?: string; requirement_id?: string }  // 缺省 = 本窗口绑定需求
returns: { success: boolean; requirement_id: string; parents: TaskTreeView[]; error?: string }
errors: REQBOARD_NO_BOUND_REQ / REQBOARD_TASK_NOT_FOUND / REQBOARD_NOT_BOUND_TO_WINDOW
```

线上实调（运行中实例的真实台账，只读；本 worker 窗口 `reqboard_status.bound=false`）：

| 样例 | 请求 | 期望（I-3） | 实际返回 | 结论 |
|------|------|------------|---------|------|
| L-1 | `{"parent_id":"t-acd60f"}` | 本窗口未绑定需求 → 明确拒绝（不返回空当成功） | `{"success":false,"requirement_id":"","parents":[],"error":"REQBOARD_NO_BOUND_REQ：本窗口未绑定需求，请传 requirement_id"}` | ✅ 一致 |
| L-2 | `{"requirement_id":"REQ-260927144541-0481"}` | 需求不属本窗口 → `REQBOARD_NOT_BOUND_TO_WINDOW` | `{"success":false,"requirement_id":"REQ-260927144541-0481","parents":[],"error":"REQBOARD_NOT_BOUND_TO_WINDOW：需求 REQ-260927144541-0481 不属于本窗口绑定的需求"}` | ✅ 一致 |
| L-3 | `{"parent_id":"t-nope"}` | 未绑定优先于不存在 → 同 L-1 | `REQBOARD_NO_BOUND_REQ` | ✅ 一致（错误码优先级可预期） |

在线可调用本身即证明：工具已注册、参数名 `parent_id/requirement_id` 被真实接受、返回体形状与 I-3 相同。

## 3. 正向/边界样例（内存端口，请求 → 实际响应 → 期望比对）

命令（仓库根 = agent-dh）：

```bash
node_modules/.bin/vitest run packages/web/dsh-pmboard/tests/task-tree.test.ts
# → Test Files 1 passed (1) / Tests 6 passed (6)
```

| 样例 | 请求 | 期望 | 实际（摘） | 结论 |
|------|------|------|-----------|------|
| S1（TC-5） | `{"parent_id":"t-p"}`，父卡 + 4 张串行子卡 | success、subtasks 按 dependsOn 链序、每项含 stageKind/status | `subtasks = [t-s1(dev,done,lastRunOk=true,reportSummary="第 2 次汇报：改完 a.ts"), t-s2(integrate), t-s3(review), t-s4(test)]`；`note="子卡链 4 张，已完成 1 张"` | ✅ 一致 |
| S2 | `{}`（缺省） | 列本窗口绑定需求下全部顶层父卡 | `parents = ["t-p","t-p2"]` | ✅ 一致 |
| S3（TC-6） | `{"parent_id":"t-p"}`，无子卡 | `subtasks=[]` + note | `subtasks=[]`；`note="该父卡尚未开工展开子卡链"`（与设计文案逐字相同） | ✅ 一致 |
| S4（TC-7） | `{"parent_id":"t-x"}`（属别窗口需求） | `REQBOARD_NOT_BOUND_TO_WINDOW` | `success=false`，error 同码 | ✅ 一致 |
| S5 | `{}` 且 exec 缺省（无窗口上下文） | 不崩、按端口默认窗口解析 | 与 S1 同结构返回 | ✅ 一致 |
| S6 | 不存在的任务（已绑定窗口内） | `REQBOARD_TASK_NOT_FOUND` | 单元用例覆盖并通过 | ✅ 一致 |

节点字段逐项核对（design/data-model「新增视图模型」）：`id / title / status / role / stageKind? / dependsOn / attempt? / lastRunOk? / reportSummary? / cardDoc` 全部存在；`cardDoc` 缺省按 `docs/requirements/<REQ>/tasks/<id>.md` 合成。

## 4. 偏差清单

- **无偏离**（对 I-3 参数、返回体、错误码、只读与绑定约束）。
- 两条实现说明（非偏离，供 review 判定语义归属）：
  1. `reportSummary`：data-model 注释写 `lastReport.summary`，但台账 `TaskReportSummary`（src/shared/protocol.ts:1104）**没有** `summary` 字段；实现改由 `completed[]` 拼接派生（`TaskTree.ts:74-79`），未新增台账字段（守住 data-model §1「不新增台账字段」）。字段名与截断语义仍符合视图模型。
  2. 未展开子卡的顶层卡 `role` 显示 `legacy`：来自全仓共享 `taskRoleIn`（`src/shared/protocol.ts:1415`：无子卡即 legacy），非本工具引入；TC-6 未断言 role。
- 已知约束（非偏离）：`parent_id` 单独传入但窗口未绑定需求时，先按绑定门拒绝（`REQBOARD_NO_BOUND_REQ`），不从 parent_id 反查需求 —— 与 I-3「缺省 = 本窗口绑定需求」及绑定纪律一致。

## 5. 结论

接口联调通过：6 组样例（3 组线上实调 + 6 组用例/探针）实际返回与 design/interfaces I-3 期望逐项一致；线上工具可调用、注册生效；无偏离。
