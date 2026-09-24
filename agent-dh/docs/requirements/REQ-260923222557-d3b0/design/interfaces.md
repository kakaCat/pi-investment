---
requirement_refs: [FR-4, FR-8, FR-9, FR-10]
---

# 接口设计（REQ-260923222557-d3b0）

## TL;DR <!-- serves: FR-4 -->

无 HTTP API 与台账契约变更。接口面 = 提示词模板变量契约 + 三个 client 渲染函数的语义契约（签名不变）。

## 提示词模板契约 <!-- serves: FR-1, FR-2, FR-3, FR-4 -->

| 模板键 | 触发 | 变量 | 约束 |
|---|---|---|---|
| worktree/implementing | 进 implementing | `{id}` | 含创建命令、目录规范 `.worktrees/REQ-{id}/`、分支 `feature/REQ-{id}` |
| worktree/task_done | 子任务 → done | `{id}` `{task_id}` `{task_title}` | 含 commit 命令示例（检查点语义） |
| worktree/archived | 进 archived | `{id}` | 含 merge --no-ff 与 worktree remove 命令 |

变量替换在注入前完成，缺失变量置空串；文本经 onStagePrompt 原样投递。

## stageHeadSummary（FR-8） <!-- serves: FR-8 -->

`stageHeadSummary(payload: StageDetail): string | undefined`（src/client/stage-panel.ts，签名不变）。design 分支语义改为：
- `body.plan` 存在（旧管线存量）→ 保持旧文案（计划待批准/已批准/被退回）；
- 否则按 `body.designDocs` 取词：未交齐 → `设计文档 n/N 已交`；交齐未确认 → `待确认设计文档`；已确认 → `设计已确认`。

## renderHead 状态取词（FR-10） <!-- serves: FR-10 -->

`renderHead`（src/client/node-panel.ts）增加行状态入参（`stageRowState` 已在 renderNodePanel :303 计算，仅下传）：
- `pending`（未到达节点）→ 状态词显示「未开始」，不再查 STAGE_STATE_WORD 过去式；
- `current` / `done` / `skipped` → 取词不变。

## 文档行渲染契约（FR-9） <!-- serves: FR-9 -->

- `renderDesignInfo`：`submitted=true` 的行改渲染 `docItem()`（button + data-action=open-doc，右栏打开）；`submitted=false` 与豁免行保持纯文本 ⬜/🚫。
- `renderDecomposingInfo`：`decompositionDoc` 缺席时渲染占位行 `⬜ 拆分计划：decomposition.md（未交）`（纯文本，不可点），与设计节点占位口径一致。

## 错误语义 <!-- serves: FR-5, FR-6 -->

无新增错误码。弹框超时到点后的工具返回形态不变（仅阈值变长）。
