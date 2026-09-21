# t-3be71b 看板 UI：父子卡展示与 autoRun 控制面

> 任务卡骨架（reqboard_decompose 自动生成）；汇报经 reqboard_task_report 追加到本文件

## 在做什么
看板 UI：父子卡展示与 autoRun 控制面

## 解决什么问题
（未填写——开工前补充这张卡要解决的业务问题）

## 范围
- 阶段：ui
- 端侧：frontend

## 得到什么结果

目视验收：父卡展开显示子卡链与进度、徽标随 autoRun 变化（运行中/已暂停/熔断）、暂停后无新事件、存量卡外观与现状一致
验证：npx vitest run tests/client-subtask-view.test.ts；界面路径：打开 :13080 项目看板 → 需求卡看自动徽标与「父卡 x/y · 子卡 x/y」→ 点「暂停/继续」；进需求详情「执行」Tab 展开父卡看子卡链（阶段徽标 + 第 N 次）。

## 实施方案（implementation）
改 src/client 渲染：父卡可折叠展开子卡（stageKind 徽标 + attempt）、需求卡进度、自动状态徽标、控制面（暂停/继续/终止）；存量卡标 [手动] 且无子卡区。

## 上游产出摘要（dependsSummary）
- 懒展开：父卡开工同事务落子卡链
- 工具面与批准计划接线（合并拆分确认门）

## 执行方式提示（executorHint）
优先新窗口或 subagent 执行；按本卡自足执行，不读会话历史
## 汇报 1（2026-09-20T19:05:29.448Z，窗口 session-d41c9696-eb63-4a47-9018-68884d1f1fc8）

看板上现在能直接看见「这条需求在自动跑还是停着」：需求卡多了自动链徽标（运行中/已暂停/熔断/手动）和「父卡 x/y · 子卡 x/y」进度，并带暂停/继续/终止按钮；点开父卡能看到它下面的子卡链（研发→联调→复核→测试，带阶段徽标与第几次重跑），存量卡保持原样只多一枚 [手动] 标。

### 完成项

- client 契约补齐：RequirementRecord.autoRun/advance 与 TaskRecord.parentId/stageKind/attempt（此前 client 类型里没有 → 看板根本读不到，徽标与子卡链无从渲染）
- 新增 client/render/subtask-view.ts 纯函数：四态徽标 autoBadgeOf/renderAutoBadge、子卡链 subtaskChain/renderSubtaskChain、进度口径 subtaskProgress/progressText、控制面 renderAutoControls
- 需求卡（泳道+列表）：自动徽标 + 父卡/子卡进度 + 暂停/继续/终止；autoRun 缺省（存量需求）完全不显示，外观不变
- 执行 Tab 任务列：只有顶层卡进列，子卡挂在父卡下（原生 <details> 折叠，零 JS）；子卡显示 stageKind 徽标 + 第 N 次重跑；存量卡标 [手动] 且无子卡区
- host 新增 POST /dashboard/api/reqboard/req/autorun（仅人）：暂停=置 autoRun=false+pausedReason=manual；继续=置 true 并**立即触发一次推进事件**，推进器未装配时如实说明（不伪装已续跑）
- 新增 tests/client-subtask-view.test.ts（11 例）：四态徽标、进度口径（canceled 不计）、父卡/存量卡判定、子卡链渲染、控制面按钮
- 尺寸/类型门禁过（src/index.ts 压回 400 行上限内）；client bundle 重建 237780B 过哨兵

### 改动文件

- `packages/pages/dsh-pmboard/src/client/render/subtask-view.ts`
- `packages/pages/dsh-pmboard/src/client/styles/subtask.ts`
- `packages/pages/dsh-pmboard/src/client/types.ts`
- `packages/pages/dsh-pmboard/src/client/api.ts`
- `packages/pages/dsh-pmboard/src/client/board-mount.ts`
- `packages/pages/dsh-pmboard/src/client/styles.ts`
- `packages/pages/dsh-pmboard/src/client/views/artifacts.ts`
- `packages/pages/dsh-pmboard/src/client/views/stage-detail.ts`
- `packages/pages/dsh-pmboard/src/http/routers/requirements.ts`
- `packages/pages/dsh-pmboard/src/http/routers/shared.ts`
- `packages/pages/dsh-pmboard/src/http/routes.ts`
- `packages/pages/dsh-pmboard/src/index.ts`
- `packages/pages/dsh-pmboard/tests/client-subtask-view.test.ts`

### 下一步

⚠️ 未闭环（非本卡造成）：message-hygiene 门禁红 —— adapters 5→9，来源是并发会话 03:03 对 src/adapters/FailureAlert.ts 的改动（+6 行拼接式文案）。我不改别人的行；等该会话收手后全量才能全绿。t-fd25e0（端到端验收与文档）待做。

---
