# t-0fc58f styles/node-panel.ts 新增入口按钮与失败提示两条规则·研发

> 任务卡骨架（自动链懒展开时只建了 TaskRecord、未落卡文档；本文件由窗口 `session-f17b3bd0` 按队列里的卡面事实回填，内容取自该子卡的实施方案与验收标准）

## 在做什么
新增 .dsh-pm-np-board-entry（flex:none、min-height、胶囊、hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则；不动 head-time 的 margin-left:auto；tests/node-panel-styles.test.ts 加 TC-14。 [子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 解决什么问题
把父卡 **t-71aeb3**（styles/node-panel.ts 新增入口按钮与失败提示两条规则）的交付拆成「研发」阶段并独立验收，避免父卡一步到位、问题不可定位。

## 范围
- 阶段：ui
- 端侧：frontend
- 子卡阶段：dev

## 得到什么结果

在 packages/web/dsh-pmboard 下执行：grep -n "dsh-pm-np" src/client/styles/node-panel.ts（须命中新增的入口按钮与失败提示规则）；npx vitest run tests/node-panel-styles.test.ts（期望 Tests 15 passed、exit 0）。

## 实施方案（implementation）
新增 .dsh-pm-np-board-entry（flex:none、min-height、胶囊、hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则；不动 head-time 的 margin-left:auto；tests/node-panel-styles.test.ts 加 TC-14。 [子卡阶段·研发] 只做本阶段；验收：改动已落盘，相关测试或命令跑通并附输出摘要

## 上游产出摘要（dependsSummary）
- t-2eb71d
- t-e481a4

## 执行留痕（自动链 run）
- 状态：done｜尝试次数：0
- 产出（completed）：
- dev 卡完成：node-panel 样式新增项目看板入口按钮与入口失败提示两条作用域内规则，并在样式测试补 TC-14。核对确认两处改动已落盘在工作区（git 未提交 diff 与父卡方案逐条一致，未做二次覆盖写入）；.dsh-pm-np-head-time 的 margin-left:auto 未改动。TC-14 覆盖三项：入口按钮作用域内且不裁切可点（flex:none + min-height）、失败提示仅挂 .dsh-pm-cprog-detail-panel 外壳、head 行保留 flex-wrap。
- 落盘改动（filesChanged）：
- `packages/web/dsh-pmboard/src/client/styles/node-panel.ts`
- `packages/web/dsh-pmboard/tests/node-panel-styles.test.ts`

## 执行方式提示（executorHint）
本卡由自动链执行完成；卡面事实以 `../queue.json` 为准。不读会话历史，按本卡自足复核。
