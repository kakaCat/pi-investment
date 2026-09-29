# t-defa17 styles/node-panel.ts 新增入口按钮与失败提示两条规则·复核

> 任务卡骨架（自动链懒展开时只建了 TaskRecord、未落卡文档；本文件由窗口 `session-f17b3bd0` 按队列里的卡面事实回填，内容取自该子卡的实施方案与验收标准）

## 在做什么
新增 .dsh-pm-np-board-entry（flex:none、min-height、胶囊、hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则；不动 head-time 的 margin-left:auto；tests/node-panel-styles.test.ts 加 TC-14。 [子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 解决什么问题
把父卡 **t-71aeb3**（styles/node-panel.ts 新增入口按钮与失败提示两条规则）的交付拆成「复核」阶段并独立验收，避免父卡一步到位、问题不可定位。

## 范围
- 阶段：ui
- 端侧：frontend
- 子卡阶段：review

## 得到什么结果

在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed）；再对照 docs/requirements/REQ-260928222643-4d34/design/frontend.md 与 src/client/styles/node-panel.ts，逐条给出「无偏离」或偏离条目。

## 实施方案（implementation）
新增 .dsh-pm-np-board-entry（flex:none、min-height、胶囊、hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则；不动 head-time 的 margin-left:auto；tests/node-panel-styles.test.ts 加 TC-14。 [子卡阶段·复核] 只做本阶段；验收：对设计与实现的偏离逐条给出结论；无偏离时显式写明「无偏离」及依据

## 上游产出摘要（dependsSummary）
- t-c5ae63

## 执行留痕（自动链 run）
- 状态：done｜尝试次数：0
- 产出（completed）：
- 逐条比对设计（design/frontend.md P-2、design/test-cases.md TC-14、decomposition.md t6）与实现（styles/node-panel.ts、tests/node-panel-styles.test.ts）：1) .dsh-pm-np-board-entry 规则 11 项声明值逐字一致、:hover 与原型一致；2) .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 三项声明值逐字一致；3) .dsh-pm-np-head-time 的 margin-left:auto 未动、:root 令牌零变更；4) 两条新规则作用域合法，失败提示元素确实渲染在 .dsh-pm-cprog-detail-panel 内（conversation-progress.ts L357/L378），后代选择器真实生效；5) TC-14 三个断言覆盖设计要求。结论：无偏离。依据为 git diff 逐行核验与设计文档逐值对照，未运行父卡终态验收（该命令属测试段，且本步边界禁止执行）。
- 落盘改动（filesChanged）：
- （无落盘改动）

## 执行方式提示（executorHint）
本卡由自动链执行完成；卡面事实以 `../queue.json` 为准。不读会话历史，按本卡自足复核。
