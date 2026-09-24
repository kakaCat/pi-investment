---
requirement_refs: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7]
sides: [frontend, backend]
---

# 接口设计（REQ-260923134706-e72f）

## I-1 HTTP：GET /dashboard/api/reqboard/isolation-log <!-- serves: FR-6 -->

新增只读端点（形状照抄既有 `injection-log`）：

| 项 | 契约 |
|---|---|
| 方法/路径 | `GET /dashboard/api/reqboard/isolation-log` |
| 参数 | `window`（可选，sessionId，过滤窗口）；`k`（可选，1..200，默认 20） |
| 200 返回 | `{ success: true, data: IsolationLogResponse }`（契约见 data-model.md §4） |
| 400 | `k` 非 1..200 整数 → badInput（与 injection-log 同文案口径） |
| 副作用 | 无（只读端口；不写、不落盘） |

## I-2 HTTP：session progress 增量字段 <!-- serves: FR-2 -->

`GET /dashboard/api/reqboard/session/:sessionId/progress` → `data.requirement.promptDifficulty: string | null`（增量，见 data-model.md §3）。

## I-3 Client：renderNodePanel <!-- serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-7 -->

```
// src/client/node-panel.ts —— 纯函数，零 IO、零 DOM，返回 HTML 字符串
export interface NodePanelInput {
  overview: StageOverview            // 全流程一览（既有契约）
  stage: StageKey                    // 当前要看的节点
  requirement: { id: string; title: string; promptDifficulty?: string | null }
  injection: InjectionInfoEntry[]    // 该会话注入留痕（可为空数组）
  isolation: IsolationLogEntry[]     // 该会话隔离留痕（可为空数组）
}
export function renderNodePanel(input: NodePanelInput): string
```

输出结构（根 `.dsh-pm-np`，data-stage/data-state）：
`.dsh-pm-np-req`（REQ 胶囊 + 标题）→ `.dsh-pm-np-head`（状态胶囊 + 一句话 + 相对时间）
→ `<details open>` 基础信息（实施节点无）→ `<details>` 执行流程（默认收起）。
文档/任务链接一律 `data-action="open-doc"` + `data-path`（沿用既有右侧栏链路）；
泳道/流程图切换按钮 `data-action="np-switch-view"` + `data-view`。

## I-4 Client：STAGE_PROCESS 与求值 <!-- serves: FR-6 -->

```
// src/client/node-panel-process.ts
export const STAGE_PROCESS: Record<MainStageKey, StageProcessSpec>
export function evaluateActions(payload: StageDetail, spec: StageProcessSpec): { done: boolean; evidence: string }[]
export function renderProcessFold(payload: StageDetail, ctx: { injection: InjectionInfoEntry[]; isolation: IsolationLogEntry[]; requirement: {...} }): string
```

求值规则（全部只读 StageDetail，不取数）：artifact-registered/confirmed 查 payload.artifacts；
advanced-beyond 查 payload.timeline 是否出现更靠后节点；tasks-decomposed/tasks-progress 查 body.tasks；
always 恒 ✅（结构性事实，如"需求已立项"）。

## I-5 错误处理 <!-- serves: FR-1, FR-6 -->

| 情况 | 处理 | 重试 |
|---|---|---|
| isolation-log/injection-log 请求失败 | client catch 静默 → 该段显示「暂无数据」空态，面板其余不受影响 | 下轮轮询自愈 |
| k 参数非法 | 400 badInput | 调用方修正 |
| overview 无该节点 | renderNodePanel 回退第一个节点（沿用 renderStageNode 口径） | - |
| 片段文件不存在（被删/改名） | 显示「路由壳/文件缺失」空态，不渲染死链；守护单测变红 | 修映射表 |
