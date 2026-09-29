# t-c5ae63 styles/node-panel.ts 新增入口按钮与失败提示两条规则·联调

> 任务卡骨架（自动链懒展开时只建了 TaskRecord、未落卡文档；本文件由窗口 `session-f17b3bd0` 按队列里的卡面事实回填，内容取自该子卡的实施方案与验收标准）

## 在做什么
新增 .dsh-pm-np-board-entry（flex:none、min-height、胶囊、hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则；不动 head-time 的 margin-left:auto；tests/node-panel-styles.test.ts 加 TC-14。 [子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 解决什么问题
把父卡 **t-71aeb3**（styles/node-panel.ts 新增入口按钮与失败提示两条规则）的交付拆成「联调」阶段并独立验收，避免父卡一步到位、问题不可定位。

## 范围
- 阶段：ui
- 端侧：frontend
- 子卡阶段：integrate

## 得到什么结果

在 packages/web/dsh-pmboard 下执行：npx vitest run tests/node-panel-styles.test.ts（期望 15 passed、exit 0）；并核对 src/client/styles/node-panel.ts 新增规则被 node-panel.ts 渲染出的 class 引用。

## 实施方案（implementation）
新增 .dsh-pm-np-board-entry（flex:none、min-height、胶囊、hover）与 .dsh-pm-cprog-detail-panel .dsh-pm-np-entry-err 两条作用域内规则；不动 head-time 的 margin-left:auto；tests/node-panel-styles.test.ts 加 TC-14。 [子卡阶段·联调] 只做本阶段；验收：接口联调通过：给出请求样例与期望响应，实际返回与预期一致

## 上游产出摘要（dependsSummary）
- t-0fc58f

## 执行留痕（自动链 run）
- 状态：done｜尝试次数：0
- 产出（completed）：
- 联调通过（34/34 断言一致）：以**真实渲染器 + 真实 injectStyles() 注入的 CSS（117316 字符全量 bundle）+ 真实浏览器（Chrome headless）**做端到端取数，请求样例与期望响应逐项一致。请求样例：DOM = renderNodePanel(design, REQ-test) 的真实输出，装入 conversation-progress.ts L345-378 同款外壳（.dsh-pm-cprog-detail-panel > [.dsh-pm-np-close, .dsh-pm-np-entry-err(role=alert), .dsh-pm-cprog-stage-detail>面板]）+ styles.ts injectStyles() 注入的 <style>。期望响应 → 实际响应（window.getComputedStyle）：入口按钮 .dsh-pm-np-board-entry flexGrow/flexShrink/flexBasis=0/0/auto（即 flex:none）、minHeight=20px、实渲染…
- 落盘改动（filesChanged）：
- （无落盘改动）

## 执行方式提示（executorHint）
本卡由自动链执行完成；卡面事实以 `../queue.json` 为准。不读会话历史，按本卡自足复核。
