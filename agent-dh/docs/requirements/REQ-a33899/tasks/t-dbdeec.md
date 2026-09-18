# t-dbdeec 会话顶部每节点 Token（同行）+ 看板卡面

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
会话顶部每节点 Token（同行）+ 看板卡面

## 背景摘要（context）
（待补充）

## 范围
- 阶段：ui
- 端侧：frontend

## 验收标准
build 后 client 产物含 .dsh-pm-flow-meta/.dsh-pm-flow-token 且既有 .dsh-pm-flow-node/.dsh-pm-flow-dot/.dsh-pm-flow-label 样式未被改写（grep 对照）；卡面含徽章；无 tokenTotals 不渲染徽章。

## 实施方案（implementation）
改 src/client/conversation-progress.ts、src/client/views/board.ts、src/client/views/artifacts.ts、src/client/styles/*.ts。验证：pnpm build:client。

## 上游产出摘要（dependsSummary）
- 读路径装配与 HTTP（需求/节点/任务）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T21:56:32.452Z，窗口 session-b11b0a40-5c65-4c8d-88c7-23988b4979b0）

会话顶部每节点 Token（同行）+ 看板卡面累计：conversation-progress 在既有节点（圆点在上/名称在下）的 label 行内新增同水平 token（.dsh-pm-flow-meta/.dsh-pm-flow-token，无快照不渲染 token 只显示名称）；BoardState 增 tokenTotals、ReqCard 增 tokenTotal，泳道卡面与列表各自渲染 🪙 徽章（无数据不渲染）；styles/token.ts 增对应样式。

### 完成项

- conversation-progress：节点 meta 行内水平 token（既有样式不改）+ ProgressPayload.nodes 类型
- types.ts：BoardState.tokenTotals / ReqCard.tokenTotal
- 卡面与列表：🪙 累计徽章（无 tokenTotals 不渲染，零噪音）
- styles/token.ts 增 .dsh-pm-flow-meta/.dsh-pm-flow-token/.dsh-pm-token-badge
- 新增 tests/token-card.test.ts 3 条全绿；typecheck 通过；pnpm build:client 通过且产物含 dsh-pm-flow-token(2)/dsh-pm-token-badge(3)

### 改动文件

- `agent-dh/packages/pages/dsh-pmboard/src/client/conversation-progress.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/types.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/views/board.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/views/artifacts.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/styles/token.ts`
- `agent-dh/packages/pages/dsh-pmboard/lib/client.js`
- `agent-dh/packages/pages/dsh-pmboard/tests/token-card.test.ts`

### 下一步

t8：端到端自证与文档更新。

---
