# t-baeed5 详情页「🪙 Token」tab（汇总卡 + 四个折叠块）

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 目标
详情页「🪙 Token」tab（汇总卡 + 四个折叠块）

## 背景摘要（context）
（待补充）

## 范围
- 阶段：ui
- 端侧：frontend

## 验收标准
pnpm build:client 通过且 verify-client-build 无报错；grep -c 'data-tab="token"' lib/client.js >= 1；一级折叠四块齐全；固定系统提示词每段可展开看到具体提示词内容（pre-wrap，超长内滚动）；无快照显示「无快照」、服务不可用显示「不可用」，均不显示 0。

## 实施方案（implementation）
改 src/client/views/stage-detail.ts、src/client/styles/*.ts、src/client/types.ts（如需），对照 design/token-ui.html 与 design/ui.md。验证：pnpm build:client。

## 上游产出摘要（dependsSummary）
- 读路径装配与 HTTP（需求/节点/任务）
- 提示词成本读路径（固定系统提示词 + 注入提示词）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-17T21:54:42.874Z，窗口 session-b11b0a40-5c65-4c8d-88c7-23988b4979b0）

详情页「🪙 Token」tab：stage-detail 追加第 5 个 tab 与容器，新增 client/token-info.ts（汇总卡 + 四个 details 折叠块：按流程节点表可下钻任务 / 固定系统提示词每段可展开看具体内容 / 注入提示词按阶段横条+明细 / 口径说明），board-mount 打开详情即预取并在切 tab 时兜底、支持点节点行展开任务明细，api 增 fetchRequirementToken，新增 styles/token.ts。

### 完成项

- client/token-info.ts：六块渲染，缺失一律「无快照/不可用」不渲染 0
- stage-detail：第 5 个 tab「🪙 Token」+ #dsh-pm-token-container
- board-mount：打开详情预取 + switch-tab 兜底 + toggle-token-node 展开任务明细
- api.fetchRequirementToken + styles/token.ts（复用全站令牌）
- 新增 tests/token-tab.test.ts 5 条全绿；pnpm build:client 通过（verify-client-build OK）；产物 grep data-tab="token" = 1、dsh-pm-tok-table = 5

### 改动文件

- `agent-dh/packages/pages/dsh-pmboard/src/client/token-info.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/views/stage-detail.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/board-mount.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/api.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/styles/token.ts`
- `agent-dh/packages/pages/dsh-pmboard/src/client/styles.ts`
- `agent-dh/packages/pages/dsh-pmboard/lib/client.cjs`
- `agent-dh/packages/pages/dsh-pmboard/lib/client.js`
- `agent-dh/packages/pages/dsh-pmboard/tests/token-tab.test.ts`

### 下一步

t7：会话顶部每节点 Token（同行）+ 看板卡面累计。

---
